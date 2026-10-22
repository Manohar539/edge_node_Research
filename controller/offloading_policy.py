import csv

from shared.config_loader import PROJECT_ROOT, load_config


def load_first_task(file_path):
    """Load the first generated task."""

    with file_path.open("r", encoding="utf-8") as file:
        return next(csv.DictReader(file))


def load_workers(file_path):
    """Load all generated edge workers."""

    with file_path.open("r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def calculate_latency(task, worker):
    """Estimate task execution and network latency."""

    cpu_cycles = float(task["cpu_cycles_million"])
    cpu_capacity = float(worker["cpu_capacity_mips"])
    input_size_kb = float(task["input_size_kb"])
    network_mbps = float(worker["network_mbps"])
    base_latency = float(worker["base_latency_ms"])

    execution_time_ms = (cpu_cycles / cpu_capacity) * 1000

    transfer_time_ms = (
        (input_size_kb * 8) / (network_mbps * 1000)
    ) * 1000

    return base_latency + execution_time_ms + transfer_time_ms


def calculate_energy_cost(task, worker):
    """Estimate software-modelled energy units."""

    if "iterations" in task:
        energy_rate = float(
            worker.get("energy_cost_per_million", 2.0)
        )

        return round(
            (float(task["iterations"]) / 1_000_000)
            * energy_rate,
            3,
        )

    cpu_ratio = (
        float(task["cpu_cycles_million"])
        / float(worker["cpu_capacity_mips"])
    )

    data_ratio = float(task["input_size_kb"]) / 5000

    return round((cpu_ratio * 5) + (data_ratio * 2), 3)


def select_worker(task, workers, config):
    """Select the best eligible worker for a task."""

    controller_config = config["controller"]
    weights = controller_config["weights"]

    minimum_energy = controller_config["minimum_energy"]
    maximum_failure = controller_config[
        "maximum_failure_probability"
    ]

    deadline_ms = float(task["deadline_ms"])
    required_memory = float(task["memory_required_mb"])

    candidates = []

    for worker in workers:
        if worker["status"] != "available":
            continue

        if float(worker["memory_mb"]) < required_memory:
            continue

        failure_probability = float(
            worker["estimated_failure_probability"]
        )

        if failure_probability > maximum_failure:
            continue

        predicted_latency = calculate_latency(task, worker)
        energy_cost = calculate_energy_cost(task, worker)

        remaining_energy = (
            float(worker["remaining_energy"]) - energy_cost
        )

        if remaining_energy < minimum_energy:
            continue

        queue_utilisation = (
            float(worker["current_queue"])
            / float(worker["queue_limit"])
        )

        latency_score = predicted_latency / deadline_ms
        energy_score = energy_cost / 100

        total_score = (
            weights["latency"] * latency_score
            + weights["reliability"] * failure_probability
            + weights["energy"] * energy_score
            + weights["queue"] * queue_utilisation
        )

        candidates.append(
            {
                "worker_id": worker["worker_id"],
                "predicted_latency_ms": round(
                    predicted_latency,
                    2,
                ),
                "failure_probability": failure_probability,
                "energy_cost": energy_cost,
                "remaining_energy": round(
                    remaining_energy,
                    2,
                ),
                "score": round(total_score, 4),
            }
        )

    if not candidates:
        return {
            "destination": "aws_lambda",
            "reason": "No eligible edge worker",
        }

    best_worker = min(
        candidates,
        key=lambda candidate: candidate["score"],
    )

    best_worker["destination"] = "edge"
    return best_worker


def main():
    config = load_config()

    tasks_file = (
        PROJECT_ROOT / config["output"]["tasks_file"]
    )
    workers_file = (
        PROJECT_ROOT / config["output"]["workers_file"]
    )

    task = load_first_task(tasks_file)
    workers = load_workers(workers_file)

    decision = select_worker(task, workers, config)

    print(f"Task: {task['task_id']}")
    print(f"Decision: {decision}")


if __name__ == "__main__":
    main()