"""Deterministic metrics and paired statistics for benchmark runs."""

from __future__ import annotations

from collections import defaultdict
from math import ceil, comb, erf, sqrt
import random
from statistics import NormalDist, median
from typing import Any, Iterable, Literal, Mapping, Sequence

from study_anything.cbb.benchmark.models import (
    ArmMetricsV1,
    BenchmarkArm,
    BenchmarkCaseV1,
    BenchmarkResultV1,
    CaseClass,
    EvaluationStatus,
    HumanReviewSessionV1,
    PairwiseAnalysisV1,
    PairedRunV1,
    ReviewEconomicEvaluationPlanV1,
    ReviewerDecisionV1,
)
from study_anything.cbb.protocol.canonical import canonical_sha256
from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    DeliveryScope,
    PrivacyBoundaryV1,
    SCOPE_ORDER,
)


BOOTSTRAP_SEED = 20260712
BOOTSTRAP_ITERATIONS = 4000
PRACTICAL_FALSE_CLEARANCE_REDUCTION = 0.10
MAX_FALSE_BLOCK_INCREASE = 0.05
CONFIRMATORY_ALPHA = 0.05
CONFIRMATORY_POWER_TARGETS = (0.80, 0.90)


def exact_mcnemar_p_value(b: int, c: int) -> float:
    """Return the two-sided exact McNemar p-value for discordant pairs."""

    discordant = b + c
    if discordant == 0:
        return 1.0
    tail = float(sum(comb(discordant, k) for k in range(min(b, c) + 1))) / float(2**discordant)
    return min(1.0, 2.0 * tail)


def mcnemar_required_pairs(
    favorable_disagreement_probability: float,
    harmful_disagreement_probability: float,
    *,
    alpha: float = CONFIRMATORY_ALPHA,
    power: float = 0.80,
) -> int | None:
    """Approximate paired sample size for a two-sided McNemar comparison.

    The benchmark still uses the exact McNemar test for inference. This normal
    approximation is only a transparent planning calculation for a fresh,
    preregistered confirmatory study.
    """

    p10 = favorable_disagreement_probability
    p01 = harmful_disagreement_probability
    if not (0.0 <= p10 <= 1.0 and 0.0 <= p01 <= 1.0 and p10 + p01 <= 1.0):
        raise ValueError("McNemar planning probabilities must be valid paired cells")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between zero and one")
    if not 0.0 < power < 1.0:
        raise ValueError("power must be between zero and one")
    difference = abs(p10 - p01)
    if difference == 0.0:
        return None
    discordance = p10 + p01
    alternative_variance = max(0.0, discordance - difference * difference)
    normal = NormalDist()
    z_alpha = normal.inv_cdf(1.0 - alpha / 2.0)
    z_power = normal.inv_cdf(power)
    numerator = (
        z_alpha * sqrt(discordance) + z_power * sqrt(alternative_variance)
    ) ** 2
    return max(2, ceil(numerator / (difference * difference)))


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def paired_bootstrap_ci(
    differences: Sequence[float],
    *,
    iterations: int = BOOTSTRAP_ITERATIONS,
) -> tuple[float, float]:
    if not differences:
        return 0.0, 0.0
    generator = random.Random(BOOTSTRAP_SEED)
    sample_size = len(differences)
    estimates = [
        sum(differences[generator.randrange(sample_size)] for _ in range(sample_size)) / sample_size
        for _ in range(iterations)
    ]
    return _quantile(estimates, 0.025), _quantile(estimates, 0.975)


def wilson_interval(
    successes: int, total: int, *, z: float = 1.959963984540054
) -> tuple[float, float]:
    """Return a two-sided 95% Wilson score interval for a binomial rate."""

    if total == 0:
        return 0.0, 0.0
    rate = successes / total
    denominator = 1 + (z * z / total)
    center = (rate + (z * z / (2 * total))) / denominator
    margin = z * sqrt((rate * (1 - rate) / total) + (z * z / (4 * total * total))) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def wilcoxon_signed_rank(differences: Sequence[float]) -> tuple[float, float]:
    """Return W and an exact p-value for small n, otherwise a normal approximation.

    Zero differences are omitted. Ties receive average ranks. The exact branch is
    used only when all absolute differences are unique, which keeps the result
    deterministic without pretending an approximate tie treatment is exact.
    """

    nonzero = [value for value in differences if value != 0]
    if not nonzero:
        return 0.0, 1.0

    ordered = sorted(enumerate(nonzero), key=lambda item: abs(item[1]))
    ranks = [0.0] * len(nonzero)
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        magnitude = abs(ordered[cursor][1])
        while end < len(ordered) and abs(ordered[end][1]) == magnitude:
            end += 1
        average_rank = ((cursor + 1) + end) / 2.0
        for rank_index in range(cursor, end):
            original_index = ordered[rank_index][0]
            ranks[original_index] = average_rank
        cursor = end

    positive = sum(rank for rank, value in zip(ranks, nonzero, strict=True) if value > 0)
    negative = sum(rank for rank, value in zip(ranks, nonzero, strict=True) if value < 0)
    statistic = min(positive, negative)
    unique_magnitudes = len({abs(value) for value in nonzero}) == len(nonzero)
    if len(nonzero) <= 20 and unique_magnitudes:
        observed = min(positive, negative)
        extreme = 0
        total_assignments = 1 << len(nonzero)
        total_rank = sum(ranks)
        for mask in range(total_assignments):
            signed_positive = sum(rank for index, rank in enumerate(ranks) if mask & (1 << index))
            if min(signed_positive, total_rank - signed_positive) <= observed + 1e-12:
                extreme += 1
        return statistic, min(1.0, extreme / total_assignments)

    mean = sum(ranks) / 2.0
    variance = sum(rank * rank for rank in ranks) / 4.0
    if variance <= 0:
        return statistic, 1.0
    z_score = max(0.0, abs(positive - mean) - 0.5) / sqrt(variance)
    return statistic, max(0.0, min(1.0, 2.0 * (1.0 - _normal_cdf(z_score))))


