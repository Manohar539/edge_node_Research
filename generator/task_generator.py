import csv
import random
from datetime import datetime, timezone
from pathlib import Path

from shared.config_loader import PROJECT_ROOT, load_config


WORKLOAD_TYPES = ["cpu", "memory", "network", "mixed"]
PRIORITIES = ["low", "medium", "high"]


def create_task(task_number):
    """Create one synthetic CPS task."""

    workload_type = random.choice(WORKLOAD_TYPES)

    return {
        "task_id": f"task-{task_number:04d}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "workload_type": workload_type,
        "input_size_kb": random.randint(100, 5000),
        "cpu_cycles_million": random.randint(100, 2000),
        "memory_required_mb": random.randint(64, 1024),
        "deadline_ms": random.randint(200, 3000),
        "priority": random.choices(
            PRIORITIES,
            weights=[0.20, 0.55, 0.25],
            k=1,
        )[0],
    }


def generate_tasks():
    """Generate repeatable synthetic tasks and save them as CSV."""

    config = load_config()

    random_seed = config["project"]["random_seed"]
    number_of_tasks = config["experiment"]["number_of_tasks"]
    output_file = PROJECT_ROOT / config["output"]["tasks_file"]

    random.seed(random_seed)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    tasks = [
        create_task(task_number)
        for task_number in range(1, number_of_tasks + 1)
    ]

    fieldnames = [
        "task_id",
        "created_at",
        "workload_type",
        "input_size_kb",
        "cpu_cycles_million",
        "memory_required_mb",
        "deadline_ms",
        "priority",
    ]

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tasks)

    print(f"Generated {len(tasks)} synthetic tasks")
    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    generate_tasks()