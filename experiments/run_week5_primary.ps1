param(
    [int]$StartRepetition = 1,
    [int]$EndRepetition = 20,

    [string[]]$FailureRates = @(
        "0.00",
        "0.05",
        "0.15",
        "0.30"
    ),

    [string[]]$Policies = @(
        "cloud_only",
        "latency_only",
        "energy_only",
        "reliability_aware"
    ),

    [switch]$ResetOutputs
)

$ErrorActionPreference = "Stop"

$numberOfTasks = "100"
$weightSetting = "default"
$taskIntervalSeconds = "0.05"

$outputFile = "data\week5_primary_task_results.csv"
$summaryFile = "data\week5_primary_run_summaries.csv"
$checkpointFile = "data\week5_primary_checkpoints.txt"

$containerOutputFile = (
    "/app/data/week5_primary_task_results.csv"
)

if ($StartRepetition -lt 1) {
    throw "StartRepetition must be at least 1."
}

if ($EndRepetition -gt 20) {
    throw "EndRepetition cannot exceed 20."
}

if ($StartRepetition -gt $EndRepetition) {
    throw "StartRepetition cannot exceed EndRepetition."
}

$validPolicies = @(
    "cloud_only",
    "latency_only",
    "energy_only",
    "reliability_aware"
)

$validFailureRates = @(
    "0.00",
    "0.05",
    "0.15",
    "0.30"
)

foreach ($policy in $Policies) {
    if ($policy -notin $validPolicies) {
        throw "Invalid policy: $policy"
    }
}

foreach ($failureRate in $FailureRates) {
    if ($failureRate -notin $validFailureRates) {
        throw "Invalid failure rate: $failureRate"
    }
}

if ($ResetOutputs) {
    Write-Host "Resetting Week 5 primary outputs."

    Remove-Item $outputFile `
        -ErrorAction SilentlyContinue

    Remove-Item $summaryFile `
        -ErrorAction SilentlyContinue

    Remove-Item $checkpointFile `
        -ErrorAction SilentlyContinue
}

$completedRuns = @{}

if (Test-Path $checkpointFile) {
    Get-Content $checkpointFile | ForEach-Object {
        $runName = $_.Trim()

        if ($runName) {
            $completedRuns[$runName] = $true
        }
    }
}

function Remove-PartialRunRows {
    param(
        [string]$RunId
    )

    if (-not (Test-Path $outputFile)) {
        return
    }

    $allRows = @(
        Import-Csv $outputFile
    )

    $remainingRows = @(
        $allRows | Where-Object {
            $_.run_id -ne $RunId
        }
    )

    if ($remainingRows.Count -eq $allRows.Count) {
        return
    }

    Write-Host (
        "Removing incomplete rows for $RunId"
    )

    if ($remainingRows.Count -eq 0) {
        Remove-Item $outputFile
    }
    else {
        $remainingRows |
            Export-Csv `
                -Path $outputFile `
                -NoTypeInformation `
                -Encoding utf8
    }
}

Write-Host ""
Write-Host "Week 5 primary experiment"
Write-Host (
    "Repetitions: $StartRepetition to " +
    "$EndRepetition"
)
Write-Host "Failure rates: $($FailureRates -join ', ')"
Write-Host "Policies: $($Policies -join ', ')"
Write-Host "Tasks per run: $numberOfTasks"
Write-Host ""

for (
    $repetition = $StartRepetition;
    $repetition -le $EndRepetition;
    $repetition++
) {
    # Seeds 101 to 120 are shared across policies
    # and failure-rate conditions.
    $runSeed = 100 + $repetition

    foreach ($failureRate in $FailureRates) {
        $failureLabel = $failureRate.Replace(".", "")

        foreach ($policy in $Policies) {
            $runId = (
                "week5-{0}-f{1}-r{2:D2}" -f `
                $policy,
                $failureLabel,
                $repetition
            )

            if ($completedRuns.ContainsKey($runId)) {
                Write-Host "Skipping completed run: $runId"
                continue
            }

            # Remove rows left by an interrupted run before
            # safely repeating that run.
            Remove-PartialRunRows -RunId $runId

            Write-Host ""
            Write-Host "===================================="
            Write-Host "Run: $runId"
            Write-Host "Policy: $policy"
            Write-Host "Failure rate: $failureRate"
            Write-Host "Repetition: $repetition"
            Write-Host "Seed: $runSeed"
            Write-Host "===================================="

            $env:FAILURE_RATE = $failureRate
            $env:RUN_SEED = [string]$runSeed

            docker compose up -d --force-recreate `
                worker-1 worker-2 worker-3

            if ($LASTEXITCODE -ne 0) {
                throw (
                    "Worker recreation failed for $runId"
                )
            }

            docker compose --profile controller run --rm `
                -e "POLICY_NAME=$policy" `
                -e "NUMBER_OF_TASKS=$numberOfTasks" `
                -e "RUN_SEED=$runSeed" `
                -e "RUN_ID=$runId" `
                -e "REPETITION=$repetition" `
                -e "FAILURE_RATE=$failureRate" `
                -e "WEIGHT_SETTING=$weightSetting" `
                -e "TASK_INTERVAL_SECONDS=$taskIntervalSeconds" `
                -e "POLICY_RESULTS_FILE=$containerOutputFile" `
                --entrypoint python controller `
                -u -m controller.policy_controller

            if ($LASTEXITCODE -ne 0) {
                throw (
                    "Controller experiment failed for $runId"
                )
            }

            Add-Content `
                -Path $checkpointFile `
                -Value $runId

            $completedRuns[$runId] = $true

            Write-Host "Completed run: $runId"
        }
    }
}

python -m analysis.run_summary `
    --input $outputFile `
    --output $summaryFile

if ($LASTEXITCODE -ne 0) {
    throw "Run-level summarisation failed."
}

$taskRows = @(
    Import-Csv $outputFile
)

$summaryRows = @(
    Import-Csv $summaryFile
)

Write-Host ""
Write-Host "Week 5 primary experiment completed."
Write-Host "Task rows: $($taskRows.Count)"
Write-Host "Run summaries: $($summaryRows.Count)"
Write-Host "Task results: $outputFile"
Write-Host "Run summaries: $summaryFile"
Write-Host "Checkpoint file: $checkpointFile"