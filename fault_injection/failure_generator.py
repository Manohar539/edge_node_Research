import csv
import random

from shared.config_loader import PROJECT_ROOT, load_config


def read_csv(file_path):
    """Read a CSV file and return all rows."""

    with file_path.open("r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def generate_failure_outcomes():
    """Generate repeatable task-worker failure outcomes."""

    config = load_config()

    tasks_file = PROJECT_ROOT / config["output"]["tasks_file"]
    workers_file = PROJECT_ROOT / config["output"]["workers_file"]

    output_file = (
        PROJECT_ROOT
        / config["output"]["failure_outcomes_file"]
    )

    tasks = read_csv(tasks_file)
    workers = read_csv(workers_file)

    failure_conditions = config["experiment"][
        "failure_conditions"
    ]

    random_seed = config["project"]["random_seed"]
    random.seed(random_seed + 200)

    outcomes = []

    for condition, failure_probability in (
        failure_conditions.items()
    ):
        for task in tasks:
            for worker in workers:
                random_value = random.random()

                failed = (
                    random_value < failure_probability
                )

                outcomes.append(
                    {
                        "condition": condition,
                        "task_id": task["task_id"],
                        "worker_id": worker["worker_id"],
                        "failure_probability": (
                            failure_probability
                        ),
                        "random_value": round(
                            random_value,
                            6,
                        ),
                        "failed": int(failed),
                    }
                )

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "condition",
        "task_id",
        "worker_id",
        "failure_probability",
        "random_value",
        "failed",
    ]

    with output_file.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(outcomes)

    failures = sum(
        outcome["failed"]
        for outcome in outcomes
    )

    print("Failure outcomes generated successfully")
    print(f"Total outcomes: {len(outcomes)}")
    print(f"Failure outcomes: {failures}")
    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    generate_failure_outcomes()