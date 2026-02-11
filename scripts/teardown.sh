#!/bin/bash
# teardown.sh — Delete all AWS resources created by this lab
# Run from CloudShell. Deletes in dependency order to avoid errors.

set -uo pipefail

CLUSTER_NAME="distlab"
NODE_GROUP_NAME="distlab-nodes"
REGION="us-east-1"

echo "============================================"
echo "  Lab Teardown"
echo "============================================"
echo ""
echo "This will delete:"
echo "  - All Kubernetes deployments and services"
echo "  - The EKS node group ($NODE_GROUP_NAME)"
echo "  - The EKS cluster ($CLUSTER_NAME)"
echo "  - ECR repositories (distlab-webapp, distlab-worker)"
echo ""
read -p "Continue? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""

# -----------------------------------------------
# Step 1: Delete Kubernetes resources
# -----------------------------------------------
echo "=== Step 1: Deleting Kubernetes resources ==="

# Delete services first — LoadBalancer services provision ELBs that
# need to be cleaned up before we delete the cluster.
if kubectl get svc webapp-service &>/dev/null 2>&1; then
    echo "  Deleting services (triggers ELB cleanup)..."
    kubectl delete svc webapp-service --ignore-not-found=true 2>/dev/null || true
    # Give AWS time to start deleting the ELB
    echo "  Waiting 30s for ELB deletion to initiate..."
    sleep 30
fi

# Delete all application resources
for manifest in k8s/worker.yaml k8s/webapp.yaml k8s/redis.yaml; do
    if [ -f "$manifest" ]; then
        echo "  Deleting resources from $manifest..."
        kubectl delete -f "$manifest" --ignore-not-found=true 2>/dev/null || true
    fi
done

# Delete PVCs (which delete underlying EBS volumes)
echo "  Deleting PersistentVolumeClaims..."
kubectl delete pvc --all --ignore-not-found=true 2>/dev/null || true

echo "  Kubernetes resources deleted."
echo ""

# -----------------------------------------------
# Step 2: Delete the node group
# -----------------------------------------------
echo "=== Step 2: Deleting node group ==="

NG_EXISTS=$(aws eks describe-nodegroup --cluster-name "$CLUSTER_NAME" --nodegroup-name "$NODE_GROUP_NAME" --region "$REGION" 2>/dev/null && echo "yes" || echo "no")

if [ "$NG_EXISTS" = "yes" ]; then
    aws eks delete-nodegroup \
        --cluster-name "$CLUSTER_NAME" \
        --nodegroup-name "$NODE_GROUP_NAME" \
        --region "$REGION" \
        --output text
    echo "  Node group deletion initiated. Waiting (this takes 3-5 minutes)..."
    aws eks wait nodegroup-deleted \
        --cluster-name "$CLUSTER_NAME" \
        --nodegroup-name "$NODE_GROUP_NAME" \
        --region "$REGION"
    echo "  Node group deleted."
else
    echo "  Node group not found, skipping."
fi
echo ""

# -----------------------------------------------
# Step 3: Delete the EKS cluster
# -----------------------------------------------
echo "=== Step 3: Deleting EKS cluster ==="

CLUSTER_EXISTS=$(aws eks describe-cluster --name "$CLUSTER_NAME" --region "$REGION" 2>/dev/null && echo "yes" || echo "no")

if [ "$CLUSTER_EXISTS" = "yes" ]; then
    aws eks delete-cluster --name "$CLUSTER_NAME" --region "$REGION" --output text
    echo "  Cluster deletion initiated. Waiting (this takes 5-10 minutes)..."
    aws eks wait cluster-deleted --name "$CLUSTER_NAME" --region "$REGION"
    echo "  Cluster deleted."
else
    echo "  Cluster not found, skipping."
fi
echo ""

# -----------------------------------------------
# Step 4: Delete ECR repositories
# -----------------------------------------------
echo "=== Step 4: Deleting ECR repositories ==="

for repo in distlab-webapp distlab-worker; do
    if aws ecr describe-repositories --repository-names "$repo" --region "$REGION" &>/dev/null; then
        aws ecr delete-repository --repository-name "$repo" --force --region "$REGION" --output text --query 'repository.repositoryName'
        echo "  Deleted $repo"
    else
        echo "  $repo not found, skipping."
    fi
done
echo ""

# -----------------------------------------------
# Step 5: Clean up kubeconfig
# -----------------------------------------------
echo "=== Step 5: Cleaning up kubeconfig ==="
kubectl config delete-context "arn:aws:eks:${REGION}:$(aws sts get-caller-identity --query Account --output text):cluster/${CLUSTER_NAME}" 2>/dev/null || true
kubectl config delete-cluster "arn:aws:eks:${REGION}:$(aws sts get-caller-identity --query Account --output text):cluster/${CLUSTER_NAME}" 2>/dev/null || true
echo "  Kubeconfig entries removed."
echo ""

echo "============================================"
echo "  Teardown complete."
echo ""
echo "  Remaining manual checks:"
echo "  - EC2 console: verify the build instance is terminated"
echo "  - ELB console: verify no orphaned load balancers"
echo "  - EBS console: verify no orphaned volumes"
echo "============================================"
