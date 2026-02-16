#!/usr/bin/env python3
"""Run Spark aggregations for trip analytics outputs."""

from __future__ import annotations

import argparse

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate cleaned trip data with Spark")
    parser.add_argument("--input", required=True, help="Input cleaned Parquet root path")
    parser.add_argument("--zones", required=True, help="Zone lookup CSV path")
    parser.add_argument("--output", required=True, help="Output root path for aggregated tables")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    spark = (
        SparkSession.builder.appName("lab2-trip-aggregations")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )

    cleaned = spark.read.option("recursiveFileLookup", "true").parquet(args.input)

    required_cols = {
        "pickup_datetime",
        "pickup_zone_id",
        "trip_duration_min",
        "fare_amount",
    }
    missing = sorted(required_cols.difference(set(cleaned.columns)))
    if missing:
        raise ValueError(f"Cleaned input missing required columns: {', '.join(missing)}")

    zones = (
        spark.read.option("header", "true")
        .option("inferSchema", "true")
        .csv(args.zones)
        .select(
            F.col("zone_id").cast("int").alias("zone_id"),
            F.col("zone_name").alias("zone_name"),
        )
    )

    cleaned_cast = cleaned.withColumn("pickup_zone_id", F.col("pickup_zone_id").cast("int")).alias("c")
    zones_lookup = zones.alias("z")

    enriched = (
        cleaned_cast.join(zones_lookup, F.col("c.pickup_zone_id") == F.col("z.zone_id"), "left")
        .withColumn(
            "pickup_zone",
            F.coalesce(F.col("zone_name"), F.concat(F.lit("Zone "), F.col("pickup_zone_id"))),
        )
        .withColumn("pickup_date", F.to_date(F.col("pickup_datetime")))
        .withColumn("hour_of_day", F.hour(F.col("pickup_datetime")))
    )

    hourly = (
        enriched.groupBy("pickup_zone", "hour_of_day")
        .agg(
            F.count("*").alias("trip_count"),
            F.round(F.avg("fare_amount"), 2).alias("avg_fare"),
            F.round(F.avg("trip_duration_min"), 2).alias("avg_duration_min"),
            F.round(F.expr("percentile_approx(fare_amount, 0.9)"), 2).alias("p90_fare"),
        )
        .orderBy("pickup_zone", "hour_of_day")
    )

    daily_summary = (
        enriched.groupBy("pickup_zone", F.date_format("pickup_date", "yyyy-MM-dd").alias("date"))
        .agg(
            F.round(F.sum("fare_amount"), 2).alias("total_revenue"),
            F.count("*").alias("trip_volume"),
        )
        .orderBy("date", "pickup_zone")
    )

    hourly_output = args.output.rstrip("/") + "/hourly"
    daily_output = args.output.rstrip("/") + "/daily_summary"

    hourly.write.mode("overwrite").parquet(hourly_output)
    daily_summary.write.mode("overwrite").partitionBy("date").parquet(daily_output)

    print(f"Hourly output written to: {hourly_output}")
    print(f"Daily summary output written to: {daily_output}")

    spark.stop()


if __name__ == "__main__":
    main()
