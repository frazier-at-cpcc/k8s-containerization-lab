import os
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_DOCKER = os.getenv("LAB_RUN_DOCKER") == "1"


def _run_or_skip(cmd, cwd):
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        output = exc.stdout or ""
        lowered = output.lower()
        if "operation not permitted" in lowered or "permission denied" in lowered:
            raise unittest.SkipTest("Docker command blocked by runtime permissions/sandbox")
        raise


@unittest.skipUnless(RUN_DOCKER, "Set LAB_RUN_DOCKER=1 to run Docker integration smoke test")
class TestLabIntegrationOptional(unittest.TestCase):
    def setUp(self):
        # Unique image tag to avoid clobbering user tags; cleaned in tearDown cleanup.
        self.tag = f"trip-cleaner:lab-test-{uuid.uuid4().hex[:12]}"
        self.addCleanup(self._cleanup_docker_image)

    def _cleanup_docker_image(self):
        # Best effort cleanup: never fail the suite if cleanup itself is blocked.
        subprocess.run(
            ["docker", "image", "rm", "-f", self.tag],
            cwd=REPO_ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def test_part1_container_build_and_run(self):
        _run_or_skip(
            ["docker", "build", "-f", "infra/docker/Dockerfile", "-t", self.tag, "."],
            cwd=REPO_ROOT,
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sample_src = REPO_ROOT / "data" / "sample" / "sample_trips.csv"
            sample_dst = tmp_path / "sample_trips.csv"
            sample_dst.write_bytes(sample_src.read_bytes())

            output_dst = tmp_path / "cleaned_sample.parquet"

            _run_or_skip(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{tmp_path}:/data",
                    self.tag,
                    "--input",
                    "/data/sample_trips.csv",
                    "--output",
                    "/data/cleaned_sample.parquet",
                ],
                cwd=REPO_ROOT,
            )

            self.assertTrue(output_dst.exists(), "Container did not produce cleaned_sample.parquet")
            self.assertGreater(output_dst.stat().st_size, 0, "Produced parquet file is empty")


if __name__ == "__main__":
    unittest.main(verbosity=2)
