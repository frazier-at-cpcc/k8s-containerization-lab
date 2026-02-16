import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPARK_SCRIPT = REPO_ROOT / "src" / "spark_aggregations.py"


class TestSparkScriptContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SPARK_SCRIPT.read_text(encoding="utf-8")

    def test_cli_args_present(self):
        self.assertIn("--input", self.text)
        self.assertIn("--zones", self.text)
        self.assertIn("--output", self.text)

    def test_required_logic_markers_present(self):
        self.assertIn("spark.sql.session.timeZone", self.text)
        self.assertIn("UTC", self.text)
        self.assertIn("percentile_approx", self.text)
        self.assertIn("daily_summary", self.text)
        self.assertIn("hourly", self.text)
        self.assertIn('partitionBy("date")', self.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
