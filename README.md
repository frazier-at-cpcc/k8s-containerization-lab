# DSBA 6190 Lab 2 Support Files

This repository contains the support files for **AWS Lab 2: Distributed Computing for Data Processing**.

## Included Files

- `clean_trips.py`: Python cleaning pipeline (CSV -> Parquet) with local + S3 support.
- `Dockerfile`: Container image definition for `clean_trips.py`.
- `sample_trips.csv`: Small test input for Part 1 local container validation.
- `trips_2023_01.csv`, `trips_2023_02.csv`, `trips_2023_03.csv`: Monthly raw partitions for Parts 2-3.
- `cleaning-job.yaml`: EKS Indexed Job to run three parallel cleaning pods.
- `spark_aggregations.py`: EMR Spark script to produce hourly and daily aggregated outputs.
- `zone_lookup.csv`: Zone ID -> zone name lookup table used by Spark job.
- `athena_ddl.sql`: Athena/Glue DDL + analysis queries for Part 4.
- `lab2-distributed-computing.pdf`: Official lab guide.

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

1. Upload all files to your S3 bucket (`dsba6190-yourname-lab2`) as described in the lab PDF.
2. On the EC2 Docker build instance:

```bash
mkdir ~/lab2 && cd ~/lab2
aws s3 cp s3://<BUCKET>/clean_trips.py .
aws s3 cp s3://<BUCKET>/sample_trips.csv .
# Create Dockerfile from this repo's Dockerfile content
# (or upload Dockerfile to S3 first and copy it here).

docker build -t trip-cleaner:latest .
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
2. Update these placeholders in `cleaning-job.yaml`:
   - `image: <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/trip-cleaner:latest`
   - `s3://dsba6190-yourname-lab2/...` paths
3. Submit and monitor:

```bash
kubectl apply -f cleaning-job.yaml
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

Use `athena_ddl.sql` after replacing bucket names. It includes:

- `CREATE DATABASE lab2_analytics`
- External table DDL for `hourly_trips`
- External partitioned table DDL for `daily_summary`
- `MSCK REPAIR TABLE`
- Query A/B/C from the lab write-up

## Important Lab Constraints

- Keep total running instances within Learner Lab limits.
- EKS must use the required Learner Lab IAM role settings from the lab guide.
- EMR clusters do not survive session end; always write outputs to S3 and terminate explicitly.
- Athena requires query results location set (for example `s3://<BUCKET>/athena-results/`).

## Notes

- `clean_trips.py` depends on `pandas`, `pyarrow`, and `boto3` (installed by the Dockerfile).
- For reproducible execution, run the cleaner through the container image in Part 1/2.
