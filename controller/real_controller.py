import csv
import json
import os
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt


MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

RESULT_TOPIC = "research/results"
OUTPUT_FILE = Path(
    os.getenv(
        "CONTROLLER_RESULTS_FILE",
        "/app/data/controller_results.csv",
    )
)

TASKS = [
    {
        "task_id": "controller-task-001",
        "worker_id": "worker-1",
        "iterations": 1_000_000,
    },
    {
        "task_id": "controller-task-002",
        "worker_id": "worker-2",
        "iterations": 1_500_000,
    },
    {
        "task_id": "controller-task-003",
        "worker_id": "worker-3",
        "iterations": 2_000_000,
    },
]

dispatch_times = {}
received_results = {}
connected_event = threading.Event()
results_complete_event = threading.Event()


def save_result(result):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    file_exists = OUTPUT_FILE.exists()

    fields = [
        "task_id",
        "worker_id",
        "status",
        "iterations",
        "worker_execution_time_ms",
        "end_to_end_latency_ms",
        "cpu_percent",
        "memory_percent",
        "completed_timestamp",
    ]

    with OUTPUT_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)

        if not file_exists:
            writer.writeheader()

        writer.writerow(result)


def on_connect(client, userdata, flags, reason_code, properties):
    print(
        f"Controller connected to MQTT: {reason_code}",
        flush=True,
    )

    client.subscribe(RESULT_TOPIC)
    connected_event.set()


def on_message(client, userdata, message):
    try:
        worker_result = json.loads(
            message.payload.decode("utf-8")
        )

        task_id = worker_result["task_id"]

        if task_id not in dispatch_times:
            return

        if task_id in received_results:
            print(
                f"Ignoring duplicate result for {task_id}",
                flush=True,
            )
            return

        end_to_end_latency_ms = (
            time.perf_counter() - dispatch_times[task_id]
        ) * 1000

        controller_result = {
            "task_id": task_id,
            "worker_id": worker_result["worker_id"],
            "status": worker_result["status"],
            "iterations": worker_result["iterations"],
            "worker_execution_time_ms": worker_result[
                "execution_time_ms"
            ],
            "end_to_end_latency_ms": round(
                end_to_end_latency_ms,
                3,
            ),
            "cpu_percent": worker_result["cpu_percent"],
            "memory_percent": worker_result[
                "memory_percent"
            ],
            "completed_timestamp": worker_result[
                "completed_timestamp"
            ],
        }

        received_results[task_id] = controller_result
        save_result(controller_result)

        print(
            f"Result: {task_id} completed by "
            f"{controller_result['worker_id']} | "
            f"worker={controller_result['worker_execution_time_ms']} ms | "
            f"end-to-end={controller_result['end_to_end_latency_ms']} ms",
            flush=True,
        )

        if len(received_results) == len(TASKS):
            results_complete_event.set()

    except Exception as error:
        print(
            f"Controller result processing failed: {error}",
            flush=True,
        )


def dispatch_tasks(client):
    for task in TASKS:
        worker_id = task["worker_id"]
        task_id = task["task_id"]
        topic = f"research/tasks/{worker_id}"

        payload = {
            "task_id": task_id,
            "iterations": task["iterations"],
        }

        dispatch_times[task_id] = time.perf_counter()

        client.publish(
            topic,
            json.dumps(payload),
            qos=1,
        )

        print(
            f"Dispatched {task_id} to {worker_id}",
            flush=True,
        )

        time.sleep(0.5)


def main():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="central-controller",
    )

    client.on_connect = on_connect
    client.on_message = on_message

    print("Starting central controller", flush=True)

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    if not connected_event.wait(timeout=10):
        raise RuntimeError(
            "Controller could not connect to MQTT"
        )

    dispatch_tasks(client)

    if not results_complete_event.wait(timeout=30):
        print(
            "Timed out while waiting for worker results",
            flush=True,
        )

    client.disconnect()
    client.loop_stop()

    print(
        f"Received {len(received_results)} "
        f"of {len(TASKS)} results",
        flush=True,
    )


if __name__ == "__main__":
    main()