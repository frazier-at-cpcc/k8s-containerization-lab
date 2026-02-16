import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestLabFiles(unittest.TestCase):
    def test_required_files_exist_and_non_empty(self):
        required = [
            "README.md",
            "src/clean_trips.py",
            "src/spark_aggregations.py",
            "infra/docker/Dockerfile",
            "infra/k8s/cleaning-job.yaml",
            "infra/sql/athena_ddl.sql",
            "data/sample/sample_trips.csv",
            "data/raw/trips_2023_01.csv",
            "data/raw/trips_2023_02.csv",
            "data/raw/trips_2023_03.csv",
            "data/reference/zone_lookup.csv",
            "docs/lab/lab2-distributed-computing.pdf",
            "tests/run_tests.py",
            "tests/validate_aws_cleanup.py",
        ]

        for rel in required:
            path = REPO_ROOT / rel
            with self.subTest(path=rel):
                self.assertTrue(path.exists(), f"Missing required file: {rel}")
                self.assertGreater(path.stat().st_size, 0, f"File is empty: {rel}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
