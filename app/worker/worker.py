import redis
import json
import time
import os
import re
from collections import Counter

REDIS_HOST = os.environ.get("REDIS_HOST", "redis-service")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
WORKER_ID = os.environ.get("HOSTNAME", "unknown-worker")

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def process_text(text):
    """Compute word frequency analysis on the given text."""
    words = re.findall(r"[a-z]+", text.lower())
    freq = Counter(words)
    # Simulate variable processing time for realism
    time.sleep(2)
    return {
        "total_words": len(words),
        "unique_words": len(freq),
        "top_20": dict(freq.most_common(20)),
    }


def run():
    print(f"Worker {WORKER_ID} starting. Waiting for tasks...")

    while True:
        # BRPOP blocks until a message is available (or timeout).
        # This is the Redis equivalent of SQS long polling.
        result = r.brpop("task_queue", timeout=5)
        if result is None:
            continue

        _, raw_task = result
        task = json.loads(raw_task)
        task_id = task["task_id"]

        print(f"[{WORKER_ID}] Processing task {task_id}...")
        r.set(f"status:{task_id}", "processing")

        try:
            analysis = process_text(task["text"])
            analysis["worker_id"] = WORKER_ID
            analysis["completed_at"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            )

            r.set(f"result:{task_id}", json.dumps(analysis))
            r.set(f"status:{task_id}", "completed")
            r.incr(f"worker_tasks:{WORKER_ID}")

            print(
                f"[{WORKER_ID}] Task {task_id} done. "
                f"{analysis['total_words']} words processed."
            )
        except Exception as e:
            print(f"[{WORKER_ID}] Error on task {task_id}: {e}")
            r.set(f"status:{task_id}", "failed")
            # Re-queue failed tasks for retry
            r.lpush("task_queue", raw_task)


if __name__ == "__main__":
    run()
