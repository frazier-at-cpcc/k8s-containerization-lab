#!/usr/bin/env python3
"""Validate that lab-provisioned AWS resources have been cleaned up."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


class AwsCliError(RuntimeError):
    pass


def run_aws(args: list[str], region: str) -> Any:
    cmd = ["aws", *args, "--region", region, "--output", "json"]
    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if proc.returncode != 0:
        raise AwsCliError(proc.stdout.strip())

    out = proc.stdout.strip()
    if not out:
        return {}
    return json.loads(out)


def is_not_found_error(err: AwsCliError) -> bool:
    text = str(err)
    markers = [
        "RepositoryNotFoundException",
        "EntityNotFoundException",
        "ResourceNotFoundException",
        "NotFoundException",
        "does not exist",
    ]
    return any(marker in text for marker in markers)


def flatten_instances(reservations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    for reservation in reservations:
        for instance in reservation.get("Instances", []):
            instances.append(instance)
    return instances


def check_no_eks_clusters(region: str) -> tuple[bool, str]:
    clusters = run_aws(["eks", "list-clusters"], region).get("clusters", [])
    if clusters:
        return False, f"EKS clusters still present: {', '.join(clusters)}"
    return True, "No EKS clusters found"


def check_no_active_emr(region: str) -> tuple[bool, str]:
    clusters = run_aws(["emr", "list-clusters", "--active"], region).get("Clusters", [])
    if clusters:
        active = ", ".join(f"{c.get('Id')}({c.get('Status', {}).get('State', 'UNKNOWN')})" for c in clusters)
        return False, f"Active EMR clusters still present: {active}"
    return True, "No active EMR clusters found"


def check_no_ec2_instances(region: str) -> tuple[bool, str]:
    reservations = run_aws(
        [
            "ec2",
            "describe-instances",
            "--filters",
            "Name=instance-state-name,Values=pending,running,stopping,stopped,shutting-down",
        ],
        region,
    ).get("Reservations", [])

    instances = flatten_instances(reservations)
    if instances:
        sample = ", ".join(
            f"{i.get('InstanceId')}:{i.get('InstanceType')}:{i.get('State', {}).get('Name')}" for i in instances[:8]
        )
        suffix = " ..." if len(instances) > 8 else ""
        return False, f"EC2 instances still present ({len(instances)}): {sample}{suffix}"
    return True, "No non-terminated EC2 instances found"


def check_ecr_repo_removed(region: str, repo: str) -> tuple[bool, str]:
    try:
        run_aws(["ecr", "describe-repositories", "--repository-names", repo], region)
        return False, f"ECR repository still present: {repo}"
    except AwsCliError as err:
        if is_not_found_error(err):
            return True, f"ECR repository not found (as expected): {repo}"
        raise


def check_glue_db_removed(region: str, db_name: str) -> tuple[bool, str]:
    try:
        run_aws(["glue", "get-database", "--name", db_name], region)
        return False, f"Glue database still present: {db_name}"
    except AwsCliError as err:
        if is_not_found_error(err):
            return True, f"Glue database not found (as expected): {db_name}"
        raise


def check_s3_prefix_empty(region: str, bucket: str, prefix: str) -> tuple[bool, str]:
    out = run_aws(
        ["s3api", "list-objects-v2", "--bucket", bucket, "--prefix", prefix, "--max-keys", "1"],
        region,
    )
    key_count = int(out.get("KeyCount", 0))
    if key_count > 0:
        key = ""
        contents = out.get("Contents") or []
        if contents:
            key = contents[0].get("Key", "")
        found = f" (e.g., {key})" if key else ""
        return False, f"S3 prefix not empty: s3://{bucket}/{prefix}{found}"
    return True, f"S3 prefix empty: s3://{bucket}/{prefix}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AWS lab cleanup state")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--ecr-repo", default="trip-cleaner", help="ECR repo expected to be removed")
    parser.add_argument("--glue-db", default="lab2_analytics", help="Glue DB expected to be removed")
    parser.add_argument(
        "--bucket",
        default=None,
        help="Optional S3 bucket name to validate cleanup prefixes",
    )
    parser.add_argument(
        "--s3-prefix",
        action="append",
        default=[],
        help=(
            "S3 prefix expected to be empty. Repeat flag to check multiple prefixes. "
            "Defaults to cleaned/, aggregated/, athena-results/ when --bucket is provided."
        ),
    )
    parser.add_argument(
        "--skip-ecr",
        action="store_true",
        help="Skip ECR repository removal check",
    )
    parser.add_argument(
        "--skip-glue",
        action="store_true",
        help="Skip Glue database removal check",
    )
    args = parser.parse_args()

    checks: list[tuple[str, bool, str]] = []

    try:
        ident = run_aws(["sts", "get-caller-identity"], args.region)
        account = ident.get("Account", "unknown")
        arn = ident.get("Arn", "unknown")
        checks.append(("auth", True, f"AWS auth OK ({account}, {arn})"))
    except AwsCliError as err:
        checks.append(("auth", False, f"AWS auth failed: {err}"))
        print_report(checks)
        return 2

    try:
        ok, msg = check_no_ec2_instances(args.region)
        checks.append(("ec2", ok, msg))

        ok, msg = check_no_eks_clusters(args.region)
        checks.append(("eks", ok, msg))

        ok, msg = check_no_active_emr(args.region)
        checks.append(("emr", ok, msg))

        if not args.skip_ecr:
            ok, msg = check_ecr_repo_removed(args.region, args.ecr_repo)
            checks.append(("ecr", ok, msg))

        if not args.skip_glue:
            ok, msg = check_glue_db_removed(args.region, args.glue_db)
            checks.append(("glue", ok, msg))

        if args.bucket:
            prefixes = args.s3_prefix or ["cleaned/", "aggregated/", "athena-results/"]
            for prefix in prefixes:
                norm_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
                ok, msg = check_s3_prefix_empty(args.region, args.bucket, norm_prefix)
                checks.append((f"s3:{norm_prefix}", ok, msg))
    except AwsCliError as err:
        checks.append(("aws-cli", False, f"AWS CLI call failed: {err}"))

    print_report(checks)
    failures = [name for name, ok, _msg in checks if not ok]
    return 1 if failures else 0


def print_report(checks: list[tuple[str, bool, str]]) -> None:
    print("AWS Cleanup Validation")
    print("=" * 24)
    for name, ok, msg in checks:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {msg}")


if __name__ == "__main__":
    raise SystemExit(main())
