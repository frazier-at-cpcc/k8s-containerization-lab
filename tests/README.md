# Lab Test Suite

This suite validates that the lab artifacts are internally consistent and executable as written.

## Quick Run (Local Contract Tests)

```bash
python3 tests/run_tests.py
```

## Include Optional Docker End-to-End Smoke Test (Part 1)

```bash
python3 tests/run_tests.py --docker
```

## Include Optional Live AWS Learner Lab Checks

```bash
python3 tests/run_tests.py --aws --aws-stage 1 --bucket <your-bucket>
```

## Validate AWS Cleanup (No Provisioned Resources Remaining)

```bash
python3 tests/validate_aws_cleanup.py --region us-west-2 --bucket <your-bucket>
```

This command fails with exit code `1` if any of the following still exist:

- non-terminated EC2 instances
- EKS clusters
- active EMR clusters
- ECR repo `trip-cleaner` (configurable)
- Glue DB `lab2_analytics` (configurable)
- objects under `cleaned/`, `aggregated/`, `athena-results/` in the given bucket (configurable)

You can increase `--aws-stage` as you progress through the lab:

- `--aws-stage 1`: Validates Part 1 artifacts (S3 raw uploads + ECR image tag)
- `--aws-stage 2`: Adds cleaned output checks + EKS constraints/cleanup checks
- `--aws-stage 3`: Adds aggregated output checks + EMR constraints/cleanup checks
- `--aws-stage 4`: Adds Athena output location + Glue table contract checks

Optional flags:

- `--eks-cluster <name>`: Validate active EKS cluster/node role settings for `LabEksClusterRole`

## Environment Variables Used by AWS Tests

These can be set directly, or via `tests/run_tests.py` flags where available.

- `LAB_RUN_AWS=1`: Enable AWS live checks
- `LAB_STAGE=1..4`: Select stage-aware checks
- `LAB_BUCKET=<bucket-name>`: Bucket to validate
- `LAB_ECR_REPO` (default `trip-cleaner`)
- `LAB_ECR_TAG` (default `latest`)
- `LAB_EKS_CLUSTER_NAME` (optional)
- `LAB_EXPECT_NO_EKS` (default `1`)
- `LAB_EXPECT_NO_EMR` (default `1`)
- `LAB_STRICT_EMR_M4_LARGE` (default `1`)
- `LAB_REQUIRE_ATHENA_OUTPUT` (default `1`)
- `LAB_ATHENA_WORKGROUP` (default `primary`)
- `LAB_GLUE_DB` (default `lab2_analytics`)
- `LAB_GLUE_HOURLY_TABLE` (default `hourly_trips`)
- `LAB_GLUE_DAILY_TABLE` (default `daily_summary`)

## What Is Covered

- Required lab files and non-empty artifacts
- `src/clean_trips.py` contract and core cleaning logic
- Kubernetes job manifest structure (`infra/k8s/cleaning-job.yaml`)
- Spark script interface and output contract markers (`src/spark_aggregations.py`)
- Athena DDL/query contract checks (`infra/sql/athena_ddl.sql`)
- Optional Docker build+run smoke test for Part 1
- Optional live AWS Learner Lab constraints and stage checks

## Notes

- Live AWS tests require valid AWS credentials/session and network access.
- In restricted local environments, AWS tests may skip automatically if AWS is unreachable.
- Optional Docker test uses a unique temporary image tag and removes that image in cleanup.
- `tests/run_tests.py` sets `PYTHONDONTWRITEBYTECODE=1`, runs Python with `-B`, and removes any new `__pycache__`/`.pyc` artifacts after the run.
- `tests/test_00_hygiene.py` registers an `atexit` cleanup hook so direct `unittest` runs also clean newly created Python cache artifacts.
