# Week 5 Pre-Specified Experimental Analysis Protocol

## 1. Purpose

This document records the analysis decisions before execution of the
full experiment. These rules will not be changed after examining the
experimental results.

## 2. Experimental Design

The primary experiment contains:

- Four policies:
  - cloud_only
  - latency_only
  - energy_only
  - reliability_aware
- Four configured failure rates:
  - 0%
  - 5%
  - 15%
  - 30%
- Twenty matched seeds:
  - 101 to 120
- One hundred tasks per run
- 320 primary run summaries
- 32,000 primary task executions

The same seed will generate the same workload definitions across all
policies and failure-rate conditions.

Workers will be recreated before every run so that energy, reliability
history, queue state and counters start from the same initial state.

## 3. Failure-Probability Estimation

The fault injector's configured rate will not be provided to the
controller.

Each worker will estimate its failure probability from its own most
recent task outcomes using:

estimated_failure_probability =
(window_failures + 1) / (window_attempts + 10)

The rolling window contains at most 20 outcomes.

The initial estimate is therefore:

(0 + 1) / (0 + 10) = 0.10

The worker publishes the estimate in its MQTT status message. The
controller uses this observed estimate for eligibility filtering and
policy scoring.

## 4. Warm-Up Handling

The primary analysis will include all 100 tasks because early operation
under limited evidence is part of the real behaviour of an online
offloading policy.

A pre-specified warm-up sensitivity analysis will repeat all run-level
calculations using tasks 21 to 100 only.

Tasks 1 to 20 will:

- execute normally;
- update worker reliability estimates;
- update remaining modelled energy;
- influence queue and worker state;
- remain in the raw dataset.

They will only be excluded when producing the secondary post-warm-up
run summaries.

The all-task analysis remains primary. The tasks 21-100 analysis is a
sensitivity analysis.

## 5. Primary Metric

The primary outcome is run-level service-disruption rate.

A task is classified as disrupted when it does not complete successfully
or when its measured end-to-end latency exceeds its configured deadline.

Secondary outcomes are:

- deadline-miss rate;
- mean end-to-end latency;
- median end-to-end latency;
- cloud-execution rate;
- fallback rate;
- task-completion rate;
- total modelled energy.

Energy is a configured software model and is not a physical power
measurement.

## 6. Failure-Rate Interpretation

The failure rates will be evaluated separately. They will not be pooled.

### 0% condition

This is the no-failure control. Reliability-aware superiority is not
required.

### 5% condition

This is the low-disruption floor condition. At 100 tasks, approximately
five injected failure events are expected per run, subject to seeded
Bernoulli variation.

With 20 observed outcomes, the smoothed estimate exceeds the 0.40
eligibility ceiling only when at least 12 of the 20 recent attempts fail:

(failures + 1) / 30 > 0.40

The eligibility filter is therefore not expected to activate at 5%.

Reliability-aware and latency-only are expected to behave similarly.
A statistically significant difference between them is not expected.
Failure to find superiority at 5% will not invalidate the robustness
claim.

Differences from cloud-only or energy-only may still result from their
latency or energy-selection behaviour.

### 15% and 30% conditions

These are the reliability-challenging conditions used for the principal
robustness conclusion.

## 7. Robustness Decision Rule

Robustness will be evaluated separately at each failure rate using the
20 matched seeds.

The strongest robustness conclusion will be supported only if the
reliability-aware policy has:

1. a lower run-level service-disruption rate than cloud-only,
   latency-only and energy-only;
2. Holm-adjusted p < 0.05 for each required comparison;
3. a consistently favourable effect direction;
4. the required result at both 15% and 30%;
5. the required result under default, latency-priority,
   reliability-priority and energy-priority weight settings.

Absence of significant superiority at 5% will not invalidate robustness.

A significant deterioration at 5% will be reported as evidence of
unnecessary low-failure overhead.

If the rule holds at 15% but not 30%, or at 30% but not 15%, the result
will be described as conditionally robust rather than fully robust.

## 8. Statistical Tests

The seed is the statistical block. Tasks within a run are not treated
as independent observations.

One Friedman test will compare the four policies at each failure rate.

The four Friedman p-values, corresponding to 0%, 5%, 15% and 30%, will
be Holm-corrected as one omnibus comparison family.

Where an adjusted Friedman result is significant, all six pairwise
policy comparisons within that failure rate will be tested using paired
Wilcoxon signed-rank tests.

Holm correction will be applied across the six pairwise comparisons
within that failure rate.

Comparisons from different failure rates will not be combined because
the rates are pre-specified operating conditions.

The same correction structure will be repeated and reported separately
for each sensitivity-weight setting.

Effect sizes and descriptive confidence intervals will be reported
alongside adjusted p-values.

Non-significant results will not be interpreted as proof of equivalence.

## 9. Analysis Windows

Two run-summary datasets will be produced:

1. Primary summaries:
   - task sequences 1 to 100;
2. Post-warm-up summaries:
   - task sequences 21 to 100.

The robustness conclusion will be based on the primary summaries.

The post-warm-up summaries will show whether the conclusion changes
after the estimator has accumulated operational evidence.

## 10. Protocol Freeze

This protocol must be committed before the Week 5 primary experiment
begins.

Any later deviation will be documented with:

- the reason for the deviation;
- the date of the change;
- whether the change was made before or after inspecting results;
- the effect on interpretation.