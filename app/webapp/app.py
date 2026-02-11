from flask import Flask, request, jsonify
import redis
import json
import time
import os
import uuid

app = Flask(__name__)

REDIS_HOST = os.environ.get("REDIS_HOST", "redis-service")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


@app.route("/health")
def health():
    """Health check endpoint used by Kubernetes readiness and liveness probes."""
    try:
        r.ping()
        return jsonify({"status": "healthy", "redis": "connected"}), 200
    except redis.ConnectionError:
        return jsonify({"status": "unhealthy", "redis": "disconnected"}), 503


@app.route("/submit", methods=["POST"])
def submit():
    """Accept text for processing and queue it in Redis."""
    text = request.json.get("text", "")
    if not text:
        return jsonify({"error": "No text provided"}), 400

    task_id = str(uuid.uuid4())[:8]
    task = {
        "task_id": task_id,
        "text": text,
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "queued",
    }
    r.lpush("task_queue", json.dumps(task))
    r.set(f"status:{task_id}", "queued")
    return jsonify({"task_id": task_id, "status": "queued"}), 202


@app.route("/status/<task_id>")
def status(task_id):
    """Check the processing status and result for a specific task."""
    current_status = r.get(f"status:{task_id}")
    if not current_status:
        return jsonify({"error": "Task not found"}), 404

    response = {"task_id": task_id, "status": current_status}
    result = r.get(f"result:{task_id}")
    if result:
        response["result"] = json.loads(result)
    return jsonify(response)


@app.route("/stats")
def stats():
    """Return pipeline statistics: queue depth, completed tasks, serving pod."""
    queue_length = r.llen("task_queue")
    completed = len(r.keys("result:*"))
    return jsonify(
        {
            "queue_depth": queue_length,
            "completed_tasks": completed,
            "hostname": os.environ.get("HOSTNAME", "unknown"),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
