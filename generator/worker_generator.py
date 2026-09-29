import csv
import random

from shared.config_loader import PROJECT_ROOT, load_config


def create_worker(worker_number):
    """Create one synthetic edge-worker profile."""

    energy_capacity = random.randint(70, 100)

    return {
        "worker_id": f"edge-worker-{worker_number:02d}",
        "cpu_capacity_mips": random.randint(1000, 4000),
        "memory_mb": random.choice([1024, 2048, 4096]),
        "network_mbps": random.randint(20, 100),
        "base_latency_ms": random.randint(10, 80),
        "energy_capacity": energy_capacity,
        "remaining_energy": energy_capacity,
        "base_failure_probability": round(
            random.uniform(0.02, 0.20),
            3,
        ),
        "queue_limit": random.randint(3, 10),
        "current_queue": 0,
        "status": "available",
    }


def generate_workers():
    """Generate repeatable synthetic edge-worker profiles."""

    config = load_config()

    random_seed = config["project"]["random_seed"]
    number_of_workers = config["experiment"]["number_of_workers"]
    output_file = PROJECT_ROOT / config["output"]["workers_file"]

    # Use a different deterministic sequence from the task generator.
    random.seed(random_seed + 100)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    workers = [
        create_worker(worker_number)
        for worker_number in range(1, number_of_workers + 1)
    ]

    fieldnames = [
        "worker_id",
        "cpu_capacity_mips",
        "memory_mb",
        "network_mbps",
        "base_latency_ms",
        "energy_capacity",
        "remaining_energy",
        "base_failure_probability",
        "queue_limit",
        "current_queue",
        "status",
    ]

    with output_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(workers)

    print(f"Generated {len(workers)} synthetic edge workers")
    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    generate_workers()