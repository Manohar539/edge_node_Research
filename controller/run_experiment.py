import csv

from controller.offloading_policy import (
    load_workers,
    select_worker,
)
from shared.config_loader import PROJECT_ROOT, load_config


def load_tasks(file_path):
    """Load all generated tasks."""

    with file_path.open("r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def run_experiment():
    """Apply the reliability-aware policy to every task."""

    config = load_config()

    tasks_file = PROJECT_ROOT / config["output"]["tasks_file"]
    workers_file = PROJECT_ROOT / config["output"]["workers_file"]
    results_file = PROJECT_ROOT / config["output"]["results_file"]

    tasks = load_tasks(tasks_file)
    workers = load_workers(workers_file)

    results = []

    for task in tasks:
        decision = select_worker(task, workers, config)

        result = {
            "task_id": task["task_id"],
            "policy": "reliability_aware",
            "destination": decision["destination"],
            "worker_id": decision.get(
                "worker_id",
                "aws_lambda",
            ),
            "predicted_latency_ms": decision.get(
                "predicted_latency_ms",
                "",
            ),
            "failure_probability": decision.get(
                "failure_probability",
                "",
            ),
            "energy_cost": decision.get(
                "energy_cost",
                "",
            ),
            "score": decision.get("score", ""),
            "reason": decision.get("reason", ""),
        }

        results.append(result)

    results_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "task_id",
        "policy",
        "destination",
        "worker_id",
        "predicted_latency_ms",
        "failure_probability",
        "energy_cost",
        "score",
        "reason",
    ]

    with results_file.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(results)

    edge_tasks = sum(
        result["destination"] == "edge"
        for result in results
    )

    cloud_tasks = len(results) - edge_tasks

    print("Experiment completed successfully")
    print(f"Total tasks: {len(results)}")
    print(f"Edge decisions: {edge_tasks}")
    print(f"AWS Lambda decisions: {cloud_tasks}")
    print(f"Results saved to: {results_file}")


if __name__ == "__main__":
    run_experiment()