import csv
import json
import os
import threading
import time
import boto3
from pathlib import Path

import paho.mqtt.client as mqtt

from controller.policies import apply_policy
from shared.config_loader import load_config


MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
POLICY_NAME = os.getenv("POLICY_NAME", "reliability_aware")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")
LAMBDA_FUNCTION = os.getenv(
    "AWS_LAMBDA_FUNCTION",
    "edge-cloud-fallback",
)

RESULT_TOPIC = "research/results"
STATUS_TOPIC = "research/workers/status"

OUTPUT_FILE = Path(
    os.getenv(
        "POLICY_RESULTS_FILE",
        "/app/data/policy_controller_results.csv",
    )
)

TASKS = [
    {
        "task_id": "policy-task-001",
        "iterations": 1_000_000,
        "cpu_cycles_million": 100,
        "input_size_kb": 256,
        "deadline_ms": 200,
        "memory_required_mb": 128,
    },
    {
        "task_id": "policy-task-002",
        "iterations": 1_500_000,
        "cpu_cycles_million": 180,
        "input_size_kb": 512,
        "deadline_ms": 250,
        "memory_required_mb": 256,
    },
    {
        "task_id": "policy-task-003",
        "iterations": 2_000_000,
        "cpu_cycles_million": 300,
        "input_size_kb": 1024,
        "deadline_ms": 350,
        "memory_required_mb": 300,
    },
]

config = load_config()

worker_profiles = {}
dispatch_times = {}
decisions = {}
result_events = {}

connected_event = threading.Event()
worker_lock = threading.Lock()


def save_result(result):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_exists = OUTPUT_FILE.exists()

    fields = [
        "task_id",
        "policy",
        "destination",
        "worker_id",
        "status",
        "iterations",
        "predicted_latency_ms",
        "worker_execution_time_ms",
        "end_to_end_latency_ms",
        "failure_probability",
        "energy_cost_modelled",
        "remaining_energy_modelled",
        "policy_score",
        "cpu_percent_measured",
        "memory_percent_measured",
        "timestamp",
    ]

    with OUTPUT_FILE.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fields,
            extrasaction="ignore",
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(result)


def handle_worker_status(payload):
    worker_id = payload["worker_id"]

    with worker_lock:
        first_message = worker_id not in worker_profiles
        worker_profiles[worker_id] = payload

    if first_message:
        print(
            f"Discovered {worker_id}: "
            f"memory={payload['memory_mb']} MB, "
            f"estimated_failure={payload['estimated_failure_probability']}, "
            f"energy={payload['remaining_energy']} "
            f"({payload['energy_value_type']})",
            flush=True,
        )


def handle_worker_result(payload):
    task_id = payload["task_id"]

    if task_id not in dispatch_times:
        return

    decision = decisions[task_id]

    end_to_end_latency_ms = (
        time.perf_counter() - dispatch_times[task_id]
    ) * 1000

    result = {
        "task_id": task_id,
        "policy": POLICY_NAME,
        "destination": "edge",
        "worker_id": payload["worker_id"],
        "status": payload["status"],
        "iterations": payload["iterations"],
        "predicted_latency_ms": decision.get(
            "predicted_latency_ms",
            "",
        ),
        "worker_execution_time_ms": payload[
            "execution_time_ms"
        ],
        "end_to_end_latency_ms": round(
            end_to_end_latency_ms,
            3,
        ),
        "failure_probability": decision.get(
            "failure_probability",
            "",
        ),
        "energy_cost_modelled": payload.get(
            "energy_cost_modelled",
            decision.get("energy_cost", ""),
        ),
        "remaining_energy_modelled": decision.get(
            "remaining_energy",
            "",
        ),
        "policy_score": decision.get("score", ""),
        "cpu_percent_measured": payload.get(
            "cpu_percent",
            "",
        ),
        "memory_percent_measured": payload.get(
            "memory_percent",
            "",
        ),
        "timestamp": payload.get(
            "completed_timestamp",
            time.time(),
        ),
    }

    save_result(result)

    print(
        f"Result: {task_id} completed by "
        f"{payload['worker_id']} | "
        f"worker={payload['execution_time_ms']} ms | "
        f"end-to-end={result['end_to_end_latency_ms']} ms",
        flush=True,
    )

    result_events[task_id].set()


def on_connect(client, userdata, flags, reason_code, properties):
    print(
        f"Policy controller connected to MQTT: {reason_code}",
        flush=True,
    )

    client.subscribe(RESULT_TOPIC, qos=1)
    client.subscribe(STATUS_TOPIC, qos=1)
    connected_event.set()


