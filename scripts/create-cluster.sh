#!/bin/bash
# create-cluster.sh — Create an EKS cluster and managed node group
# Run this from CloudShell, which has console-level AWS credentials.

set -euo pipefail

CLUSTER_NAME="distlab"
REGION="us-east-1"
NODE_GROUP_NAME="distlab-nodes"
NODE_INSTANCE_TYPE="t3.small"
NODE_COUNT=2
K8S_VERSION="1.31"

echo "============================================"
echo "  EKS Cluster Setup for Learner Lab"
echo "============================================"
echo ""

# -----------------------------------------------
# Step 1: Discover the EKS IAM roles
# -----------------------------------------------
echo "=== Step 1: Finding EKS IAM roles ==="

# The Learner Lab pre-creates EKS roles. Find them.
ALL_ROLES=$(aws iam list-roles --query 'Roles[*].[RoleName,Arn]' --output text 2>/dev/null)

# Look for roles with "Eks" or "EKS" in the name
EKS_ROLES=$(echo "$ALL_ROLES" | grep -i "eks" || true)

if [ -z "$EKS_ROLES" ]; then
    echo "ERROR: No IAM roles containing 'Eks' found in this account."
    echo ""
    echo "The Learner Lab should pre-provision EKS roles. Available roles:"
    echo "$ALL_ROLES" | awk '{print "  " $1}'
    echo ""
    echo "Look for a role that might be usable for EKS and update this script."
    exit 1
fi

echo "Found EKS-related roles:"
echo "$EKS_ROLES" | while read -r name arn; do
    echo "  $name"
done
echo ""

# Try to identify the cluster role (needs eks.amazonaws.com trust)
# and the node role (needs ec2.amazonaws.com trust).
# In Learner Lab, these may be the same role.
CLUSTER_ROLE_ARN=""
NODE_ROLE_ARN=""

while read -r name arn; do
    TRUST=$(aws iam get-role --role-name "$name" --query 'Role.AssumeRolePolicyDocument.Statement[*].Principal.Service' --output text 2>/dev/null || echo "")

    if echo "$TRUST" | grep -q "eks.amazonaws.com"; then
        if [ -z "$CLUSTER_ROLE_ARN" ]; then
            CLUSTER_ROLE_ARN="$arn"
            echo "Cluster role: $name"
        fi
    fi

    if echo "$TRUST" | grep -q "ec2.amazonaws.com"; then
        if [ -z "$NODE_ROLE_ARN" ]; then
            NODE_ROLE_ARN="$arn"
            echo "Node role:    $name"
        fi
    fi

    # If the role trusts both services, use it for both
    if echo "$TRUST" | grep -q "eks.amazonaws.com" && echo "$TRUST" | grep -q "ec2.amazonaws.com"; then
        CLUSTER_ROLE_ARN="$arn"
        NODE_ROLE_ARN="$arn"
        echo "(Role $name trusts both eks and ec2 — using for both)"
    fi
done <<< "$EKS_ROLES"

# Fallback: if we didn't find specific trust relationships, use the first EKS role for both
if [ -z "$CLUSTER_ROLE_ARN" ]; then
    CLUSTER_ROLE_ARN=$(echo "$EKS_ROLES" | head -1 | awk '{print $2}')
    echo "Warning: Could not determine cluster role by trust policy. Using: $(echo "$EKS_ROLES" | head -1 | awk '{print $1}')"
fi
if [ -z "$NODE_ROLE_ARN" ]; then
    NODE_ROLE_ARN="$CLUSTER_ROLE_ARN"
    echo "Warning: Could not determine node role. Using same as cluster role."
fi

echo ""
echo "Cluster role ARN: $CLUSTER_ROLE_ARN"
echo "Node role ARN:    $NODE_ROLE_ARN"
echo ""

# -----------------------------------------------
# Step 2: Discover VPC and subnets
# -----------------------------------------------
echo "=== Step 2: Discovering VPC configuration ==="

VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=is-default,Values=true" \
    --query "Vpcs[0].VpcId" \
    --output text \
    --region "$REGION")

if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
    echo "ERROR: No default VPC found in $REGION."
    exit 1
fi
echo "Default VPC: $VPC_ID"

# Get subnets in at least 2 different AZs (EKS requirement)
SUBNET_INFO=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=default-for-az,Values=true" \
    --query "Subnets[*].[SubnetId,AvailabilityZone]" \
    --output text \
    --region "$REGION")

SUBNET_IDS=$(echo "$SUBNET_INFO" | awk '{print $1}' | head -3)
SUBNET_COUNT=$(echo "$SUBNET_IDS" | wc -l)

if [ "$SUBNET_COUNT" -lt 2 ]; then
    echo "ERROR: Need at least 2 subnets in different AZs. Found $SUBNET_COUNT."
    exit 1
fi

