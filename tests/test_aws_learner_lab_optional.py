import json
import os
import shutil
import subprocess
import unittest
from collections import Counter

RUN_AWS = os.getenv("LAB_RUN_AWS") == "1"


class AWSCliError(RuntimeError):
    pass


def _run_aws(cmd_args, region=None):
    cmd = ["aws", *cmd_args]
    if region and "--region" not in cmd_args:
        cmd.extend(["--region", region])
    if "--output" not in cmd_args:
        cmd.extend(["--output", "json"])

    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if proc.returncode != 0:
        raise AWSCliError(proc.stdout.strip())

    out = proc.stdout.strip()
    if not out:
        return {}
    return json.loads(out)


@unittest.skipUnless(RUN_AWS, "Set LAB_RUN_AWS=1 to run live AWS Learner Lab checks")
class TestAWSLearnerLabOptional(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("aws"):
            raise unittest.SkipTest("AWS CLI is not installed")

        cls.region = os.getenv("AWS_REGION", "us-east-1")
        cls.stage = int(os.getenv("LAB_STAGE", "0") or "0")

        try:
            cls.identity = _run_aws(["sts", "get-caller-identity"], region=cls.region)
        except AWSCliError as exc:
            raise unittest.SkipTest(f"AWS unavailable in this runtime: {exc}")

    def _require_bucket(self):
        bucket = os.getenv("LAB_BUCKET", "").strip()
        if not bucket:
            self.skipTest("Set LAB_BUCKET to run S3-backed lab artifact checks")
        return bucket

    def _assert_s3_prefix_has_object(self, bucket, prefix):
        data = _run_aws(
            ["s3api", "list-objects-v2", "--bucket", bucket, "--prefix", prefix, "--max-items", "1"],
            region=self.region,
        )
        found = int(data.get("KeyCount", 0)) > 0
        self.assertTrue(found, f"Expected at least one object under s3://{bucket}/{prefix}")

    def test_identity_works(self):
        self.assertIn("Account", self.identity)
        self.assertIn("Arn", self.identity)

    def test_ec2_running_limits_and_sizes(self):
        # Learner Lab constraints from lab guide:
        # <= 9 concurrent EC2 instances, <= 32 vCPU, only nano/micro/small/medium/large.
        reservations = _run_aws(
            [
                "ec2",
                "describe-instances",
                "--filters",
                "Name=instance-state-name,Values=pending,running",
            ],
            region=self.region,
        ).get("Reservations", [])

        instances = []
        for r in reservations:
            for inst in r.get("Instances", []):
                instances.append(inst)

        self.assertLessEqual(
            len(instances),
            9,
            f"Running/pending EC2 instances exceed Learner Lab limit: {len(instances)} > 9",
        )

        if not instances:
            return

        allowed_sizes = {"nano", "micro", "small", "medium", "large"}
        type_counts = Counter(inst["InstanceType"] for inst in instances)

        for itype in type_counts:
            size = itype.split(".")[-1]
            self.assertIn(
                size,
                allowed_sizes,
                f"Instance type not in Learner Lab allowed sizes: {itype}",
            )

        describe = _run_aws(
            ["ec2", "describe-instance-types", "--instance-types", *sorted(type_counts.keys())],
            region=self.region,
        )
        vcpu_map = {
            item["InstanceType"]: item["VCpuInfo"]["DefaultVCpus"]
            for item in describe.get("InstanceTypes", [])
        }
        total_vcpu = sum(vcpu_map[t] * c for t, c in type_counts.items())

        self.assertLessEqual(
            total_vcpu,
            32,
            f"Running/pending EC2 vCPU exceed Learner Lab limit: {total_vcpu} > 32",
        )

    def test_part1_stage_artifacts(self):
        if self.stage < 1:
            self.skipTest("Set LAB_STAGE>=1 after completing Part 1 checks")

        bucket = self._require_bucket()

        # Raw partitions and scripts/reference uploads expected by lab.
        self._assert_s3_prefix_has_object(bucket, "raw/month=01/")
        self._assert_s3_prefix_has_object(bucket, "raw/month=02/")
        self._assert_s3_prefix_has_object(bucket, "raw/month=03/")
        self._assert_s3_prefix_has_object(bucket, "scripts/spark_aggregations.py")
        self._assert_s3_prefix_has_object(bucket, "reference/zone_lookup.csv")

        repo = os.getenv("LAB_ECR_REPO", "trip-cleaner")
        tag = os.getenv("LAB_ECR_TAG", "latest")

        _run_aws(["ecr", "describe-repositories", "--repository-names", repo], region=self.region)
        images = _run_aws(["ecr", "describe-images", "--repository-name", repo], region=self.region).get("imageDetails", [])
        has_tag = any(tag in detail.get("imageTags", []) for detail in images)
        self.assertTrue(has_tag, f"ECR repo '{repo}' missing expected tag '{tag}'")

    def test_part2_cleaned_outputs_and_eks_constraints(self):
        if self.stage < 2:
            self.skipTest("Set LAB_STAGE>=2 after completing Part 2 checks")

        bucket = self._require_bucket()

        cleaned_listing = _run_aws(
            ["s3api", "list-objects-v2", "--bucket", bucket, "--prefix", "cleaned/"],
            region=self.region,
        )
        parquet_count = sum(1 for o in cleaned_listing.get("Contents", []) if o.get("Key", "").endswith(".parquet"))
        self.assertGreaterEqual(parquet_count, 3, "Expected at least 3 cleaned parquet files after Part 2")

        cluster_name = os.getenv("LAB_EKS_CLUSTER_NAME", "").strip()
        if cluster_name:
            cluster = _run_aws(["eks", "describe-cluster", "--name", cluster_name], region=self.region)["cluster"]
            self.assertIn(
                "LabEksClusterRole",
                cluster.get("roleArn", ""),
                "EKS cluster role should be LabEksClusterRole in Learner Lab",
            )

            nodegroups = _run_aws(["eks", "list-nodegroups", "--cluster-name", cluster_name], region=self.region).get("nodegroups", [])
            for ng in nodegroups:
                desc = _run_aws(
                    ["eks", "describe-nodegroup", "--cluster-name", cluster_name, "--nodegroup-name", ng],
                    region=self.region,
                )["nodegroup"]
                self.assertIn(
                    "LabEksClusterRole",
                    desc.get("nodeRole", ""),
                    f"Nodegroup '{ng}' role should be LabEksClusterRole",
                )
                for itype in desc.get("instanceTypes", []):
                    size = itype.split(".")[-1]
                    self.assertIn(size, {"nano", "micro", "small", "medium", "large"})

        if os.getenv("LAB_EXPECT_NO_EKS", "1") == "1":
            clusters = _run_aws(["eks", "list-clusters"], region=self.region).get("clusters", [])
            self.assertEqual(clusters, [], "Expected no remaining EKS clusters (cleanup check)")

    def test_part3_aggregated_outputs_and_emr_constraints(self):
        if self.stage < 3:
            self.skipTest("Set LAB_STAGE>=3 after completing Part 3 checks")

        bucket = self._require_bucket()
        self._assert_s3_prefix_has_object(bucket, "aggregated/hourly/")
        self._assert_s3_prefix_has_object(bucket, "aggregated/daily_summary/")

        active_states = ["STARTING", "BOOTSTRAPPING", "RUNNING", "WAITING"]
        clusters = _run_aws(["emr", "list-clusters", "--active"], region=self.region).get("Clusters", [])

        if os.getenv("LAB_EXPECT_NO_EMR", "1") == "1":
            self.assertEqual(clusters, [], "Expected no active EMR clusters (cleanup check)")

        if os.getenv("LAB_STRICT_EMR_M4_LARGE", "1") == "1":
            for cluster in clusters:
                cid = cluster["Id"]
                groups = _run_aws(["emr", "list-instance-groups", "--cluster-id", cid], region=self.region).get(
                    "InstanceGroups", []
                )
                for g in groups:
                    self.assertEqual(
                        g.get("InstanceType"),
                        "m4.large",
                        f"EMR cluster {cid} has non-compliant instance type: {g.get('InstanceType')}",
                    )

    def test_part4_athena_and_glue_contract(self):
        if self.stage < 4:
            self.skipTest("Set LAB_STAGE>=4 after completing Part 4 checks")

        if os.getenv("LAB_REQUIRE_ATHENA_OUTPUT", "1") == "1":
            wg = os.getenv("LAB_ATHENA_WORKGROUP", "primary")
            cfg = _run_aws(["athena", "get-work-group", "--work-group", wg], region=self.region)["WorkGroup"][
                "Configuration"
            ]
            out = cfg.get("ResultConfiguration", {}).get("OutputLocation", "")
            self.assertTrue(out.startswith("s3://"), "Athena result output location is not configured")

        db = os.getenv("LAB_GLUE_DB", "lab2_analytics")
        hourly = os.getenv("LAB_GLUE_HOURLY_TABLE", "hourly_trips")
        daily = os.getenv("LAB_GLUE_DAILY_TABLE", "daily_summary")

        _run_aws(["glue", "get-database", "--name", db], region=self.region)
        _run_aws(["glue", "get-table", "--database-name", db, "--name", hourly], region=self.region)
        daily_tbl = _run_aws(
            ["glue", "get-table", "--database-name", db, "--name", daily],
            region=self.region,
        )["Table"]

        partition_keys = [k["Name"] for k in daily_tbl.get("PartitionKeys", [])]
        self.assertIn("date", partition_keys, "Expected 'date' partition key on daily_summary table")


if __name__ == "__main__":
    unittest.main(verbosity=2)