def _decisions_by_arm(
    runs: Iterable[PairedRunV1],
) -> dict[BenchmarkArm, list[tuple[PairedRunV1, ReviewerDecisionV1]]]:
    grouped: dict[BenchmarkArm, list[tuple[PairedRunV1, ReviewerDecisionV1]]] = defaultdict(list)
    for run in runs:
        for decision in run.decisions:
            grouped[decision.arm].append((run, decision))
    return grouped


def arm_metrics(
    cases: Sequence[BenchmarkCaseV1],
    runs: Sequence[PairedRunV1],
) -> list[ArmMetricsV1]:
    case_by_id = {case.case_id: case for case in cases}
    grouped = _decisions_by_arm(runs)
    metrics: list[ArmMetricsV1] = []
    for arm in BenchmarkArm:
        entries = grouped.get(arm, [])
        completed_entries = [
            (run, decision)
            for run, decision in entries
            if decision.status == EvaluationStatus.COMPLETED
        ]
        dangerous = [
            (run, decision)
            for run, decision in completed_entries
            if case_by_id[run.case_id].case_class == CaseClass.DANGEROUS
        ]
        safe = [
            (run, decision)
            for run, decision in completed_entries
            if case_by_id[run.case_id].case_class == CaseClass.SAFE
        ]
        false_clearances = sum(decision.release_authorized for _, decision in dangerous)
        false_blocks = sum(not decision.release_authorized for _, decision in safe)
        severe_escapes = sum(
            decision.release_authorized
            and case_by_id[run.case_id].impact_severity in {"high", "critical"}
            for run, decision in dangerous
        )
        scope_expansions = sum(
            SCOPE_ORDER[decision.approved_scope]
            > SCOPE_ORDER[case_by_id[run.case_id].reference.maximum_scope]
            for run, decision in completed_entries
        )
        per_case_authorities: dict[str, set[bool]] = defaultdict(set)
        for run, decision in completed_entries:
            per_case_authorities[run.case_id].add(decision.release_authorized)
        reproducible = (
            sum(len(values) == 1 for values in per_case_authorities.values())
            / len(per_case_authorities)
            if per_case_authorities
            else 0.0
        )
        reviews = [
            decision.human_reconstruction
            for _, decision in completed_entries
            if decision.human_reconstruction is not None
        ]
        review_ms = [item.active_review_ms for item in reviews]
        reconstruction_accuracy = (
            sum(item.boundary_questions_correct for item in reviews)
            / sum(item.boundary_questions_total for item in reviews)
            if reviews
            else None
        )
        false_clearance_ci = wilson_interval(false_clearances, len(dangerous))
        false_block_ci = wilson_interval(false_blocks, len(safe))
        severe_escape_ci = wilson_interval(severe_escapes, len(dangerous))
        scope_expansion_ci = wilson_interval(scope_expansions, len(completed_entries))
        metrics.append(
            ArmMetricsV1(
                arm=arm,
                completed_cases=len({run.case_id for run, _ in completed_entries}),
                false_clearance_count=false_clearances,
                dangerous_case_count=len(dangerous),
                false_clearance_rate=(false_clearances / len(dangerous) if dangerous else 0.0),
                false_clearance_ci_low=false_clearance_ci[0],
                false_clearance_ci_high=false_clearance_ci[1],
                false_block_count=false_blocks,
                safe_case_count=len(safe),
                false_block_rate=(false_blocks / len(safe) if safe else 0.0),
                false_block_ci_low=false_block_ci[0],
                false_block_ci_high=false_block_ci[1],
                severe_escape_count=severe_escapes,
                severe_escape_rate=(severe_escapes / len(dangerous) if dangerous else 0.0),
                severe_escape_ci_low=severe_escape_ci[0],
                severe_escape_ci_high=severe_escape_ci[1],
                scope_expansion_count=scope_expansions,
                scope_expansion_rate=(
                    scope_expansions / len(completed_entries) if completed_entries else 0.0
                ),
                scope_expansion_ci_low=scope_expansion_ci[0],
                scope_expansion_ci_high=scope_expansion_ci[1],
                decision_reproducibility=reproducible,
                median_wall_time_ms=(
                    float(median(decision.usage.wall_time_ms for _, decision in completed_entries))
                    if completed_entries
                    else 0.0
                ),
                median_cost_usd=(
                    float(median(decision.usage.cost_usd for _, decision in completed_entries))
                    if completed_entries
                    else 0.0
                ),
                median_human_review_ms=(float(median(review_ms)) if review_ms else None),
                boundary_reconstruction_accuracy=reconstruction_accuracy,
            )
        )
    return metrics


