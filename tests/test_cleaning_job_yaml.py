import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
JOB_PATH = REPO_ROOT / "infra" / "k8s" / "cleaning-job.yaml"


class TestCleaningJobYaml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        docs = list(yaml.safe_load_all(JOB_PATH.read_text(encoding="utf-8")))
        cls.job = docs[0]

    def test_job_shape(self):
        self.assertEqual(self.job["apiVersion"], "batch/v1")
        self.assertEqual(self.job["kind"], "Job")

    def test_parallel_indexed_settings(self):
        spec = self.job["spec"]
        self.assertEqual(spec["parallelism"], 3)
        self.assertEqual(spec["completions"], 3)
        self.assertEqual(spec["completionMode"], "Indexed")
        self.assertEqual(spec["backoffLimit"], 2)

    def test_container_and_env_contract(self):
        container = self.job["spec"]["template"]["spec"]["containers"][0]
        image = container["image"]
        self.assertIn("trip-cleaner:latest", image)
        self.assertIn(".dkr.ecr.us-east-1.amazonaws.com", image)

        args_script = "\n".join(container.get("args", []))
        self.assertIn("JOB_COMPLETION_INDEX", args_script)
        self.assertIn("python clean_trips.py", args_script)
        self.assertIn("s3://", args_script)
        self.assertIn("month=${MONTH}", args_script)

        env = {item["name"]: item for item in container["env"]}
        self.assertIn("AWS_DEFAULT_REGION", env)
        self.assertEqual(env["AWS_DEFAULT_REGION"].get("value"), "us-east-1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
