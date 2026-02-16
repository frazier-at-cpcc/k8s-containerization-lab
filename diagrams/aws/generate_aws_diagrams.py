#!/usr/bin/env python3
"""Generate AWS architecture diagrams for the DSBA 6190 lesson."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.analytics import (
    Athena,
    EMR,
    GlueDataCatalog,
    KinesisDataAnalytics,
    KinesisDataFirehose,
    KinesisDataStreams,
    Quicksight,
)
from diagrams.aws.compute import ECR, EKS, Fargate, Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.general import Users
from diagrams.aws.integration import SNS, SQS
from diagrams.aws.management import Cloudtrail, Cloudwatch, Config
from diagrams.aws.security import IAMRole, KMS, SecretsManager
from diagrams.aws.storage import S3


OUT_DIR = Path(__file__).resolve().parent

GRAPH_ATTR = {
    "fontsize": "20",
    "pad": "0.6",
    "nodesep": "0.85",
    "ranksep": "0.95",
    "splines": "spline",
    "concentrate": "false",
    "labelloc": "t",
    "labeljust": "c",
    "fontname": "Helvetica",
    "dpi": "160",
}

NODE_ATTR = {
    "fontsize": "12",
    "fontname": "Helvetica",
}

EDGE_ATTR = {
    "fontsize": "11",
    "fontname": "Helvetica",
    "color": "#6f7d8c",
    "penwidth": "1.3",
}


def ensure_graphviz() -> None:
    """Ensure Graphviz is available for rendering diagrams."""
    if shutil.which("dot"):
        return

    # Common Homebrew path on macOS.
    if Path("/opt/homebrew/bin/dot").exists():
        os.environ["PATH"] = f"/opt/homebrew/bin:{os.environ.get('PATH', '')}"

    if not shutil.which("dot"):
        raise RuntimeError("Graphviz 'dot' was not found in PATH.")


def diagram_batch_analytics_platform() -> None:
    with Diagram(
        "AWS Batch Analytics Platform",
        filename=str(OUT_DIR / "aws-batch-analytics-platform"),
        show=False,
        outformat="png",
        direction="LR",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    ):
        analysts = Users("Analysts")

        raw_zone = S3("Raw Zone (CSV)")
        clean_zone = S3("Clean Zone (Parquet)")
        curated_zone = S3("Curated Zone (Aggregates)")

        with Cluster("Containerized Cleaning"):
            ecr_repo = ECR("ECR Cleaner Image")
            eks_jobs = EKS("EKS Indexed Batch Jobs")

        with Cluster("Distributed Transform Layer"):
            emr_spark = EMR("EMR Spark Aggregations")

        with Cluster("Analytics Serving Layer"):
            glue_catalog = GlueDataCatalog("Glue Data Catalog")
            athena = Athena("Athena")
            dashboard = Quicksight("QuickSight")

        raw_zone >> Edge(style="invis") >> ecr_repo
        ecr_repo >> Edge(style="dashed", label="pull image") >> eks_jobs
        raw_zone >> Edge(label="read partitions") >> eks_jobs
        eks_jobs >> Edge(label="write cleaned") >> clean_zone
        clean_zone >> emr_spark >> Edge(label="publish aggregates") >> curated_zone
        curated_zone >> glue_catalog >> athena >> dashboard
        analysts >> athena


def diagram_partition_parallel_cleaning() -> None:
    with Diagram(
        "AWS Partition-Parallel Cleaning on EKS",
        filename=str(OUT_DIR / "aws-partition-parallel-cleaning"),
        show=False,
        outformat="png",
        direction="LR",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    ):
        raw_partitions = S3("Raw Partitions (month=01/02/03)")
        cleaned_partitions = S3("Cleaned Partitions")
        logs = Cloudwatch("CloudWatch Logs")
        failures = SQS("Failed Partition Queue")

        with Cluster("EKS Job: trip-cleaning-batch"):
            job_controller = EKS("Indexed Job Controller")
            pod_pool = Fargate("Worker Pods (3 partitions)")

        raw_partitions >> job_controller
        job_controller >> Edge(label="schedule partitions") >> pod_pool
        pod_pool >> Edge(label="partition output") >> cleaned_partitions
        pod_pool >> Edge(style="dashed", label="job logs") >> logs
        job_controller >> Edge(label="retry exhausted") >> failures


def diagram_hybrid_realtime_analytics() -> None:
    with Diagram(
        "AWS Hybrid Analytics (Real-Time + Batch)",
        filename=str(OUT_DIR / "aws-hybrid-realtime-analytics"),
        show=False,
        outformat="png",
        direction="LR",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    ):
        producers = Users("Apps / Transactions")
        stream = KinesisDataStreams("Kinesis Data Streams")

        with Cluster("Real-Time Path (<2 min alerts)"):
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

        stream >> Edge(label="fan-out archive") >> firehose >> archive
        archive >> batch_recon >> curated >> investigate


def diagram_cross_cutting_controls() -> None:
    with Diagram(
        "AWS Analytics Platform Cross-Cutting Controls",
        filename=str(OUT_DIR / "aws-cross-cutting-controls"),
        show=False,
        outformat="png",
        direction="TB",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    ):
        with Cluster("Core Analytics Services"):
            orchestration = EKS("Batch Orchestration")
            distributed = EMR("Distributed Compute")
            serving = Athena("SQL Serving")

        with Cluster("Security Controls"):
            iam = IAMRole("Least-Privilege IAM")
            kms = KMS("Encryption Keys")
            secrets = SecretsManager("Secrets Manager")

        with Cluster("Observability and Governance"):
            logs = Cloudwatch("Metrics + Logs")
            audit = Cloudtrail("Audit Trail")
            config = Config("Config Compliance")

        iam >> orchestration
        iam >> serving
        kms >> serving
        secrets >> orchestration

        orchestration >> logs
        distributed >> logs
        serving >> logs

        serving >> audit

        config >> orchestration


def main() -> None:
    ensure_graphviz()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    diagram_batch_analytics_platform()
    diagram_partition_parallel_cleaning()
    diagram_hybrid_realtime_analytics()
    diagram_cross_cutting_controls()

    print("Generated diagrams:")
    for png in sorted(OUT_DIR.glob("*.png")):
        print(f"- {png}")


if __name__ == "__main__":
    main()
