import csv
from collections import defaultdict
from statistics import mean

from shared.config_loader import PROJECT_ROOT, load_config


def read_results(file_path):
    with file_path.open("r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def summarise_results():
    config = load_config()

    results_file = (
        PROJECT_ROOT
        / config["output"]["comparison_results_file"]
    )

    summary_file = (
        PROJECT_ROOT
        / config["output"]["summary_file"]
    )

    results = read_results(results_file)

    groups = defaultdict(list)

    for result in results:
        key = (
            result["condition"],
            result["policy"],
        )

        groups[key].append(result)

    summaries = []

    for (condition, policy), rows in groups.items():
        total_tasks = len(rows)

        latencies = [
            float(row["observed_latency_ms"])
            for row in rows
        ]

        energy_costs = [
            float(row["energy_cost"])
            for row in rows
        ]

        failures = sum(
            int(row["edge_failed"])
            for row in rows
        )

        fallbacks = sum(
            int(row["fallback_used"])
            for row in rows
        )

        deadline_misses = sum(
            int(row["deadline_missed"])
            for row in rows
        )

        summaries.append(
            {
                "condition": condition,
                "policy": policy,
                "total_tasks": total_tasks,
                "average_latency_ms": round(
                    mean(latencies),
                    2,
                ),
                "failure_rate_percent": round(
                    (failures / total_tasks) * 100,
                    2,
                ),
                "fallback_rate_percent": round(
                    (fallbacks / total_tasks) * 100,
                    2,
                ),
                "deadline_miss_rate_percent": round(
                    (deadline_misses / total_tasks) * 100,
                    2,
                ),
                "total_energy_cost": round(
                    sum(energy_costs),
                    3,
                ),
                "average_energy_cost": round(
                    mean(energy_costs),
                    3,
                ),
            }
        )

    fieldnames = [
        "condition",
        "policy",
        "total_tasks",
        "average_latency_ms",
        "failure_rate_percent",
        "fallback_rate_percent",
        "deadline_miss_rate_percent",
        "total_energy_cost",
        "average_energy_cost",
    ]

    with summary_file.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(summaries)

    print("Summary generated successfully")
    print(f"Summary rows: {len(summaries)}")
    print(f"Saved to: {summary_file}")

    for row in summaries:
        print(
            f"{row['condition']} | "
            f"{row['policy']} | "
            f"latency={row['average_latency_ms']} ms | "
            f"failures={row['failure_rate_percent']}% | "
            f"energy={row['total_energy_cost']}"
        )


if __name__ == "__main__":
    summarise_results()