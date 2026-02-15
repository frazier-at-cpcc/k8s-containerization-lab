#!/usr/bin/env python3
"""Clean trip CSV data and write normalized Parquet output.

Supports local files/directories and S3 URIs for both input and output.
"""

from __future__ import annotations

import argparse
import glob
import os
from io import BytesIO
from typing import Dict, List, Tuple
from urllib.parse import urlparse

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


COLUMN_ALIASES = {
    "pickup_datetime": ["pickup_datetime", "pickup_ts", "pickup_time", "tpep_pickup_datetime"],
    "pickup_zone_id": ["pickup_zone_id", "pickup_zone", "PULocationID"],
    "dropoff_zone_id": ["dropoff_zone_id", "dropoff_zone", "DOLocationID"],
    "trip_distance": ["trip_distance", "distance_miles", "distance"],
    "trip_duration_min": ["trip_duration_min", "duration_min", "duration_minutes"],
    "fare_amount": ["fare_amount", "total_amount", "fare"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean trip data and write Parquet output")
    parser.add_argument("--input", required=True, help="Input CSV file/path (local path or s3:// URI)")
    parser.add_argument("--output", required=True, help="Output Parquet path/prefix (local path or s3:// URI)")
    parser.add_argument("--min-duration", type=float, default=1.0, help="Minimum trip duration in minutes")
    parser.add_argument("--max-duration", type=float, default=180.0, help="Maximum trip duration in minutes")
    parser.add_argument("--min-distance", type=float, default=0.1, help="Minimum trip distance")
    parser.add_argument("--max-distance", type=float, default=100.0, help="Maximum trip distance")
    parser.add_argument("--min-fare", type=float, default=0.0, help="Minimum fare amount")
    parser.add_argument("--max-fare", type=float, default=500.0, help="Maximum fare amount")
    return parser.parse_args()


def is_s3_uri(path: str) -> bool:
    return path.startswith("s3://")


def split_s3_uri(uri: str) -> Tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Invalid S3 URI: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def list_input_sources(input_path: str, s3_client) -> List[str]:
    if is_s3_uri(input_path):
        bucket, key = split_s3_uri(input_path)
        if key.endswith(".csv"):
            return [input_path]

        prefix = key if key.endswith("/") or key == "" else f"{key}/"
        paginator = s3_client.get_paginator("list_objects_v2")
        sources: List[str] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                obj_key = obj["Key"]
                if obj_key.endswith(".csv"):
                    sources.append(f"s3://{bucket}/{obj_key}")
        return sorted(sources)

    if os.path.isfile(input_path):
        return [input_path]

    if os.path.isdir(input_path):
        return sorted(glob.glob(os.path.join(input_path, "*.csv")))

    if any(ch in input_path for ch in ["*", "?", "["]):
        return sorted(glob.glob(input_path))

    return []


def read_csv_source(path: str, s3_client) -> pd.DataFrame:
    if is_s3_uri(path):
        bucket, key = split_s3_uri(path)
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        payload = obj["Body"].read()
        return pd.read_csv(BytesIO(payload))

    return pd.read_csv(path)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: Dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = canonical
                break

    df = df.rename(columns=rename_map)

    missing = [canonical for canonical in COLUMN_ALIASES if canonical not in df.columns]
    if missing:
        raise ValueError(
            "Input is missing required columns after normalization: " + ", ".join(missing)
        )

    return df[[
        "pickup_datetime",
        "pickup_zone_id",
        "dropoff_zone_id",
        "trip_distance",
        "trip_duration_min",
        "fare_amount",
    ]].copy()


def clean_dataframe(df: pd.DataFrame, args: argparse.Namespace) -> Tuple[pd.DataFrame, Dict[str, int]]:
    initial_rows = len(df)

    df = normalize_columns(df)
    df["pickup_datetime"] = pd.to_datetime(df["pickup_datetime"], errors="coerce")

    numeric_cols = [
        "pickup_zone_id",
        "dropoff_zone_id",
        "trip_distance",
        "trip_duration_min",
        "fare_amount",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    null_mask = df.isnull().any(axis=1)
    dropped_nulls = int(null_mask.sum())
    df = df.loc[~null_mask].copy()

    duration_mask = (
        (df["trip_duration_min"] < args.min_duration)
        | (df["trip_duration_min"] > args.max_duration)
    )
    dropped_duration = int(duration_mask.sum())
    df = df.loc[~duration_mask].copy()

    distance_mask = (
        (df["trip_distance"] < args.min_distance)
        | (df["trip_distance"] > args.max_distance)
    )
    dropped_distance = int(distance_mask.sum())
    df = df.loc[~distance_mask].copy()

    fare_mask = (df["fare_amount"] < args.min_fare) | (df["fare_amount"] > args.max_fare)
    dropped_fare = int(fare_mask.sum())
    df = df.loc[~fare_mask].copy()

    df["pickup_zone_id"] = df["pickup_zone_id"].astype("int64")
    df["dropoff_zone_id"] = df["dropoff_zone_id"].astype("int64")
    df = df.sort_values("pickup_datetime").reset_index(drop=True)

    summary = {
        "input_rows": int(initial_rows),
        "dropped_nulls": dropped_nulls,
        "dropped_duration_outliers": dropped_duration,
        "dropped_distance_outliers": dropped_distance,
        "dropped_fare_outliers": dropped_fare,
        "output_rows": int(len(df)),
    }
    return df, summary


def resolve_output_target(output_path: str) -> str:
    if output_path.endswith(".parquet"):
        return output_path

    if is_s3_uri(output_path):
        bucket, key = split_s3_uri(output_path)
        key = key.rstrip("/")
        return f"s3://{bucket}/{key}/cleaned.parquet" if key else f"s3://{bucket}/cleaned.parquet"

    if output_path.endswith(os.sep) or os.path.isdir(output_path):
        return os.path.join(output_path, "cleaned.parquet")

    return os.path.join(output_path, "cleaned.parquet")


def write_parquet(df: pd.DataFrame, output_path: str, s3_client) -> str:
    target = resolve_output_target(output_path)
    table = pa.Table.from_pandas(df, preserve_index=False)

    if is_s3_uri(target):
        bucket, key = split_s3_uri(target)
        buffer = BytesIO()
        pq.write_table(table, buffer, compression="snappy")
        s3_client.put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())
        return target

    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    pq.write_table(table, target, compression="snappy")
    return target


def main() -> None:
    args = parse_args()
    s3_client = boto3.client("s3")

    sources = list_input_sources(args.input, s3_client)
    if not sources:
        raise FileNotFoundError(f"No CSV sources found under input: {args.input}")

    frames = [read_csv_source(path, s3_client) for path in sources]
    raw_df = pd.concat(frames, ignore_index=True)

    cleaned_df, summary = clean_dataframe(raw_df, args)
    output_target = write_parquet(cleaned_df, args.output, s3_client)

    print("Trip cleaning summary")
    print(f"Input rows: {summary['input_rows']}")
    print(f"Rows dropped (nulls): {summary['dropped_nulls']}")
    print(f"Rows dropped (duration outliers): {summary['dropped_duration_outliers']}")
    print(f"Rows dropped (distance outliers): {summary['dropped_distance_outliers']}")
    print(f"Rows dropped (fare outliers): {summary['dropped_fare_outliers']}")
    print(f"Output rows: {summary['output_rows']}")
    print(f"Output written to: {output_target}")


if __name__ == "__main__":
    main()
