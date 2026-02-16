import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = REPO_ROOT / "infra" / "sql" / "athena_ddl.sql"


class TestAthenaSql(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = SQL_PATH.read_text(encoding="utf-8")
        cls.sql_lower = cls.sql.lower()

    def test_contains_core_ddl(self):
        self.assertIn("create database if not exists lab2_analytics", self.sql_lower)
        self.assertIn("create external table if not exists lab2_analytics.hourly_trips", self.sql_lower)
        self.assertIn("create external table if not exists lab2_analytics.daily_summary", self.sql_lower)

    def test_daily_summary_partitioning(self):
        self.assertRegex(
            self.sql_lower,
            r"partitioned\s+by\s*\(\s*date\s+string\s*\)",
        )
        self.assertIn("msck repair table lab2_analytics.daily_summary", self.sql_lower)

    def test_includes_partition_pruning_query_pair(self):
        # Expect one query without date filter and one with date filter.
        self.assertIn("from lab2_analytics.daily_summary", self.sql_lower)
        self.assertIn("where date = '2023-01-15'", self.sql_lower)

        no_filter_pattern = re.compile(
            r"select\s+pickup_zone,\s*sum\(total_revenue\)\s+as\s+revenue\s*"
            r"from\s+lab2_analytics\.daily_summary\s*"
            r"group\s+by\s+pickup_zone",
            re.IGNORECASE | re.DOTALL,
        )
        self.assertRegex(self.sql, no_filter_pattern)


if __name__ == "__main__":
    unittest.main(verbosity=2)
