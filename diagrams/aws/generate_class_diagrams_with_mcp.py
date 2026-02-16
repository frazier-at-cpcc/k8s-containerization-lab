#!/usr/bin/env python3
"""Generate class-session AWS diagrams using the AWS Diagram MCP server package."""

from __future__ import annotations

import asyncio
from pathlib import Path

from awslabs.aws_diagram_mcp_server.diagrams_tools import generate_diagram


WORKSPACE = Path(__file__).resolve().parent

DIAGRAMS = {
    "class-batch-analytics-platform": """
with Diagram("Class Session - AWS Batch Analytics Platform", show=False, direction="LR"):
    raw_zone = S3("Raw Zone (CSV)")

    with Cluster("Containerized Cleaning"):
        ecr_repo = ECR("ECR Cleaner Image")
        eks_jobs = EKS("EKS Indexed Jobs")

    clean_zone = S3("Clean Zone (Parquet)")

    with Cluster("Distributed Transform Layer"):
        emr_spark = EMR("EMR Spark Aggregations")

    curated_zone = S3("Curated Zone (Aggregates)")

    with Cluster("Analytics Serving Layer"):
        glue_catalog = GlueDataCatalog("Glue Catalog")
        athena = Athena("Athena")
        dashboard = Quicksight("QuickSight")

    analysts = Users("Analysts")

    raw_zone >> Edge(label="read partitions") >> eks_jobs
    ecr_repo >> Edge(style="dashed", label="pull image") >> eks_jobs
    eks_jobs >> Edge(label="write cleaned") >> clean_zone
    clean_zone >> emr_spark >> Edge(label="publish aggregates") >> curated_zone
    curated_zone >> glue_catalog >> athena >> dashboard
    analysts >> athena
""",
    "class-eks-partition-parallel-cleaning": """
with Diagram("Class Session - EKS Partition-Parallel Cleaning", show=False, direction="LR"):
    raw_partitions = S3("Raw Partitions")

    with Cluster("EKS Job: trip-cleaning-batch"):
        controller = EKS("Indexed Job Controller")
        workers = Fargate("Worker Pods (3 partitions)")

    cleaned = S3("Cleaned Partitions")
    logs = Cloudwatch("CloudWatch Logs")
    failed = SQS("Failed Partition Queue")

    raw_partitions >> controller >> Edge(label="schedule partitions") >> workers
    workers >> Edge(label="partition output") >> cleaned
    workers >> Edge(style="dashed", label="job logs") >> logs
    controller >> Edge(label="retry exhausted") >> failed
""",
    "class-hybrid-realtime-batch-analytics": """
with Diagram("Class Session - Hybrid Analytics", show=False, direction="LR"):
    producers = Users("Apps / Transactions")
    stream = KinesisDataStreams("Kinesis Data Streams")

    with Cluster("Real-Time Path (under 2 min alerts)"):
        stream_analytics = KinesisDataAnalytics("Streaming Analytics")
        feature_store = Dynamodb("Feature Store")
        scorer = Lambda("Fraud Scoring Service")
        alerts = SNS("Alert Topics")

    with Cluster("Batch Path (Daily Reconciliation)"):
        firehose = KinesisDataFirehose("Kinesis Firehose")
        archive = S3("Raw Event Archive")
        batch_recon = EMR("EMR Reconciliation")
        curated = S3("Curated Compliance Data")
        investigate = Athena("Athena Investigation SQL")

    producers >> stream
    stream >> stream_analytics >> feature_store >> scorer >> alerts
    stream >> firehose >> archive >> batch_recon >> curated >> investigate
""",
    "class-cross-cutting-controls": """
with Diagram("Class Session - AWS Cross-Cutting Controls", show=False, direction="TB"):
    with Cluster("Security Controls"):
        secrets = SecretsManager("Secrets Manager")
        iam = IAMRole("Least-Privilege IAM")
        kms = KMS("Encryption Keys")

    with Cluster("Core Analytics Services"):
        orchestration = EKS("Batch Orchestration")
        distributed = EMR("Distributed Compute")
        serving = Athena("SQL Serving")

    with Cluster("Observability and Governance"):
        config = Config("Config Compliance")
        logs = Cloudwatch("Metrics + Logs")
        audit = Cloudtrail("Audit Trail")

    secrets >> orchestration
    iam >> orchestration
    iam >> serving
    kms >> serving

    orchestration >> logs
    distributed >> logs
    serving >> logs

    serving >> audit
    config >> orchestration
""",
}


async def main() -> None:
    print(f"Workspace: {WORKSPACE}")
    for filename, code in DIAGRAMS.items():
        response = await generate_diagram(
            code=code,
            filename=filename,
            workspace_dir=str(WORKSPACE),
        )
        result = response.model_dump()
        print(f"{filename}: {result['status']} -> {result['path']}")
        if result["status"] != "success":
            raise RuntimeError(f"{filename} failed: {result['message']}")

    print("All class diagrams generated successfully.")


if __name__ == "__main__":
    asyncio.run(main())

