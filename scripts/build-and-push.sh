#!/bin/bash
# build-and-push.sh — Build Docker images and push to Amazon ECR
# Run this on the EC2 build instance (which has Docker installed).

set -euo pipefail

REGION="us-east-1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  Build and Push Container Images"
echo "============================================"
echo ""

# -----------------------------------------------
# Step 1: Get account info and authenticate to ECR
# -----------------------------------------------
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_BASE="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

echo "Account:  $ACCOUNT_ID"
echo "ECR base: $ECR_BASE"
echo ""

# -----------------------------------------------
# Step 2: Create ECR repositories (idempotent)
# -----------------------------------------------
echo "=== Creating ECR repositories ==="

for repo in distlab-webapp distlab-worker; do
    if aws ecr describe-repositories --repository-names "$repo" --region "$REGION" &>/dev/null; then
        echo "  $repo already exists"
    else
        aws ecr create-repository --repository-name "$repo" --region "$REGION" --output text --query 'repository.repositoryUri'
        echo "  Created $repo"
    fi
done
echo ""

# -----------------------------------------------
# Step 3: Authenticate Docker to ECR
# -----------------------------------------------
echo "=== Authenticating Docker to ECR ==="
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_BASE"
echo ""

# -----------------------------------------------
# Step 4: Build images
# -----------------------------------------------
echo "=== Building webapp image ==="
docker build -t distlab-webapp:v1 "$REPO_ROOT/app/webapp/"
echo ""

echo "=== Building worker image ==="
docker build -t distlab-worker:v1 "$REPO_ROOT/app/worker/"
echo ""

# -----------------------------------------------
# Step 5: Tag and push
# -----------------------------------------------
echo "=== Tagging and pushing images ==="

docker tag distlab-webapp:v1 "$ECR_BASE/distlab-webapp:v1"
docker tag distlab-worker:v1 "$ECR_BASE/distlab-worker:v1"

echo "Pushing distlab-webapp:v1..."
docker push "$ECR_BASE/distlab-webapp:v1"
echo ""

echo "Pushing distlab-worker:v1..."
docker push "$ECR_BASE/distlab-worker:v1"
echo ""

# -----------------------------------------------
# Summary
# -----------------------------------------------
echo "============================================"
echo "  Images pushed successfully!"
echo ""
echo "  Webapp: $ECR_BASE/distlab-webapp:v1"
echo "  Worker: $ECR_BASE/distlab-worker:v1"
echo ""
echo "  Use these URIs in your Kubernetes manifests."
echo "============================================"
