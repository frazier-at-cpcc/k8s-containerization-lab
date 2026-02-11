#!/bin/bash
# submit-tasks.sh — Submit sample text to the distributed processing pipeline
# Run from CloudShell after deploying the application.

set -euo pipefail

# Get the LoadBalancer URL
APP_URL=$(kubectl get svc webapp-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)

if [ -z "$APP_URL" ] || [ "$APP_URL" = "null" ]; then
    echo "ERROR: Could not find the webapp LoadBalancer URL."
    echo "Is the webapp deployed? Check: kubectl get svc webapp-service"
    exit 1
fi

echo "Submitting tasks to http://$APP_URL"
echo ""

# Sample texts with varied vocabulary for interesting frequency analysis
TEXTS=(
    "The architecture of distributed systems requires careful consideration of fault tolerance and data consistency. When a node fails in a distributed cluster the remaining nodes must detect the failure and redistribute the workload. Consensus algorithms like Raft and Paxos help maintain consistency across replicated state machines even when network partitions occur."
    "Container orchestration platforms like Kubernetes manage the lifecycle of containerized applications across a cluster of machines. The scheduler decides where to place each pod based on resource requests and constraints. When a node becomes unhealthy the controller manager reschedules affected pods onto healthy nodes automatically."
    "Message queues decouple producers from consumers in distributed architectures. The producer publishes messages without knowing which consumer will process them. This decoupling allows each component to scale independently and provides natural backpressure when the system is under heavy load."
    "Microservices communicate through well-defined APIs often using HTTP REST or gRPC protocols. Each service owns its data and can be deployed updated and scaled independently. Service mesh technologies like Istio add observability traffic management and security without changing application code."
    "Load balancing distributes incoming network traffic across multiple servers to ensure no single server bears too much demand. Round robin algorithms distribute requests evenly while least connections algorithms route traffic to the server handling the fewest active connections."
    "The CAP theorem states that a distributed data store can provide at most two of three guarantees: consistency availability and partition tolerance. Since network partitions are unavoidable in practice system designers must choose between consistency and availability during partition events."
    "Horizontal scaling adds more machines to a pool of resources while vertical scaling adds more power to an existing machine. Containers make horizontal scaling practical because they start in seconds compared to minutes for virtual machines. Kubernetes autoscalers can adjust replica counts based on CPU utilization or custom metrics."
    "Event driven architectures use events to trigger and communicate between decoupled services. An event represents a significant change in state such as a new order being placed or a payment being processed. Event sourcing stores the full history of state changes rather than just the current state."
    "Database replication copies data from one database server to others to improve read performance and provide redundancy. Synchronous replication waits for all replicas to confirm a write before acknowledging the client. Asynchronous replication acknowledges immediately and propagates changes later risking temporary inconsistency."
    "Observability in distributed systems requires three pillars: metrics traces and logs. Metrics provide quantitative measurements over time. Distributed traces follow a request as it moves through multiple services. Structured logs provide detailed context for specific events within individual services."
    "Infrastructure as code treats server configuration and provisioning as software that can be version controlled tested and deployed automatically. Tools like Terraform and CloudFormation describe the desired state of infrastructure and converge actual state to match. This eliminates configuration drift and makes environments reproducible."
    "Service discovery allows services to find each other without hardcoded addresses. In Kubernetes CoreDNS resolves service names to cluster IP addresses. External service discovery tools like Consul or etcd maintain a registry of available service instances and their health status."
    "Circuit breakers prevent cascading failures in distributed systems by failing fast when a downstream service is unresponsive. When failures exceed a threshold the circuit opens and subsequent requests fail immediately without attempting the call. After a timeout period the circuit enters a half open state to test if the service has recovered."
    "Rate limiting controls how many requests a client can make to a service within a given time window. Token bucket algorithms allow bursts up to a configured limit while maintaining a steady average rate. Rate limiting protects services from being overwhelmed and ensures fair access across clients."
    "Blue green deployments maintain two identical production environments. The current version runs on the blue environment while the new version is deployed to green. Once testing confirms the green environment works correctly traffic is switched from blue to green. Rolling back means switching traffic back to blue."
)

SUBMITTED=0

for text in "${TEXTS[@]}"; do
    RESPONSE=$(curl -s -X POST "http://$APP_URL/submit" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"$text\"}")

    TASK_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('task_id','???'))" 2>/dev/null || echo "???")
    SUBMITTED=$((SUBMITTED + 1))
    echo "  [$SUBMITTED/${#TEXTS[@]}] Task $TASK_ID submitted"
done

echo ""
echo "Submitted $SUBMITTED tasks."
echo ""

# Wait a moment for processing
echo "Waiting 10 seconds for workers to process..."
sleep 10

# Show stats
echo ""
echo "=== Pipeline Stats ==="
curl -s "http://$APP_URL/stats" | python3 -m json.tool
echo ""
echo "To check a specific task: curl http://$APP_URL/status/<task_id>"
