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
            $runRows = @(
                Import-Csv $outputFile |
                    Where-Object {
                        $_.run_id -eq $runId
                    }
            )

            if ($runRows.Count -ne 100) {
                throw (
                    "Run $runId produced " +
                    "$($runRows.Count) rows; expected 100."
                )
            }

            $uniqueTaskIds = @(
                $runRows.task_id |
                    Sort-Object -Unique
            )

            if ($uniqueTaskIds.Count -ne 100) {
                throw (
                    "Run $runId does not contain " +
                    "100 unique task IDs."
                )
            }

            $incompleteRows = @(
                $runRows |
                    Where-Object {
                        $_.status -ne "completed"
                    }
            )

            if ($incompleteRows.Count -ne 0) {
                throw (
                    "Run $runId contains " +
                    "$($incompleteRows.Count) " +
                    "incomplete task rows."
                )
            }

            $validCloudTypes = @(
                "none",
                "policy_cloud",
                "direct_cloud",
                "timeout_fallback"
            )

            $invalidCloudRows = @(
                $runRows |
                    Where-Object {
                        $_.cloud_offload_type `
                            -notin $validCloudTypes
                    }
            )

            if ($invalidCloudRows.Count -ne 0) {
                throw (
                    "Run $runId contains invalid " +
                    "cloud-offload classifications."
                )
            }

            Write-Host (
                "Validated 100 completed task rows " +
                "for $runId"
            )
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
$uniqueRunIds = @(
    $taskRows.run_id |
        Sort-Object -Unique
)

$expectedSummaryRows = $uniqueRunIds.Count * 2

if ($summaryRows.Count -ne $expectedSummaryRows) {
    throw (
        "Found $($summaryRows.Count) summary rows; " +
        "expected $expectedSummaryRows."
    )
}

foreach ($completedRunId in $uniqueRunIds) {
    $runSummaries = @(
        $summaryRows |
            Where-Object {
                $_.run_id -eq $completedRunId
            }
    )

    if ($runSummaries.Count -ne 2) {
        throw (
            "$completedRunId has " +
            "$($runSummaries.Count) summaries; " +
            "expected 2."
        )
    }

    $primarySummary = @(
        $runSummaries |
            Where-Object {
                $_.analysis_scope -eq `
                    "primary_all_tasks"
            }
    )

    if (
        $primarySummary.Count -ne 1 -or
        [int]$primarySummary[0].tasks_total -ne 100
    ) {
        throw (
            "$completedRunId has an invalid " +
            "primary summary."
        )
    }

    $postWarmupSummary = @(
        $runSummaries |
            Where-Object {
                $_.analysis_scope -eq `
                    "secondary_post_warmup"
            }
    )

    if (
        $postWarmupSummary.Count -ne 1 -or
        [int]$postWarmupSummary[0].tasks_total -ne 80
    ) {
        throw (
            "$completedRunId has an invalid " +
            "post-warm-up summary."
        )
    }
}

Write-Host (
    "Validated $($uniqueRunIds.Count) runs and " +
    "$($summaryRows.Count) summary rows."
)
Write-Host ""
Write-Host "Week 5 primary experiment completed."
Write-Host "Task rows: $($taskRows.Count)"
Write-Host "Run summaries: $($summaryRows.Count)"
Write-Host "Task results: $outputFile"
Write-Host "Run summaries: $summaryFile"
Write-Host "Checkpoint file: $checkpointFile"