import json
import os
import threading
import time
import random
import paho.mqtt.client as mqtt
import psutil
from collections import deque

WORKER_ID = os.getenv("WORKER_ID", "worker-1")
MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
INJECTED_FAILURE_RATE = float(
    os.getenv("INJECTED_FAILURE_RATE", "0.0")
)
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))
FAILURE_WINDOW_SIZE = 20
PRIOR_FAILURES = 1
PRIOR_OBSERVATIONS = 10
worker_number = int(WORKER_ID.split("-")[-1])
random_generator = random.Random(
    RANDOM_SEED + worker_number
)
ENERGY_COST_PER_MILLION = float(
    os.getenv("ENERGY_COST_PER_MILLION", "2.0")
)
CPU_CAPACITY_MIPS = float(os.getenv("CPU_CAPACITY_MIPS", "2000"))
MEMORY_CAPACITY_MB = float(
    os.getenv("MEMORY_CAPACITY_MB", "256")
)
NETWORK_MBPS = float(os.getenv("NETWORK_MBPS", "100"))
BASE_LATENCY_MS = float(os.getenv("BASE_LATENCY_MS", "10"))

QUEUE_LIMIT = int(os.getenv("QUEUE_LIMIT", "10"))

TASK_TOPIC = f"research/tasks/{WORKER_ID}"
RESULT_TOPIC = "research/results"
STATUS_TOPIC = "research/workers/status"

state_lock = threading.Lock()

worker_state = {
    "status": "available",
    "current_queue": 0,
    "remaining_energy": 100.0,
    "completed_tasks": 0,
    "failed_tasks": 0,
    "outcome_history": deque(maxlen=FAILURE_WINDOW_SIZE),
}


def perform_cpu_work(iterations):
    result = 0

    for number in range(iterations):
        result += (number * number) % 97

    return result


def model_energy_cost(iterations):
    """Software energy model; this is not physical energy measurement."""
    return round(
    (iterations / 1_000_000) 
    * ENERGY_COST_PER_MILLION,
    3,
)


def create_status_message():

    memory = psutil.virtual_memory()

    with state_lock:
        completed = worker_state["completed_tasks"]
        failed = worker_state["failed_tasks"]
        outcomes = worker_state["outcome_history"]
        window_attempts = len(outcomes)
        window_failures = sum(outcomes)

        estimated_failure_probability = (
            window_failures + PRIOR_FAILURES
        ) / (
            window_attempts + PRIOR_OBSERVATIONS
        )

        return {
            "energy_cost_per_million": ENERGY_COST_PER_MILLION,
            "worker_id": WORKER_ID,
            "status": worker_state["status"],
            "cpu_percent_measured": psutil.cpu_percent(),
            "memory_percent_measured": memory.percent,
            "memory_mb": MEMORY_CAPACITY_MB,
            "cpu_capacity_mips": CPU_CAPACITY_MIPS,
            "network_mbps": NETWORK_MBPS,
            "base_latency_ms": BASE_LATENCY_MS,
                        "estimated_failure_probability": round(
                estimated_failure_probability,
                4,
            ),
            "failure_estimation_method": "rolling_observed_outcomes",
            "failure_window_size": FAILURE_WINDOW_SIZE,
            "window_attempts": window_attempts,
            "window_failures": window_failures,
            "remaining_energy": round(
                worker_state["remaining_energy"],
                3,
            ),
            "energy_value_type": "modelled",
            "current_queue": worker_state["current_queue"],
            "queue_limit": QUEUE_LIMIT,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "timestamp": time.time(),
        }


def publish_status(client):
    client.publish(
        STATUS_TOPIC,
        json.dumps(create_status_message()),
        qos=1,
        retain=True,
    )


def status_loop(client):
    while True:
        publish_status(client)
        time.sleep(2)


def on_connect(client, userdata, flags, reason_code, properties):
    print(
        f"{WORKER_ID} connected to MQTT: {reason_code}",
        flush=True,
    )

    client.subscribe(TASK_TOPIC, qos=1)
    publish_status(client)

    print(
        f"{WORKER_ID} subscribed to {TASK_TOPIC}",
        flush=True,
    )


def on_message(client, userdata, message):
    received_time = time.time()
    try:
        task = json.loads(message.payload.decode("utf-8"))
        task_id = task["task_id"]
        iterations = int(task.get("iterations", 1_000_000))
        if random_generator.random() < INJECTED_FAILURE_RATE:
            raise RuntimeError(
                f"Seeded injected failure at rate "
                f"{INJECTED_FAILURE_RATE}"
            )

        with state_lock:
            worker_state["status"] = "busy"
            worker_state["current_queue"] = 1

        publish_status(client)

        start_time = time.perf_counter()
        calculation_result = perform_cpu_work(iterations)
        execution_time_ms = (
            time.perf_counter() - start_time
        ) * 1000

        energy_cost = model_energy_cost(iterations)

        with state_lock:
            worker_state["completed_tasks"] += 1
            worker_state["outcome_history"].append(0)
            worker_state["remaining_energy"] = max(
                0.0,
                worker_state["remaining_energy"] - energy_cost,
            )
            worker_state["status"] = "available"
            worker_state["current_queue"] = 0

        result_message = {
            "task_id": task_id,
            "worker_id": WORKER_ID,
            "status": "completed",
            "iterations": iterations,
            "execution_time_ms": round(
                execution_time_ms,
                3,
            ),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "energy_cost_modelled": energy_cost,
            "received_timestamp": received_time,
            "completed_timestamp": time.time(),
            "calculation_result": calculation_result,
        }

        client.publish(
            RESULT_TOPIC,
            json.dumps(result_message),
            qos=1,
        )

        publish_status(client)

        print(
            f"Completed task {task_id} in "
            f"{execution_time_ms:.3f} ms",
            flush=True,
        )

    except Exception as error:
        with state_lock:
            worker_state["failed_tasks"] += 1
            worker_state["outcome_history"].append(1)
            worker_state["status"] = "available"
            worker_state["current_queue"] = 0

        publish_status(client)

        print(
            f"Task processing failed: {error}",
            flush=True,
        )


client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id=WORKER_ID,
)

client.on_connect = on_connect
client.on_message = on_message

print(f"Starting {WORKER_ID}", flush=True)

client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()

threading.Thread(
    target=status_loop,
    args=(client,),
    daemon=True,
).start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    client.disconnect()
    client.loop_stop()