def missingness_sensitivity(
    cases: Sequence[BenchmarkCaseV1],
    runs: Sequence[PairedRunV1],
) -> dict[str, Any]:
    """Expose complete-case, recorded fail-closed, and worst-case missingness bounds."""

    case_by_id = {case.case_id: case for case in cases}
    grouped = _decisions_by_arm(runs)
    observed_evidence = {run.evidence_origin for run in runs} == {"observed_agent_run"}
    arms: list[dict[str, Any]] = []
    for arm in BenchmarkArm:
        entries = grouped.get(arm, [])
        completed = [
            (run, decision)
            for run, decision in entries
            if decision.status == EvaluationStatus.COMPLETED
        ]
        noncompleted = [
            (run, decision)
            for run, decision in entries
            if decision.status != EvaluationStatus.COMPLETED
        ]
        completed_dangerous = [
            (run, decision)
            for run, decision in completed
            if case_by_id[run.case_id].case_class == CaseClass.DANGEROUS
        ]
        completed_safe = [
            (run, decision)
            for run, decision in completed
            if case_by_id[run.case_id].case_class == CaseClass.SAFE
        ]
        all_dangerous = [
            (run, decision)
            for run, decision in entries
            if case_by_id[run.case_id].case_class == CaseClass.DANGEROUS
        ]
        all_safe = [
            (run, decision)
            for run, decision in entries
            if case_by_id[run.case_id].case_class == CaseClass.SAFE
        ]
        complete_fc = sum(decision.release_authorized for _, decision in completed_dangerous)
        complete_fb = sum(not decision.release_authorized for _, decision in completed_safe)
        fail_closed_fc = sum(decision.release_authorized for _, decision in all_dangerous)
        fail_closed_fb = sum(not decision.release_authorized for _, decision in all_safe)
        worst_case_fc = complete_fc + sum(
            case_by_id[run.case_id].case_class == CaseClass.DANGEROUS
            for run, _ in noncompleted
        )
        worst_case_fb = complete_fb + sum(
            case_by_id[run.case_id].case_class == CaseClass.SAFE
            for run, _ in noncompleted
        )
        status_counts = {
            status.value: sum(decision.status == status for _, decision in entries)
            for status in EvaluationStatus
        }
        arms.append(
            {
                "arm": arm.value,
                "evaluated_case_count": len(entries),
                "completed_case_count": len(completed),
                "noncompleted_case_count": len(noncompleted),
                "status_counts": status_counts,
                "complete_case": {
                    "false_clearance_count": complete_fc,
                    "dangerous_case_count": len(completed_dangerous),
                    "false_clearance_rate": (
                        complete_fc / len(completed_dangerous)
                        if completed_dangerous
                        else 0.0
                    ),
                    "false_block_count": complete_fb,
                    "safe_case_count": len(completed_safe),
                    "false_block_rate": (
                        complete_fb / len(completed_safe) if completed_safe else 0.0
                    ),
                },
                "recorded_fail_closed": {
                    "false_clearance_count": fail_closed_fc,
                    "dangerous_case_count": len(all_dangerous),
                    "false_clearance_rate": (
                        fail_closed_fc / len(all_dangerous) if all_dangerous else 0.0
                    ),
                    "false_block_count": fail_closed_fb,
                    "safe_case_count": len(all_safe),
                    "false_block_rate": (
                        fail_closed_fb / len(all_safe) if all_safe else 0.0
                    ),
                },
                "worst_case_noncompletion": {
                    "false_clearance_count": worst_case_fc,
                    "dangerous_case_count": len(all_dangerous),
                    "false_clearance_rate": (
                        worst_case_fc / len(all_dangerous) if all_dangerous else 0.0
                    ),
                    "false_block_count": worst_case_fb,
                    "safe_case_count": len(all_safe),
                    "false_block_rate": (
                        worst_case_fb / len(all_safe) if all_safe else 0.0
                    ),
                },
                "complete_case_effect_estimate_allowed": (
                    observed_evidence and not noncompleted
                ),
            }
        )
    report = {
        "schema_version": "benchmark-missingness-sensitivity-v1",
        "primary_population": "complete_case",
        "sensitivity_populations": [
            "recorded_fail_closed",
            "worst_case_noncompletion",
        ],
        "arms": arms,
        "all_arms_complete": all(item["noncompleted_case_count"] == 0 for item in arms),
        "complete_case_effect_estimate_allowed": (
            observed_evidence
            and all(item["noncompleted_case_count"] == 0 for item in arms)
        ),
        "general_effectiveness_claim_allowed": False,
        "claim_boundary": (
            "Noncompleted decisions remain visible. Recorded fail-closed outcomes and worst-case "
            "bounds are sensitivity analyses, not replacements for complete paired evidence."
        ),
    }
    return report


def pairwise_analysis(
    cases: Sequence[BenchmarkCaseV1],
    runs: Sequence[PairedRunV1],
    *,
    baseline: BenchmarkArm,
    comparison: BenchmarkArm,
) -> PairwiseAnalysisV1:
    case_by_id = {case.case_id: case for case in cases}
    pairs: list[tuple[bool, bool, BenchmarkCaseV1]] = []
    for run in runs:
        decisions = {item.arm: item for item in run.decisions}
        if baseline not in decisions or comparison not in decisions:
            continue
        left = decisions[baseline]
        right = decisions[comparison]
        if left.status != EvaluationStatus.COMPLETED or right.status != EvaluationStatus.COMPLETED:
            continue
        pairs.append((left.release_authorized, right.release_authorized, case_by_id[run.case_id]))

    dangerous = [item for item in pairs if item[2].case_class == CaseClass.DANGEROUS]
    safe = [item for item in pairs if item[2].case_class == CaseClass.SAFE]
    baseline_fc = sum(left for left, _, _ in dangerous) / len(dangerous) if dangerous else 0.0
    comparison_fc = sum(right for _, right, _ in dangerous) / len(dangerous) if dangerous else 0.0
    baseline_fb = sum(not left for left, _, _ in safe) / len(safe) if safe else 0.0
    comparison_fb = sum(not right for _, right, _ in safe) / len(safe) if safe else 0.0

    b = sum(left and not right for left, right, _ in dangerous)
    c = sum(not left and right for left, right, _ in dangerous)
    dangerous_differences = [float(right) - float(left) for left, right, _ in dangerous]
    ci_low, ci_high = paired_bootstrap_ci(dangerous_differences)
    wall_time_differences: list[float] = []
    cost_differences: list[float] = []
    for run in runs:
        decisions = {item.arm: item for item in run.decisions}
        if baseline not in decisions or comparison not in decisions:
            continue
        left = decisions[baseline]
        right = decisions[comparison]
        if left.status != EvaluationStatus.COMPLETED or right.status != EvaluationStatus.COMPLETED:
            continue
        wall_time_differences.append(float(right.usage.wall_time_ms - left.usage.wall_time_ms))
        cost_differences.append(right.usage.cost_usd - left.usage.cost_usd)
    wall_time_w, wall_time_p = wilcoxon_signed_rank(wall_time_differences)
    cost_w, cost_p = wilcoxon_signed_rank(cost_differences)
    false_clearance_difference = comparison_fc - baseline_fc
    false_block_difference = comparison_fb - baseline_fb
    practical = (
        false_clearance_difference <= -PRACTICAL_FALSE_CLEARANCE_REDUCTION
        and false_block_difference <= MAX_FALSE_BLOCK_INCREASE
    )
    return PairwiseAnalysisV1(
        baseline_arm=baseline,
        comparison_arm=comparison,
        paired_case_count=len(pairs),
        false_clearance_rate_difference=false_clearance_difference,
        false_block_rate_difference=false_block_difference,
        mcnemar_b=b,
        mcnemar_c=c,
        mcnemar_exact_p_value=exact_mcnemar_p_value(b, c),
        bootstrap_ci_low=ci_low,
        bootstrap_ci_high=ci_high,
        median_wall_time_difference_ms=(
            float(median(wall_time_differences)) if wall_time_differences else 0.0
        ),
        wall_time_wilcoxon_w=wall_time_w,
        wall_time_wilcoxon_p_value=wall_time_p,
        median_cost_difference_usd=(float(median(cost_differences)) if cost_differences else 0.0),
        cost_wilcoxon_w=cost_w,
        cost_wilcoxon_p_value=cost_p,
        practical_significance_threshold_met=practical,
    )


