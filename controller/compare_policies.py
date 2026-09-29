import csv
from collections import defaultdict

from controller.offloading_policy import load_workers
from controller.policies import apply_policy
from shared.config_loader import PROJECT_ROOT, load_config


def read_csv(file_path):
    with file_path.open("r", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def run_comparison():
    config = load_config()
    output = config["output"]

    tasks = read_csv(PROJECT_ROOT / output["tasks_file"])
    workers = load_workers(
        PROJECT_ROOT / output["workers_file"]
    )

    failure_rows = read_csv(
        PROJECT_ROOT / output["failure_outcomes_file"]
    )

    failure_lookup = {
        (
            row["condition"],
            row["task_id"],
            row["worker_id"],
        ): row["failed"] == "1"
        for row in failure_rows
    }

    cloud_latency = float(
        config["cloud"]["estimated_latency_ms"]
    )

    fallback_overhead = float(
        config["cloud"]["fallback_overhead_ms"]
    )

    policies = config["experiment"]["policies"]

    conditions = config["experiment"][
        "failure_conditions"
    ].keys()

    results = []

    for condition in conditions:
        for policy in policies:
            for task in tasks:
                decision = apply_policy(
                    policy,
                    task,
                    workers,
                    config,
                )

                initial_destination = decision["destination"]

                worker_id = decision.get(
                    "worker_id",
                    "aws_lambda",
                )

                edge_failed = False
                fallback_used = False
                energy_cost = 0

                if initial_destination == "edge":
                    edge_failed = failure_lookup.get(
                        (
                            condition,
                            task["task_id"],
                            worker_id,
                        ),
                        False,
                    )

                    edge_latency = float(
                        decision["predicted_latency_ms"]
                    )

                    energy_cost = float(
                        decision.get("energy_cost", 0)
                    )

                    if edge_failed:
                        fallback_used = True
                        final_destination = "aws_lambda"

                        observed_latency = (
                            edge_latency
                            + fallback_overhead
                            + cloud_latency
                        )
                    else:
                        final_destination = "edge"
                        observed_latency = edge_latency
                else:
                    final_destination = "aws_lambda"
                    observed_latency = cloud_latency

                deadline = float(task["deadline_ms"])

                results.append(
                    {
                        "condition": condition,
                        "policy": policy,
                        "task_id": task["task_id"],
                        "initial_destination": (
                            initial_destination
                        ),
                        "final_destination": (
                            final_destination
                        ),
                        "worker_id": worker_id,
                        "edge_failed": int(edge_failed),
                        "fallback_used": int(fallback_used),
                        "observed_latency_ms": round(
                            observed_latency,
                            2,
                        ),
                        "energy_cost": round(
                            energy_cost,
                            3,
                        ),
                        "deadline_ms": deadline,
                        "deadline_missed": int(
                            observed_latency > deadline
                        ),
                    }
                )

    output_file = (
        PROJECT_ROOT
        / output["comparison_results_file"]
    )

    fieldnames = [
        "condition",
        "policy",
        "task_id",
        "initial_destination",
        "final_destination",
        "worker_id",
        "edge_failed",
        "fallback_used",
        "observed_latency_ms",
        "energy_cost",
        "deadline_ms",
        "deadline_missed",
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
        writer.writerows(results)

    summary = defaultdict(
        lambda: {
            "failures": 0,
            "fallbacks": 0,
            "deadline_misses": 0,
        }
    )

    for result in results:
        key = (
            result["condition"],
            result["policy"],
        )

        summary[key]["failures"] += result["edge_failed"]
        summary[key]["fallbacks"] += result["fallback_used"]
        summary[key]["deadline_misses"] += (
            result["deadline_missed"]
        )

    print("Policy comparison completed")
    print(f"Total experiment rows: {len(results)}")

    for (condition, policy), values in summary.items():
        print(
            f"{condition} | {policy} | "
            f"failures={values['failures']} | "
            f"fallbacks={values['fallbacks']} | "
            f"deadline_misses={values['deadline_misses']}"
        )

    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    run_comparison()