echo "Using subnets:"
echo "$SUBNET_INFO" | head -3 | while read -r sid az; do
    echo "  $sid ($az)"
done

# Comma-separated for the API call
SUBNET_CSV=$(echo "$SUBNET_IDS" | tr '\n' ',' | sed 's/,$//')

# Get default security group
DEFAULT_SG=$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=default" \
    --query "SecurityGroups[0].GroupId" \
    --output text \
    --region "$REGION")

echo "Security group: $DEFAULT_SG"
echo ""

# -----------------------------------------------
# Step 3: Check if cluster already exists
# -----------------------------------------------
echo "=== Step 3: Checking for existing cluster ==="

EXISTING=$(aws eks describe-cluster --name "$CLUSTER_NAME" --region "$REGION" 2>/dev/null && echo "yes" || echo "no")

if [ "$EXISTING" = "yes" ]; then
    CLUSTER_STATUS=$(aws eks describe-cluster --name "$CLUSTER_NAME" --query 'cluster.status' --output text --region "$REGION")
    echo "Cluster '$CLUSTER_NAME' already exists (status: $CLUSTER_STATUS)."

    if [ "$CLUSTER_STATUS" = "ACTIVE" ]; then
        echo "Skipping cluster creation. Checking node group..."
    else
        echo "Cluster is in state $CLUSTER_STATUS. Waiting for it to become ACTIVE..."
        aws eks wait cluster-active --name "$CLUSTER_NAME" --region "$REGION"
    fi
else
    # -----------------------------------------------
    # Step 4: Create the cluster
    # -----------------------------------------------
    echo "=== Step 4: Creating EKS cluster ==="
    echo "This takes 12-18 minutes. Continue with the next lab section while you wait."
    echo ""

    aws eks create-cluster \
        --name "$CLUSTER_NAME" \
        --region "$REGION" \
        --kubernetes-version "$K8S_VERSION" \
        --role-arn "$CLUSTER_ROLE_ARN" \
        --resources-vpc-config "subnetIds=$SUBNET_CSV,securityGroupIds=$DEFAULT_SG" \
        --output text \
        --query 'cluster.status'

    echo ""
    echo "Cluster creation initiated. Waiting for ACTIVE status..."
    echo "(You can open a new CloudShell tab and continue with lab step A3)"
    echo ""

    aws eks wait cluster-active --name "$CLUSTER_NAME" --region "$REGION"
    echo "Cluster is ACTIVE."
fi

echo ""

# -----------------------------------------------
# Step 5: Create the node group (if it doesn't exist)
# -----------------------------------------------
echo "=== Step 5: Creating managed node group ==="

EXISTING_NG=$(aws eks describe-nodegroup --cluster-name "$CLUSTER_NAME" --nodegroup-name "$NODE_GROUP_NAME" --region "$REGION" 2>/dev/null && echo "yes" || echo "no")

if [ "$EXISTING_NG" = "yes" ]; then
    NG_STATUS=$(aws eks describe-nodegroup --cluster-name "$CLUSTER_NAME" --nodegroup-name "$NODE_GROUP_NAME" --query 'nodegroup.status' --output text --region "$REGION")
    echo "Node group '$NODE_GROUP_NAME' already exists (status: $NG_STATUS)."
else
    # Convert space-separated subnet list to space-separated (for --subnets)
    SUBNET_ARGS=$(echo "$SUBNET_IDS" | tr '\n' ' ')

    aws eks create-nodegroup \
        --cluster-name "$CLUSTER_NAME" \
        --nodegroup-name "$NODE_GROUP_NAME" \
        --node-role "$NODE_ROLE_ARN" \
        --subnets $SUBNET_ARGS \
        --instance-types "$NODE_INSTANCE_TYPE" \
        --scaling-config "minSize=$NODE_COUNT,maxSize=4,desiredSize=$NODE_COUNT" \
        --ami-type AL2023_x86_64_STANDARD \
        --region "$REGION" \
        --output text \
        --query 'nodegroup.status'

    echo "Node group creation initiated. Waiting for ACTIVE status..."
    echo "(This takes 3-5 minutes)"
    echo ""

    aws eks wait nodegroup-active \
        --cluster-name "$CLUSTER_NAME" \
        --nodegroup-name "$NODE_GROUP_NAME" \
        --region "$REGION"

    echo "Node group is ACTIVE."
fi

echo ""

# -----------------------------------------------
# Step 6: Configure kubectl
# -----------------------------------------------
echo "=== Step 6: Configuring kubectl ==="

aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$REGION"

echo ""
echo "=== Verification ==="
echo ""
kubectl get nodes
echo ""
echo "============================================"
echo "  Cluster setup complete!"
echo "  Cluster: $CLUSTER_NAME"
echo "  Nodes:   $NODE_COUNT x $NODE_INSTANCE_TYPE"
echo "  Region:  $REGION"
echo "============================================"
