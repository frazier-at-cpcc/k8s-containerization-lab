# Containerization and Kubernetes Lab — AWS Learner Lab

A hands-on lab where students containerize a distributed text-processing pipeline and deploy it to Amazon EKS. Students build Docker images, push them to Amazon ECR, and use Kubernetes to orchestrate a multi-service application with automatic scaling and self-healing.

## Repository Structure

```
├── lab-guide.md              # Full lab instructions
├── scripts/
│   ├── setup-tools.sh        # Install kubectl and eksctl in CloudShell
│   ├── create-cluster.sh     # Create EKS cluster and managed node group
│   ├── create-ecr-repos.sh   # Create ECR repositories
│   ├── build-and-push.sh     # Build Docker images and push to ECR
│   ├── submit-tasks.sh       # Submit sample text to the running pipeline
│   └── teardown.sh           # Delete all AWS resources
├── app/
│   ├── webapp/               # Flask web API (producer)
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── worker/               # Background worker (consumer)
│       ├── worker.py
│       ├── requirements.txt
│       └── Dockerfile
└── k8s/
    ├── redis.yaml            # Redis deployment + service + PVC
    ├── webapp.yaml           # Web app deployment + service (LoadBalancer)
    └── worker.yaml           # Worker deployment
```

## Prerequisites

- AWS Academy Learner Lab access
- Basic Linux command line familiarity
- Introductory Python knowledge
- AWS Console navigation

## Session Structure

The lab is designed with natural stopping points. Students do not need to complete it in one sitting.

**Session A (~90 minutes):** Infrastructure setup and containerization — create the EKS cluster, build Docker images, push to ECR.

**Session B (~90 minutes):** Kubernetes deployment and experiments — deploy the application, run the pipeline, perform failure and scaling experiments.

Students can stop after Session A and resume later. The EKS cluster, ECR images, and node group persist between Learner Lab sessions. When resuming, students only need to open CloudShell and verify their cluster is running.

## Estimated Cost

- EKS control plane: ~$0.40 per 4-hour session ($0.10/hr)
- Two t3.small nodes: ~$0.17 per 4-hour session
- ECR storage: negligible
- Temporary EC2 build instance: ~$0.04
- **Total per session: ~$0.60–0.80**

Delete the cluster when not in use to preserve budget. The teardown script handles this.

## Quick Start (Instructor)

1. Ensure students have Learner Lab access with remaining budget
2. Verify the `LabEksClusterRole` IAM role exists in the lab environment (it should be pre-provisioned)
3. Distribute this repository to students (GitHub, zip file, or S3)
4. Students follow `lab-guide.md` from top to bottom
