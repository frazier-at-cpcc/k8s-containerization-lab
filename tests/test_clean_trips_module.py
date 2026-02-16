import argparse
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "clean_trips.py"


class _FakeS3Client:
    def __init__(self):
        self.put_calls = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)


def _load_clean_trips_with_stubs():
    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = lambda *_args, **_kwargs: _FakeS3Client()

    fake_pa = types.ModuleType("pyarrow")

    class _FakeTable:
        @staticmethod
        def from_pandas(df, preserve_index=False):
            return {"rows": len(df), "preserve_index": preserve_index}

    fake_pa.Table = _FakeTable

    fake_pq = types.ModuleType("pyarrow.parquet")

    def _write_table(_table, target, compression="snappy"):
        payload = b"PAR1"
        if hasattr(target, "write"):
            target.write(payload)
            return
        path = Path(str(target))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    fake_pq.write_table = _write_table

    originals = {
        "boto3": sys.modules.get("boto3"),
        "pyarrow": sys.modules.get("pyarrow"),
        "pyarrow.parquet": sys.modules.get("pyarrow.parquet"),
    }

    sys.modules["boto3"] = fake_boto3
    sys.modules["pyarrow"] = fake_pa
    sys.modules["pyarrow.parquet"] = fake_pq

    try:
        spec = importlib.util.spec_from_file_location("clean_trips_testable", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in originals.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


class TestCleanTripsModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_clean_trips_with_stubs()

    def test_normalize_columns_accepts_aliases(self):
        df = pd.DataFrame(
            {
                "pickup_ts": ["2023-01-01 00:00:00"],
                "PULocationID": [1],
                "DOLocationID": [2],
                "distance": [2.4],
                "duration_minutes": [10],
                "total_amount": [12.5],
            }
        )
        out = self.mod.normalize_columns(df)
        self.assertEqual(
            list(out.columns),
            [
                "pickup_datetime",
                "pickup_zone_id",
                "dropoff_zone_id",
                "trip_distance",
                "trip_duration_min",
                "fare_amount",
            ],
        )

    def test_clean_dataframe_summary_counts(self):
        df = pd.DataFrame(
            {
                "pickup_datetime": [
                    "2023-01-01 00:05:00",  # valid
                    "2023-01-01 00:06:00",  # null fare
                    "2023-01-01 00:07:00",  # duration too short
                    "2023-01-01 00:08:00",  # distance too long
                    "2023-01-01 00:09:00",  # fare too high
                    "2023-01-01 00:01:00",  # valid, earlier time
                ],
                "pickup_zone_id": [1, 1, 1, 1, 1, 2],
                "dropoff_zone_id": [2, 2, 2, 2, 2, 3],
                "trip_distance": [2.0, 2.0, 2.0, 150.0, 2.0, 1.0],
                "trip_duration_min": [12.0, 12.0, 0.5, 12.0, 12.0, 15.0],
                "fare_amount": [11.0, None, 11.0, 11.0, 900.0, 8.0],
            }
        )

        args = argparse.Namespace(
            min_duration=1.0,
            max_duration=180.0,
            min_distance=0.1,
            max_distance=100.0,
            min_fare=0.0,
            max_fare=500.0,
        )

        cleaned, summary = self.mod.clean_dataframe(df, args)

        self.assertEqual(summary["input_rows"], 6)
        self.assertEqual(summary["dropped_nulls"], 1)
        self.assertEqual(summary["dropped_duration_outliers"], 1)
        self.assertEqual(summary["dropped_distance_outliers"], 1)
        self.assertEqual(summary["dropped_fare_outliers"], 1)
        self.assertEqual(summary["output_rows"], 2)

        # Should be sorted by pickup time ascending.
        self.assertLess(cleaned.iloc[0]["pickup_datetime"], cleaned.iloc[1]["pickup_datetime"])

    def test_resolve_output_target_variants(self):
        self.assertEqual(
            self.mod.resolve_output_target("s3://bucket/path/"),
            "s3://bucket/path/cleaned.parquet",
        )
        self.assertEqual(
            self.mod.resolve_output_target("s3://bucket"),
            "s3://bucket/cleaned.parquet",
        )
        self.assertTrue(
            self.mod.resolve_output_target("local/out").endswith("cleaned.parquet")
        )
        self.assertEqual(
            self.mod.resolve_output_target("already.parquet"),
            "already.parquet",
        )

    def test_list_input_sources_local_patterns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a.csv"
            b = root / "b.csv"
            c = root / "c.txt"
            a.write_text("x\n1\n", encoding="utf-8")
            b.write_text("x\n2\n", encoding="utf-8")
            c.write_text("x\n3\n", encoding="utf-8")

            sources_dir = self.mod.list_input_sources(str(root), s3_client=None)
            self.assertEqual([str(a), str(b)], sources_dir)

            sources_file = self.mod.list_input_sources(str(a), s3_client=None)
            self.assertEqual([str(a)], sources_file)

            sources_glob = self.mod.list_input_sources(str(root / "*.csv"), s3_client=None)
            self.assertEqual([str(a), str(b)], sources_glob)

    def test_write_parquet_local_and_s3(self):
        df = pd.DataFrame(
            {
                "pickup_datetime": pd.to_datetime(["2023-01-01 00:00:00"]),
                "pickup_zone_id": [1],
                "dropoff_zone_id": [2],
                "trip_distance": [1.0],
                "trip_duration_min": [10.0],
                "fare_amount": [5.0],
            }
        )

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "out"
            target = self.mod.write_parquet(df, str(out_dir), s3_client=_FakeS3Client())
            self.assertTrue(Path(target).exists())

        s3_client = _FakeS3Client()
        s3_target = self.mod.write_parquet(df, "s3://bucket/prefix/", s3_client=s3_client)
        self.assertEqual(s3_target, "s3://bucket/prefix/cleaned.parquet")
        self.assertEqual(len(s3_client.put_calls), 1)
        self.assertEqual(s3_client.put_calls[0]["Bucket"], "bucket")
        self.assertEqual(s3_client.put_calls[0]["Key"], "prefix/cleaned.parquet")
        self.assertGreater(len(s3_client.put_calls[0]["Body"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
