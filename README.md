# DSBA 6190 Lab 2 Repository

This repository contains support materials for **AWS Lab 2: Distributed Computing for Data Processing**, plus lecture artifacts and validation tooling.

## Repository Layout

```text
.
├── src/
│   ├── clean_trips.py
│   └── spark_aggregations.py
├── infra/
│   ├── docker/Dockerfile
│   ├── k8s/cleaning-job.yaml
│   └── sql/athena_ddl.sql
├── data/
│   ├── sample/sample_trips.csv
│   ├── raw/trips_2023_01.csv
│   ├── raw/trips_2023_02.csv
│   ├── raw/trips_2023_03.csv
│   └── reference/zone_lookup.csv
├── docs/
│   ├── lab/lab2-distributed-computing.pdf
│   ├── lecture/
│   └── slides/
├── diagrams/aws/
├── notebooks/
└── tests/
```

## Core Assets

- `src/clean_trips.py`: containerized cleaning pipeline (CSV -> Parquet), local + S3.
- `infra/docker/Dockerfile`: image definition for the cleaning pipeline.
- `infra/k8s/cleaning-job.yaml`: EKS indexed batch job for partition-parallel cleaning.
- `src/spark_aggregations.py`: EMR Spark aggregations for hourly + daily outputs.
- `infra/sql/athena_ddl.sql`: Athena/Glue DDL and query patterns.
- `docs/lab/lab2-distributed-computing.pdf`: official lab guide.

Recommended S3 upload mapping for the lab:

- `src/clean_trips.py` -> `s3://<BUCKET>/clean_trips.py`
- `infra/docker/Dockerfile` -> `s3://<BUCKET>/Dockerfile`
- `data/sample/sample_trips.csv` -> `s3://<BUCKET>/sample_trips.csv`
- `src/spark_aggregations.py` -> `s3://<BUCKET>/scripts/spark_aggregations.py`
- `data/reference/zone_lookup.csv` -> `s3://<BUCKET>/reference/zone_lookup.csv`
- `data/raw/trips_2023_*.csv` -> `s3://<BUCKET>/raw/month=MM/`

## Data Schema Used Across Scripts

Raw/cleaned data columns:

- `pickup_datetime` (timestamp)
- `pickup_zone_id` (int)
- `dropoff_zone_id` (int)
- `trip_distance` (double)
- `trip_duration_min` (double)
- `fare_amount` (double)

Spark outputs:

- `aggregated/hourly/`: `pickup_zone`, `hour_of_day`, `trip_count`, `avg_fare`, `avg_duration_min`, `p90_fare`
- `aggregated/daily_summary/`: `pickup_zone`, `total_revenue`, `trip_volume`, partitioned by `date`

## Part 1: Container Build and ECR Push

1. Upload files to your S3 bucket (`dsba6190-yourname-lab2`) as described in the lab PDF.
2. On the EC2 Docker build instance:

```bash
mkdir ~/lab2 && cd ~/lab2
mkdir -p src infra/docker
aws s3 cp s3://<BUCKET>/clean_trips.py src/clean_trips.py
aws s3 cp s3://<BUCKET>/Dockerfile infra/docker/Dockerfile
aws s3 cp s3://<BUCKET>/sample_trips.csv sample_trips.csv

docker build -f infra/docker/Dockerfile -t trip-cleaner:latest .
docker run --rm -v ~/lab2:/data trip-cleaner:latest \
  --input /data/sample_trips.csv \
  --output /data/cleaned_sample.parquet
```

3. Push image to ECR:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1

aws ecr create-repository --repository-name trip-cleaner --region $REGION
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

docker tag trip-cleaner:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/trip-cleaner:latest
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/trip-cleaner:latest
```

## Part 2: EKS Batch Cleaning

1. Create EKS cluster with `eksctl` per lab instructions.
2. Update placeholders in `infra/k8s/cleaning-job.yaml`:
   - `image: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/trip-cleaner:latest`
   - `s3://dsba6190-yourname-lab2/...` paths
3. Submit and monitor:

```bash
kubectl apply -f infra/k8s/cleaning-job.yaml
kubectl get jobs --watch
kubectl get pods
kubectl logs <pod-name>
aws s3 ls s3://<BUCKET>/cleaned/ --recursive
```

4. Delete the EKS cluster when done.

## Part 3: EMR Spark Aggregations

1. Create EMR cluster (m4.large primary/core/task) per lab guide.
2. Add Spark step:

- Script: `s3://<BUCKET>/scripts/spark_aggregations.py`
- Arguments:
  - `--input s3://<BUCKET>/cleaned/`
  - `--zones s3://<BUCKET>/reference/zone_lookup.csv`
  - `--output s3://<BUCKET>/aggregated/`

3. Validate output:

```bash
aws s3 ls s3://<BUCKET>/aggregated/hourly/
aws s3 ls s3://<BUCKET>/aggregated/daily_summary/
```

4. Terminate EMR cluster.

## Part 4: Athena/Glue Query Layer

Use `infra/sql/athena_ddl.sql` after replacing bucket names.

## Lab Constraints

- Keep total running instances within Learner Lab limits.
- EKS must use required Learner Lab IAM roles from the lab guide.
- EMR clusters do not survive session end; always write outputs to S3 and terminate explicitly.
- Athena requires query results location (for example `s3://<BUCKET>/athena-results/`).

## Validation Commands

```bash
python3 tests/run_tests.py
python3 tests/run_tests.py --docker
python3 tests/run_tests.py --aws
python3 tests/validate_aws_cleanup.py --region us-west-2 --bucket <your-bucket>
```

## Notes

- `src/clean_trips.py` depends on `pandas`, `pyarrow`, and `boto3` (installed by the Docker image).
- For reproducible execution, run cleaning through the container image for Part 1 and Part 2.