def on_message(client, userdata, message):
    try:
        payload = json.loads(
            message.payload.decode("utf-8")
        )

        if message.topic == STATUS_TOPIC:
            handle_worker_status(payload)
        elif message.topic == RESULT_TOPIC:
            handle_worker_result(payload)

    except Exception as error:
        print(
            f"Message processing failed: {error}",
            flush=True,
        )


def wait_for_workers(timeout_seconds=10):
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        with worker_lock:
            available_workers = len(worker_profiles)

        if available_workers >= 3:
            return True

        time.sleep(0.2)

    return False


def invoke_cloud_fallback(task,decision,original_start_time=None,):
    lambda_client = boto3.client(
        "lambda",
        region_name=AWS_REGION,
    )

    start_time = (
        original_start_time
        if original_start_time is not None
        else time.perf_counter()
    )

    response = lambda_client.invoke(
        FunctionName=LAMBDA_FUNCTION,
        InvocationType="RequestResponse",
        Payload=json.dumps(
            {
                "task_id": task["task_id"],
                "iterations": task["iterations"],
            }
        ).encode("utf-8"),
    )

    lambda_result = json.loads(
        response["Payload"].read().decode("utf-8")
    )

    if "FunctionError" in response:
        raise RuntimeError(
            f"Lambda execution failed: {lambda_result}"
        )

    end_to_end_latency_ms = (
        time.perf_counter() - start_time
    ) * 1000

    result = {
        "task_id": task["task_id"],
        "policy": POLICY_NAME,
        "destination": "aws_lambda",
        "worker_id": "aws_lambda",
        "status": lambda_result["status"],
        "iterations": lambda_result["iterations"],
        "predicted_latency_ms": config["cloud"][
            "estimated_latency_ms"
        ],
        "worker_execution_time_ms": lambda_result[
            "execution_time_ms"
        ],
        "end_to_end_latency_ms": round(
            end_to_end_latency_ms,
            3,
        ),
        "failure_probability": "",
        "energy_cost_modelled": "",
        "remaining_energy_modelled": "",
        "policy_score": "",
        "cpu_percent_measured": "",
        "memory_percent_measured": "",
        "timestamp": lambda_result[
            "completed_timestamp"
        ],
    }

    save_result(result)

    print(
        f"Lambda result: {task['task_id']} | "
        f"execution={lambda_result['execution_time_ms']} ms | "
        f"end-to-end={result['end_to_end_latency_ms']} ms",
        flush=True,
    )


def dispatch_task(client, task):
    with worker_lock:
        workers = list(worker_profiles.values())

    decision = apply_policy(
        POLICY_NAME,
        task,
        workers,
        config,
    )

    decisions[task["task_id"]] = decision

    print(
        f"Decision for {task['task_id']}: {decision}",
        flush=True,
    )

    if decision["destination"] == "aws_lambda":
        invoke_cloud_fallback(task, decision)
        return

    worker_id = decision["worker_id"]
    topic = f"research/tasks/{worker_id}"

    payload = {
        "task_id": task["task_id"],
        "iterations": task["iterations"],
    }

    result_events[task["task_id"]] = threading.Event()
    dispatch_times[task["task_id"]] = time.perf_counter()

    publish_result = client.publish(
        topic,
        json.dumps(payload),
        qos=1,
    )
    publish_result.wait_for_publish()

    print(
        f"Dispatched {task['task_id']} to "
        f"{worker_id} using {POLICY_NAME}",
        flush=True,
    )

    timeout_seconds = config["controller"][
        "worker_timeout_seconds"
    ]

    if not result_events[task["task_id"]].wait(
        timeout=timeout_seconds
    ):
        print(
            f"Edge timeout for {task['task_id']}; "
            f"invoking AWS Lambda fallback",
            flush=True,
        )

        invoke_cloud_fallback(
            task,
            {
                "reason": "Edge worker timeout or failure",
            },
            original_start_time=dispatch_times[
                task["task_id"]
            ],
        )

    time.sleep(1)


def main():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="policy-controller",
    )

    client.on_connect = on_connect
    client.on_message = on_message

    print(
        f"Starting controller with policy: {POLICY_NAME}",
        flush=True,
    )

    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()

    if not connected_event.wait(timeout=10):
        raise RuntimeError(
            "Controller could not connect to MQTT"
        )

    if not wait_for_workers():
        raise RuntimeError(
            "Three live worker profiles were not received"
        )

    print(
        "Three live Docker workers discovered",
        flush=True,
    )

    for task in TASKS:
        dispatch_task(client, task)

    client.disconnect()
    client.loop_stop()

    print(
        f"Policy experiment completed. Results: {OUTPUT_FILE}",
        flush=True,
    )


if __name__ == "__main__":
    main()