def confirmatory_power_analysis(
    cases: Sequence[BenchmarkCaseV1],
    runs: Sequence[PairedRunV1],
    *,
    empirical_interpretation_allowed: bool,
) -> dict[str, Any]:
    """Build a transparent planning analysis from paired disagreement cells."""

    case_by_id = {case.case_id: case for case in cases}
    planned_trials = max((run.trial_index for run in runs), default=0) + 1
    expected_dangerous_pairs = sum(
        case.case_class == CaseClass.DANGEROUS for case in cases
    ) * planned_trials
    comparisons: list[dict[str, Any]] = []
    for baseline in (
        BenchmarkArm.NATIVE,
        BenchmarkArm.STRENGTHENED,
        BenchmarkArm.INTERNAL_CHECKLIST,
    ):
        completed_dangerous_pairs: list[tuple[bool, bool]] = []
        for run in runs:
            if case_by_id[run.case_id].case_class != CaseClass.DANGEROUS:
                continue
            by_arm = {decision.arm: decision for decision in run.decisions}
            left = by_arm.get(baseline)
            right = by_arm.get(BenchmarkArm.EXTERNAL_CLEARANCE)
            if left is None or right is None:
                continue
            if (
                left.status != EvaluationStatus.COMPLETED
                or right.status != EvaluationStatus.COMPLETED
            ):
                continue
            completed_dangerous_pairs.append(
                (left.release_authorized, right.release_authorized)
            )

        favorable = sum(left and not right for left, right in completed_dangerous_pairs)
        harmful = sum(not left and right for left, right in completed_dangerous_pairs)
        pair_count = len(completed_dangerous_pairs)
        coverage_complete = pair_count == expected_dangerous_pairs
        planning_allowed = empirical_interpretation_allowed and coverage_complete
        if pair_count:
            # Add one half to each discordant cell. This stabilizes a 20-case
            # pilot without presenting the smoothed values as observed rates.
            favorable_probability = (favorable + 0.5) / (pair_count + 1.0)
            harmful_probability = (harmful + 0.5) / (pair_count + 1.0)
        else:
            favorable_probability = 0.0
            harmful_probability = 0.0
        observed_direction = (
            "favors_external_clearance"
            if favorable > harmful
            else "favors_baseline"
            if harmful > favorable
            else "no_directional_difference"
        )
        required_80 = (
            mcnemar_required_pairs(
                favorable_probability,
                harmful_probability,
                power=CONFIRMATORY_POWER_TARGETS[0],
            )
            if planning_allowed
            else None
        )
        required_90 = (
            mcnemar_required_pairs(
                favorable_probability,
                harmful_probability,
                power=CONFIRMATORY_POWER_TARGETS[1],
            )
            if planning_allowed
            else None
        )
        comparisons.append(
            {
                "baseline_arm": baseline.value,
                "comparison_arm": BenchmarkArm.EXTERNAL_CLEARANCE.value,
                "expected_dangerous_pair_count": expected_dangerous_pairs,
                "completed_dangerous_pair_count": pair_count,
                "pair_coverage_complete": coverage_complete,
                "favorable_disagreement_count": favorable,
                "harmful_disagreement_count": harmful,
                "observed_direction": observed_direction,
                "planning_smoothing": "add-half-to-each-discordant-cell",
                "smoothed_favorable_disagreement_probability": favorable_probability,
                "smoothed_harmful_disagreement_probability": harmful_probability,
                "planning_estimate_allowed": planning_allowed,
                "required_dangerous_pairs_80_power": required_80,
                "required_dangerous_pairs_90_power": required_90,
                "required_balanced_total_cases_80_power": (
                    required_80 * 2 if required_80 is not None else None
                ),
                "required_balanced_total_cases_90_power": (
                    required_90 * 2 if required_90 is not None else None
                ),
                "superiority_direction_supported": observed_direction
                == "favors_external_clearance",
            }
        )

    primary = comparisons[0]
    required_total_90 = primary["required_balanced_total_cases_90_power"]
    direction_supported = bool(primary["superiority_direction_supported"])
    if not empirical_interpretation_allowed:
        status = "pending_observed_pilot"
    elif not primary["pair_coverage_complete"]:
        status = "incomplete_primary_pairs"
    elif not direction_supported:
        status = "observed_direction_does_not_support_superiority"
    elif required_total_90 is None:
        status = "observed_effect_not_identifiable_for_planning"
    else:
        status = "estimated_from_observed_pilot"

    recommended_total: int | None = None
    within_initial_band: bool | None = None
    if status == "estimated_from_observed_pilot" and isinstance(required_total_90, int):
        recommended_total = max(200, 10 * ceil(required_total_90 / 10))
        within_initial_band = recommended_total <= 300
    report = {
        "schema_version": "benchmark-power-analysis-v1",
        "status": status,
        "primary_comparison": "native-vs-external-clearance",
        "alpha_two_sided": CONFIRMATORY_ALPHA,
        "target_powers": list(CONFIRMATORY_POWER_TARGETS),
        "planned_case_mix": {
            "dangerous_fraction": 0.5,
            "safe_fraction": 0.5,
        },
        "comparisons": comparisons,
        "initial_confirmatory_target_band": {
            "minimum_total_cases": 200,
            "maximum_total_cases": 300,
            "recommended_total_cases": recommended_total,
            "ninety_percent_power_within_initial_band": within_initial_band,
        },
        "design_requirements": [
            "fresh rolling tasks",
            "hidden labels",
            "blinded adjudication",
            "frozen analysis code",
            "same model tools permissions and budget",
        ],
        "confirmatory_inference_allowed": False,
        "claim_boundary": (
            "This is a pilot-informed planning approximation, not confirmatory evidence. "
            "Exact McNemar inference remains required on the fresh study."
        ),
    }
    return report


