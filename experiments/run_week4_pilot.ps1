$ErrorActionPreference = "Stop"

$failureRate = "0.15"
$runSeed = "101"
$numberOfTasks = "10"

$outputFile = "data\week4_all_policies_pilot.csv"
$summaryFile = "data\week4_all_policies_summary.csv"
$containerOutputFile = "/app/data/week4_all_policies_pilot.csv"

$policies = @(
    "cloud_only",
    "latency_only",
    "energy_only",
    "reliability_aware"
)

Remove-Item $outputFile -ErrorAction SilentlyContinue
Remove-Item $summaryFile -ErrorAction SilentlyContinue

foreach ($policy in $policies) {
    Write-Host ""
    Write-Host "Running policy: $policy"

    $env:FAILURE_RATE = $failureRate
    $env:RUN_SEED = $runSeed

    docker compose up -d --force-recreate `
        worker-1 worker-2 worker-3

    if ($LASTEXITCODE -ne 0) {
        throw "Worker recreation failed for $policy"
    }

    docker compose --profile controller run --rm `
        -e "POLICY_NAME=$policy" `
        -e "NUMBER_OF_TASKS=$numberOfTasks" `
        -e "RUN_SEED=$runSeed" `
        -e "RUN_ID=pilot-$policy-r001" `
        -e "REPETITION=1" `
        -e "FAILURE_RATE=$failureRate" `
        -e "WEIGHT_SETTING=default" `
        -e "TASK_INTERVAL_SECONDS=0.05" `
        -e "POLICY_RESULTS_FILE=$containerOutputFile" `
        --entrypoint python controller `
        -u -m controller.policy_controller

    if ($LASTEXITCODE -ne 0) {
        throw "Controller experiment failed for $policy"
    }
}

python -m analysis.run_summary `
    --input $outputFile `
    --output $summaryFile

if ($LASTEXITCODE -ne 0) {
    throw "Run-level summarisation failed"
}

Write-Host ""
Write-Host "Pilot experiment completed."
Write-Host "Task results: $outputFile"
Write-Host "Run summaries: $summaryFile"