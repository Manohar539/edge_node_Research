import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


SUMMARY_FIELDS = [
    "run_id",
    "run_seed",
    "repetition",
    "configured_failure_rate",
    "weight_setting",
    "policy",
    "tasks_total",
    "tasks_completed",
    "service_disruptions",
    "service_disruption_rate",
    "deadline_misses",
    "deadline_miss_rate",
    "cloud_executions",
    "cloud_execution_rate",
    "fallbacks",
    "fallback_rate",
    "mean_end_to_end_latency_ms",
    "median_end_to_end_latency_ms",
    "mean_worker_execution_time_ms",
    "total_modelled_energy",
]


def number(value, default=0.0):
    """Convert a CSV value into a number safely."""

    if value in ("", None):
        return default

    return float(value)


def load_results(input_file):
    """Load task-level results from a CSV file."""

    with input_file.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:
        return list(csv.DictReader(file))


def group_results(rows):
    """Group task rows into independent experimental runs."""

    grouped = defaultdict(list)

    for row in rows:
        key = (
            row["run_id"],
            row["run_seed"],
            row["repetition"],
            row["configured_failure_rate"],
            row["weight_setting"],
            row["policy"],
        )

        grouped[key].append(row)

    return grouped


def summarise_run(key, rows):
    """Calculate one run-level summary."""

    (
        run_id,
        run_seed,
        repetition,
        failure_rate,
        weight_setting,
        policy,
    ) = key

    tasks_total = len(rows)

    tasks_completed = sum(
        row["status"] == "completed"
        for row in rows
    )

    disruptions = sum(
        int(number(row["service_disrupted"]))
        for row in rows
    )

    deadline_misses = sum(
        int(number(row["deadline_missed"]))
        for row in rows
    )

    cloud_executions = sum(
        int(number(row["cloud_used"]))
        for row in rows
    )

    fallbacks = sum(
        int(number(row["fallback_used"]))
        for row in rows
    )

    end_to_end_latencies = [
        number(row["end_to_end_latency_ms"])
        for row in rows
        if row["end_to_end_latency_ms"] != ""
    ]

    worker_execution_times = [
        number(row["worker_execution_time_ms"])
        for row in rows
        if row["worker_execution_time_ms"] != ""
    ]

    modelled_energy = [
        number(row["energy_cost_modelled"])
        for row in rows
        if row["energy_cost_modelled"] != ""
    ]

    return {
        "run_id": run_id,
        "run_seed": run_seed,
        "repetition": repetition,
        "configured_failure_rate": failure_rate,
        "weight_setting": weight_setting,
        "policy": policy,
        "tasks_total": tasks_total,
        "tasks_completed": tasks_completed,
        "service_disruptions": disruptions,
        "service_disruption_rate": round(
            disruptions / tasks_total,
            4,
        ),
        "deadline_misses": deadline_misses,
        "deadline_miss_rate": round(
            deadline_misses / tasks_total,
            4,
        ),
        "cloud_executions": cloud_executions,
        "cloud_execution_rate": round(
            cloud_executions / tasks_total,
            4,
        ),
        "fallbacks": fallbacks,
        "fallback_rate": round(
            fallbacks / tasks_total,
            4,
        ),
        "mean_end_to_end_latency_ms": round(
            statistics.mean(end_to_end_latencies),
            3,
        ),
        "median_end_to_end_latency_ms": round(
            statistics.median(end_to_end_latencies),
            3,
        ),
        "mean_worker_execution_time_ms": round(
            statistics.mean(worker_execution_times),
            3,
        ),
        "total_modelled_energy": round(
            sum(modelled_energy),
            3,
        ),
    }


def write_summaries(output_file, summaries):
    """Write run summaries to CSV."""

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_file.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=SUMMARY_FIELDS,
        )

        writer.writeheader()
        writer.writerows(summaries)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )

    arguments = parser.parse_args()

    rows = load_results(arguments.input)

    if not rows:
        raise ValueError(
            "The task-level results file is empty"
        )

    grouped = group_results(rows)

    summaries = [
        summarise_run(key, run_rows)
        for key, run_rows in grouped.items()
    ]

    write_summaries(
        arguments.output,
        summaries,
    )

    print(
        f"Created {len(summaries)} run-level summaries "
        f"in {arguments.output}"
    )


if __name__ == "__main__":
    main()