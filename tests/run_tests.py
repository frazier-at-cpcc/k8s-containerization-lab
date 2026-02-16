#!/usr/bin/env python3
"""Convenience runner for lab validation test suite."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Keep this process from writing bytecode while orchestrating test discovery/runs.
sys.dont_write_bytecode = True

from _artifact_cleanup import cleanup_python_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lab validation test suite")
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Include optional Docker integration smoke test",
    )
    parser.add_argument(
        "--aws",
        action="store_true",
        help="Include optional live AWS Learner Lab checks",
    )
    parser.add_argument(
        "--aws-stage",
        type=int,
        default=None,
        help="Lab stage completed (1-4) for stage-aware AWS checks",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default=None,
        help="S3 bucket name for stage artifact checks (maps to LAB_BUCKET)",
    )
    parser.add_argument(
        "--eks-cluster",
        type=str,
        default=None,
        help="Optional EKS cluster name to validate role constraints",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    # Keep test runs clean by not writing __pycache__/pyc artifacts.
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    if args.docker:
        env["LAB_RUN_DOCKER"] = "1"

    if args.aws:
        env["LAB_RUN_AWS"] = "1"

    if args.aws_stage is not None:
        env["LAB_STAGE"] = str(args.aws_stage)

    if args.bucket:
        env["LAB_BUCKET"] = args.bucket

    if args.eks_cluster:
        env["LAB_EKS_CLUSTER_NAME"] = args.eks_cluster

    cmd = [
        sys.executable,
        "-B",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py",
        "-v",
    ]
    try:
        result = subprocess.run(cmd, cwd=root, env=env)
        return result.returncode
    finally:
        cleanup_python_artifacts(root)


if __name__ == "__main__":
    raise SystemExit(main())