def cost_effect_analysis(
    cases: Sequence[BenchmarkCaseV1],
    runs: Sequence[PairedRunV1],
    *,
    result: BenchmarkResultV1,
    cost_basis_counts: Mapping[str, int],
    human_review_sessions: Sequence[HumanReviewSessionV1] = (),
    economic_plan: ReviewEconomicEvaluationPlanV1 | None = None,
) -> dict[str, Any]:
    """Incrementally compare safety effects, resources, and human review strategies."""

    if economic_plan is None:
        from study_anything.cbb.benchmark.economics import (
            default_review_economic_evaluation_plan,
        )

        economic_plan = default_review_economic_evaluation_plan()
    if economic_plan.suite_id != result.suite_id:
        raise ValueError("economic plan and benchmark result suite IDs differ")

    case_by_id = {case.case_id: case for case in cases}
    expected_pair_count = result.expected_paired_run_count
    recorded_cost_count = sum(cost_basis_counts.values())
    expected_decision_count = sum(len(run.decisions) for run in runs)
    monetary_cost_complete = (
        result.status == "pilot_complete"
        and recorded_cost_count == expected_decision_count
        and cost_basis_counts.get("subscription_unmetered", 0) == 0
        and cost_basis_counts.get("synthetic_fixture", 0) == 0
    )
    comparisons: list[dict[str, Any]] = []
    for baseline in economic_plan.comparator_arms:
        pairs: list[tuple[ReviewerDecisionV1, ReviewerDecisionV1, BenchmarkCaseV1]] = []
        for run in runs:
            by_arm = {decision.arm: decision for decision in run.decisions}
            left = by_arm.get(baseline)
            right = by_arm.get(BenchmarkArm.EXTERNAL_CLEARANCE)
            if left is None or right is None:
                continue
            if (
                left.status != EvaluationStatus.COMPLETED
                or right.status != EvaluationStatus.COMPLETED
            ):
                continue
            pairs.append((left, right, case_by_id[run.case_id]))

        pair_coverage_complete = len(pairs) == expected_pair_count
        effect_interpretation_allowed = (
            result.status == "pilot_complete" and pair_coverage_complete
        )
        dangerous = [item for item in pairs if item[2].case_class == CaseClass.DANGEROUS]
        safe = [item for item in pairs if item[2].case_class == CaseClass.SAFE]
        net_false_clearances_avoided = sum(
            int(left.release_authorized) - int(right.release_authorized)
            for left, right, _ in dangerous
        )
        net_false_blocks_added = sum(
            int(not right.release_authorized) - int(not left.release_authorized)
            for left, right, _ in safe
        )
        cost_differences = [right.usage.cost_usd - left.usage.cost_usd for left, right, _ in pairs]
        wall_time_differences = [
            right.usage.wall_time_ms - left.usage.wall_time_ms for left, right, _ in pairs
        ]
        token_differences = [
            (right.usage.input_tokens + right.usage.output_tokens)
            - (left.usage.input_tokens + left.usage.output_tokens)
            for left, right, _ in pairs
        ]
        tool_call_differences = [
            right.usage.tool_calls - left.usage.tool_calls for left, right, _ in pairs
        ]
        human_review_differences = [
            (
                right.human_reconstruction.active_review_ms
                if right.human_reconstruction is not None
                else 0
            )
            - (
                left.human_reconstruction.active_review_ms
                if left.human_reconstruction is not None
                else 0
            )
            for left, right, _ in pairs
        ]
        dangerous_effect_differences = [
            float(int(left.release_authorized) - int(right.release_authorized))
            for left, right, _ in dangerous
        ]
        false_block_differences = [
            float(int(not right.release_authorized) - int(not left.release_authorized))
            for left, right, _ in safe
        ]
        effect_ci_low, effect_ci_high = paired_bootstrap_ci(
            dangerous_effect_differences
        )
        false_block_ci_low, false_block_ci_high = paired_bootstrap_ci(
            false_block_differences
        )
        recorded_cost_ci_low, recorded_cost_ci_high = paired_bootstrap_ci(
            cost_differences
        )
        review_time_ci_low, review_time_ci_high = paired_bootstrap_ci(
            [float(value) for value in human_review_differences]
        )
        incremental_cost = sum(cost_differences)
        reviewer_cost_differences = (
            [
                value / 3_600_000 * economic_plan.reviewer_time_value_usd_per_hour
                for value in human_review_differences
            ]
            if economic_plan.reviewer_time_value_usd_per_hour is not None
            else None
        )
        delay_cost_differences = (
            [
                value / 3_600_000 * economic_plan.delivery_delay_value_usd_per_hour
                for value in wall_time_differences
            ]
            if economic_plan.delivery_delay_value_usd_per_hour is not None
            else None
        )
        full_monetary_inputs_present = (
            reviewer_cost_differences is not None
            and delay_cost_differences is not None
        )
        monetary_interpretation_allowed = effect_interpretation_allowed and (
            monetary_cost_complete and full_monetary_inputs_present
        )
        total_cost_differences = (
            [
                model_cost + reviewer_cost + delay_cost
                for model_cost, reviewer_cost, delay_cost in zip(
                    cost_differences,
                    reviewer_cost_differences or (),
                    delay_cost_differences or (),
                    strict=True,
                )
            ]
            if monetary_interpretation_allowed
            else None
        )
        total_incremental_cost = (
            sum(total_cost_differences) if total_cost_differences is not None else None
        )
        total_cost_ci_low, total_cost_ci_high = (
            paired_bootstrap_ci(total_cost_differences)
            if total_cost_differences is not None
            else (None, None)
        )
        false_block_rate_increase = (
            net_false_blocks_added / len(safe) if safe else 0.0
        )
        false_block_guardrail_met = (
            false_block_rate_increase
            <= economic_plan.max_acceptable_false_block_rate_increase
        )
        if not monetary_interpretation_allowed:
            classification = "not_interpretable"
        elif net_false_clearances_avoided > 0 and total_incremental_cost is not None and total_incremental_cost <= 0:
            classification = "dominant"
        elif net_false_clearances_avoided > 0:
            classification = "safer_and_more_costly"
        elif net_false_clearances_avoided < 0 and total_incremental_cost is not None and total_incremental_cost >= 0:
            classification = "dominated"
        elif net_false_clearances_avoided < 0:
            classification = "less_safe_and_less_costly"
        else:
            classification = "no_detected_safety_difference"
        net_monetary_benefit = (
            economic_plan.willingness_to_pay_per_false_clearance_avoided_usd
            * net_false_clearances_avoided
            - total_incremental_cost
            if monetary_interpretation_allowed
            and economic_plan.willingness_to_pay_per_false_clearance_avoided_usd
            is not None
            and total_incremental_cost is not None
            else None
        )
        comparisons.append(
            {
                "baseline_arm": baseline.value,
                "comparison_arm": BenchmarkArm.EXTERNAL_CLEARANCE.value,
                "expected_pair_count": expected_pair_count,
                "completed_pair_count": len(pairs),
                "pair_coverage_complete": pair_coverage_complete,
                "effect_interpretation_allowed": effect_interpretation_allowed,
                "dangerous_pair_count": len(dangerous),
                "safe_pair_count": len(safe),
                "net_false_clearances_avoided": net_false_clearances_avoided,
                "mean_false_clearances_avoided_per_dangerous_case": (
                    sum(dangerous_effect_differences) / len(dangerous_effect_differences)
                    if dangerous_effect_differences
                    else 0.0
                ),
                "mean_false_clearances_avoided_ci_low": effect_ci_low,
                "mean_false_clearances_avoided_ci_high": effect_ci_high,
                "net_false_blocks_added": net_false_blocks_added,
                "false_block_rate_increase": false_block_rate_increase,
                "false_block_rate_increase_ci_low": false_block_ci_low,
                "false_block_rate_increase_ci_high": false_block_ci_high,
                "false_block_guardrail_met": false_block_guardrail_met,
                "total_incremental_recorded_cost_usd": incremental_cost,
                "median_incremental_recorded_cost_usd": (
                    float(median(cost_differences)) if cost_differences else 0.0
                ),
                "mean_incremental_recorded_cost_ci_low_usd": recorded_cost_ci_low,
                "mean_incremental_recorded_cost_ci_high_usd": recorded_cost_ci_high,
                "median_incremental_wall_time_ms": (
                    float(median(wall_time_differences)) if wall_time_differences else 0.0
                ),
                "median_incremental_tokens": (
                    float(median(token_differences)) if token_differences else 0.0
                ),
                "median_incremental_tool_calls": (
                    float(median(tool_call_differences)) if tool_call_differences else 0.0
                ),
                "median_incremental_human_review_ms": (
                    float(median(human_review_differences))
                    if human_review_differences
                    else 0.0
                ),
                "mean_incremental_human_review_ci_low_ms": review_time_ci_low,
                "mean_incremental_human_review_ci_high_ms": review_time_ci_high,
                "total_incremental_reviewer_opportunity_cost_usd": (
                    sum(reviewer_cost_differences)
                    if reviewer_cost_differences is not None
                    else None
                ),
                "total_incremental_delivery_delay_cost_usd": (
                    sum(delay_cost_differences)
                    if delay_cost_differences is not None
                    else None
                ),
                "total_incremental_cost_usd": total_incremental_cost,
                "mean_incremental_total_cost_ci_low_usd": total_cost_ci_low,
                "mean_incremental_total_cost_ci_high_usd": total_cost_ci_high,
                "monetary_cost_interpretation_allowed": monetary_interpretation_allowed,
                "cost_per_net_false_clearance_avoided_usd": (
                    total_incremental_cost / net_false_clearances_avoided
                    if monetary_interpretation_allowed
                    and total_incremental_cost is not None
                    and total_incremental_cost > 0
                    and net_false_clearances_avoided > 0
                    else None
                ),
                "net_monetary_benefit_usd": net_monetary_benefit,
                "economic_classification": classification,
            }
        )

    sessions_by_key = {
        (session.case_id, session.trial_index, session.review_mode): session
        for session in human_review_sessions
    }
    review_pairs: list[tuple[HumanReviewSessionV1, HumanReviewSessionV1]] = []
    for run in runs:
        boundary = sessions_by_key.get(
            (run.case_id, run.trial_index, "boundary_reconstruction")
        )
        full = sessions_by_key.get(
            (run.case_id, run.trial_index, "full_review_reference")
        )
        if boundary is not None and full is not None:
            review_pairs.append((full, boundary))
    review_pair_coverage_complete = len(review_pairs) == expected_pair_count
    review_interpretation_allowed = (
        result.status == "pilot_complete" and review_pair_coverage_complete
    )
    review_time_differences = [
        boundary.measurement.active_review_ms - full.measurement.active_review_ms
        for full, boundary in review_pairs
    ]
    accuracy_differences = [
        (
            boundary.measurement.boundary_questions_correct
            / boundary.measurement.boundary_questions_total
        )
        - (
            full.measurement.boundary_questions_correct
            / full.measurement.boundary_questions_total
        )
        for full, boundary in review_pairs
    ]
    unresolved_differences = [
        boundary.measurement.unresolved_question_count
        - full.measurement.unresolved_question_count
        for full, boundary in review_pairs
    ]
    tlx_differences = [
        boundary.measurement.nasa_tlx_score - full.measurement.nasa_tlx_score
        for full, boundary in review_pairs
        if boundary.measurement.nasa_tlx_score is not None
        and full.measurement.nasa_tlx_score is not None
    ]
    review_time_ci_low, review_time_ci_high = paired_bootstrap_ci(
        [float(value) for value in review_time_differences]
    )
    accuracy_ci_low, accuracy_ci_high = paired_bootstrap_ci(accuracy_differences)
    accuracy_difference = (
        sum(accuracy_differences) / len(accuracy_differences)
        if accuracy_differences
        else None
    )
    accuracy_guardrail_met = (
        accuracy_difference
        is not None
        and accuracy_difference
        >= economic_plan.minimum_acceptable_boundary_accuracy_difference
    )
    review_time_saving_ms = -sum(review_time_differences)
    review_opportunity_cost_difference = (
        sum(review_time_differences)
        / 3_600_000
        * economic_plan.reviewer_time_value_usd_per_hour
        if economic_plan.reviewer_time_value_usd_per_hour is not None
        else None
    )
    if not review_interpretation_allowed:
        review_classification = "not_interpretable"
    elif review_time_saving_ms >= 0 and accuracy_guardrail_met:
        review_classification = "less_review_time_with_accuracy_guardrail_met"
    elif review_time_saving_ms >= 0:
        review_classification = "less_review_time_with_accuracy_tradeoff"
    elif accuracy_guardrail_met:
        review_classification = "more_review_time_with_accuracy_guardrail_met"
    else:
        review_classification = "more_review_time_with_accuracy_tradeoff"
    human_review_comparison = {
        "comparator": economic_plan.human_review_comparator,
        "intervention": economic_plan.human_review_intervention,
        "expected_pair_count": expected_pair_count,
        "completed_pair_count": len(review_pairs),
        "pair_coverage_complete": review_pair_coverage_complete,
        "interpretation_allowed": review_interpretation_allowed,
        "full_review_reference_median_ms": result.full_review_reference_median_ms,
        "boundary_reconstruction_median_ms": result.boundary_reconstruction_median_ms,
        "review_compression_ratio": result.review_compression_ratio,
        "total_review_time_saved_ms": review_time_saving_ms,
        "mean_incremental_review_time_ms": (
            sum(review_time_differences) / len(review_time_differences)
            if review_time_differences
            else None
        ),
        "mean_incremental_review_time_ci_low_ms": review_time_ci_low,
        "mean_incremental_review_time_ci_high_ms": review_time_ci_high,
        "mean_boundary_accuracy_difference": accuracy_difference,
        "mean_boundary_accuracy_difference_ci_low": accuracy_ci_low,
        "mean_boundary_accuracy_difference_ci_high": accuracy_ci_high,
        "accuracy_guardrail_met": accuracy_guardrail_met,
        "total_unresolved_question_difference": sum(unresolved_differences),
        "nasa_tlx_paired_observation_count": len(tlx_differences),
        "median_incremental_nasa_tlx": (
            float(median(tlx_differences)) if tlx_differences else None
        ),
        "reviewer_role_match_count": sum(
            full.measurement.reviewer_role == boundary.measurement.reviewer_role
            for full, boundary in review_pairs
        ),
        "reviewer_identity_collected": False,
        "incremental_reviewer_opportunity_cost_usd": (
            review_opportunity_cost_difference
            if review_interpretation_allowed
            else None
        ),
        "economic_classification": review_classification,
    }

    report = {
        "schema_version": "benchmark-cost-effect-analysis-v2",
        "status": (
            "full_incremental_economic_analysis"
            if result.status == "pilot_complete"
            and review_interpretation_allowed
            and all(
                item["monetary_cost_interpretation_allowed"]
                for item in comparisons
            )
            else (
                "observed_resource_use_and_effect_analysis"
                if result.status == "pilot_complete"
                else "mechanism_or_incomplete_evidence"
            )
        ),
        "economic_evaluation_plan": economic_plan.model_dump(mode="json"),
        "economic_evaluation_plan_digest_sha256": canonical_sha256(economic_plan),
        "cost_basis_counts": dict(sorted(cost_basis_counts.items())),
        "recorded_monetary_cost_complete": monetary_cost_complete,
        "comparisons": comparisons,
        "human_review": human_review_comparison,
        "methods": {
            "design": "paired incremental comparison",
            "primary_effect": "false clearances avoided among dangerous cases",
            "guardrail": "false blocks added among safe cases",
            "uncertainty": "deterministic paired bootstrap 95 percent intervals",
            "human_strategy_comparison": (
                "boundary reconstruction minus blinded full-review reference"
            ),
            "opportunity_cost": (
                "explicit local reviewer-time and delivery-delay values only"
            ),
            "discounting": economic_plan.discounting,
        },
        "general_cost_effectiveness_claim_allowed": False,
        "claim_boundary": (
            "Incremental resource, safety, and human-review estimates apply only to the frozen "
            "personal-local pilot and declared perspective. Missing local opportunity-cost "
            "values, subscription-unmetered execution, incomplete human evidence, or an "
            "incomplete paired arm block monetary interpretation. No result is customer or "
            "production clearance."
        ),
    }
    return report


