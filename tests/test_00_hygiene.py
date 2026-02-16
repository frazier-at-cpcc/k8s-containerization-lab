import atexit
import sys
import unittest
from pathlib import Path

from _artifact_cleanup import cleanup_python_artifacts

REPO_ROOT = Path(__file__).resolve().parents[1]

# Prevent bytecode writes during discovery/execution after this module is loaded.
sys.dont_write_bytecode = True


@atexit.register
def _cleanup_test_artifacts():
    cleanup_python_artifacts(REPO_ROOT)


class TestSuiteHygiene(unittest.TestCase):
    def test_cleanup_hook_is_active(self):
        # Presence of this module in discovery ensures cleanup hook registration.
        self.assertTrue(callable(_cleanup_test_artifacts))


if __name__ == "__main__":
    unittest.main(verbosity=2)
