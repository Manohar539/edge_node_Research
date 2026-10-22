import time


def perform_cpu_work(iterations):
    result = 0

    for number in range(iterations):
        result += (number * number) % 97

    return result


def lambda_handler(event, context):
    start_time = time.perf_counter()

    task_id = event.get("task_id", "unknown-task")
    iterations = int(event.get("iterations", 1_000_000))

    calculation_result = perform_cpu_work(iterations)

    execution_time_ms = (
        time.perf_counter() - start_time
    ) * 1000

    return {
        "task_id": task_id,
        "worker_id": "aws_lambda",
        "status": "completed",
        "iterations": iterations,
        "execution_time_ms": round(
            execution_time_ms,
            3,
        ),
        "memory_limit_mb": context.memory_limit_in_mb,
        "aws_request_id": context.aws_request_id,
        "completed_timestamp": time.time(),
        "calculation_result": calculation_result,
    }