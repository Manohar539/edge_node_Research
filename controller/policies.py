from controller.offloading_policy import (
    calculate_energy_cost,
    calculate_latency,
    select_worker,
)


def eligible_workers(task, workers):
    """Return available workers with sufficient memory."""

    required_memory = float(task["memory_required_mb"])

    return [
        worker
        for worker in workers
        if worker["status"] == "available"
        and float(worker["memory_mb"]) >= required_memory
    ]


def cloud_only_policy(task, workers, config):
    """Send every task directly to AWS Lambda."""

    return {
        "destination": "aws_lambda",
        "worker_id": "aws_lambda",
        "reason": "Cloud-only policy",
    }


def latency_only_policy(task, workers, config):
    """Choose the edge worker with the lowest latency."""

    candidates = eligible_workers(task, workers)

    if not candidates:
        return {
            "destination": "aws_lambda",
            "worker_id": "aws_lambda",
            "reason": "No eligible edge worker",
        }

    worker = min(
        candidates,
        key=lambda item: calculate_latency(task, item),
    )

    return {
        "destination": "edge",
        "worker_id": worker["worker_id"],
        "predicted_latency_ms": round(
            calculate_latency(task, worker),
            2,
        ),
        "failure_probability": float(
            worker["base_failure_probability"]
        ),
        "energy_cost": calculate_energy_cost(task, worker),
        "reason": "Lowest predicted latency",
    }


def energy_only_policy(task, workers, config):
    """Choose the worker with the lowest energy cost."""

    candidates = eligible_workers(task, workers)

    if not candidates:
        return {
            "destination": "aws_lambda",
            "worker_id": "aws_lambda",
            "reason": "No eligible edge worker",
        }

    worker = min(
        candidates,
        key=lambda item: calculate_energy_cost(task, item),
    )

    return {
        "destination": "edge",
        "worker_id": worker["worker_id"],
        "predicted_latency_ms": round(
            calculate_latency(task, worker),
            2,
        ),
        "failure_probability": float(
            worker["base_failure_probability"]
        ),
        "energy_cost": calculate_energy_cost(task, worker),
        "reason": "Lowest predicted energy cost",
    }


def reliability_aware_policy(task, workers, config):
    """Apply the proposed reliability-aware policy."""

    return select_worker(task, workers, config)


POLICY_FUNCTIONS = {
    "cloud_only": cloud_only_policy,
    "latency_only": latency_only_policy,
    "energy_only": energy_only_policy,
    "reliability_aware": reliability_aware_policy,
}


def apply_policy(policy_name, task, workers, config):
    """Apply the requested offloading policy."""

    if policy_name not in POLICY_FUNCTIONS:
        raise ValueError(f"Unknown policy: {policy_name}")

    policy_function = POLICY_FUNCTIONS[policy_name]

    return policy_function(task, workers, config)