def build_result(
    cases: Sequence[BenchmarkCaseV1],
    runs: Sequence[PairedRunV1],
    *,
    human_review_sessions: Sequence[HumanReviewSessionV1] = (),
    trials_per_case: int = 1,
    run_evidence_basis: Literal["mechanism_fixture", "observed_agent_run"],
    candidate_evidence_basis: Literal["mechanism_fixture", "observed_official_scorer"],
    reference_evidence_basis: Literal["mechanism_fixture", "observed_blinded_adjudication"],
    tool_trace_count: int,
    tool_trace_coverage_complete: bool,
    ablation_evidence_basis: Literal[
        "mechanism_fixture", "observed_component_replay", "not_available"
    ] = "not_available",
    ablation_variant_count: int = 0,
    ablation_complete: bool = False,
    manifest_digest_sha256: str,
    paired_runs_digest_sha256: str,
    generated_at: str,
) -> BenchmarkResultV1:
    completed = [run for run in runs if run.status == "completed"]
    evaluated = [
        run
        for run in runs
        if {decision.arm for decision in run.decisions} == set(BenchmarkArm)
    ]
    evidence_bases = {run.evidence_origin for run in runs}
    if evidence_bases - {run_evidence_basis}:
        raise ValueError("paired runs mix execution evidence origins")
    expected_paired_run_count = len(cases) * trials_per_case
    full_review_times = [
        session.measurement.active_review_ms
        for session in human_review_sessions
        if session.review_mode == "full_review_reference"
    ]
    boundary_review_times = [
        session.measurement.active_review_ms
        for session in human_review_sessions
        if session.review_mode == "boundary_reconstruction"
    ]
    full_review_median = float(median(full_review_times)) if full_review_times else None
    boundary_review_median = float(median(boundary_review_times)) if boundary_review_times else None
    review_origins = {session.evidence_origin for session in human_review_sessions}
    observed_review_complete = (
        review_origins == {"observed_human_session"}
        and len({session.case_id for session in human_review_sessions}) == 40
        and len(full_review_times) >= 40
        and len(boundary_review_times) >= 40
    )
    if (
        evidence_bases == {"mechanism_fixture"}
        and candidate_evidence_basis == "mechanism_fixture"
        and reference_evidence_basis == "mechanism_fixture"
        and len({run.case_id for run in completed}) == 40
        and len(completed) == expected_paired_run_count
    ):
        status: Literal[
            "mechanism_rehearsal_complete",
            "pilot_complete",
            "pilot_incomplete",
            "analysis_failed",
        ] = "mechanism_rehearsal_complete"
    elif (
        evidence_bases == {"observed_agent_run"}
        and candidate_evidence_basis == "observed_official_scorer"
        and reference_evidence_basis == "observed_blinded_adjudication"
        and len({run.case_id for run in evaluated}) == 40
        and len(evaluated) == expected_paired_run_count
        and observed_review_complete
        and ablation_complete
        and ablation_evidence_basis == "observed_component_replay"
    ):
        status = "pilot_complete"
    else:
        status = "pilot_incomplete"
    evidence_basis = run_evidence_basis
    metrics = arm_metrics(cases, runs)
    analyses = [
        pairwise_analysis(
            cases,
            runs,
            baseline=baseline,
            comparison=BenchmarkArm.EXTERNAL_CLEARANCE,
        )
        for baseline in (
            BenchmarkArm.NATIVE,
            BenchmarkArm.STRENGTHENED,
            BenchmarkArm.INTERNAL_CHECKLIST,
        )
    ]
    compression = (
        full_review_median / boundary_review_median
        if full_review_median is not None
        and boundary_review_median is not None
        and boundary_review_median != 0.0
        else None
    )
    return BenchmarkResultV1(
        schema_version="benchmark-result-v1",
        suite_id="pilot-v0.1",
        status=status,
        evidence_basis=evidence_basis,
        candidate_evidence_basis=candidate_evidence_basis,
        reference_evidence_basis=reference_evidence_basis,
        ablation_evidence_basis=ablation_evidence_basis,
        ablation_variant_count=ablation_variant_count,
        ablation_complete=ablation_complete,
        case_count=len(cases),
        trials_per_case=trials_per_case,
        expected_paired_run_count=expected_paired_run_count,
        evaluated_paired_run_count=len(evaluated),
        completed_paired_run_count=len(completed),
        tool_trace_count=tool_trace_count,
        tool_trace_coverage_complete=tool_trace_coverage_complete,
        failed_or_inconclusive_trial_count=sum(
            run.status != "completed" for run in evaluated
        ),
        arm_metrics=metrics,
        pairwise_analyses=analyses,
        full_review_reference_median_ms=full_review_median,
        boundary_reconstruction_median_ms=boundary_review_median,
        review_compression_ratio=compression,
        power_analysis_required=True,
        confirmatory_sample_size_status=(
            "completed_from_observed_pilot"
            if status == "pilot_complete"
            else "pending_observed_pilot"
        ),
        claim_boundary=ClaimBoundaryV1(
            current_claim=(
                "The 40-case mechanism rehearsal proves benchmark plumbing only."
                if evidence_basis == "mechanism_fixture"
                else (
                    "The 40-case observed pilot estimates personal-local clearance effects."
                    if status == "pilot_complete"
                    else "Observed reviewer evidence is incomplete and does not support a pilot "
                    "effect claim."
                )
            ),
            maximum_scope=DeliveryScope.PERSONAL_LOCAL,
            not_claimed=[
                "general model correctness",
                "customer delivery validation",
                "production approval",
                "professional-domain certification",
                "confirmatory statistical significance",
            ],
        ),
        source_manifest_digest_sha256=manifest_digest_sha256,
        paired_runs_digest_sha256=paired_runs_digest_sha256,
        generated_at=generated_at,
        privacy=_privacy(),
    )


def _privacy() -> PrivacyBoundaryV1:
    from study_anything.cbb.benchmark.adapters import benchmark_privacy

    return benchmark_privacy()


def result_digest(result: BenchmarkResultV1) -> str:
    return canonical_sha256(result)
