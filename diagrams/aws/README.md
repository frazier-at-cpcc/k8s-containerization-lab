# AWS Lesson Diagrams

This folder contains AWS architecture diagrams for the application-centered lesson on containerization and distributed computing for data analytics.

## Files

- `generate_aws_diagrams.py`: Python generator using the `diagrams` library.
- `generate_class_diagrams_with_mcp.py`: Class-session diagrams generated through the AWS Diagram MCP package.
- `aws-batch-analytics-platform.png`: End-to-end batch analytics architecture.
- `aws-partition-parallel-cleaning.png`: EKS indexed job partition processing pattern.
- `aws-hybrid-realtime-analytics.png`: Hybrid real-time and batch analytics pattern.
- `aws-cross-cutting-controls.png`: Security, observability, and governance overlays.
- `generated-diagrams/`: Output folder for MCP-generated class-session diagrams.

## Generate / Refresh

```bash
python3 diagrams/aws/generate_aws_diagrams.py
```

## Generate Class Session Diagrams via MCP Server

```bash
uvx --from awslabs.aws-diagram-mcp-server@latest \
  python diagrams/aws/generate_class_diagrams_with_mcp.py
```
