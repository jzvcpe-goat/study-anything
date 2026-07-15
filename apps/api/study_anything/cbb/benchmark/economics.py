"""Economic evaluation plans and aggregate human-evidence readiness."""

from __future__ import annotations

from collections import Counter
from statistics import mean, median
from typing import Any, Sequence

from study_anything.cbb.benchmark.models import (
    BenchmarkArm,
    BlindedAdjudicationReceiptV1,
    HumanReviewSessionV1,
    ReviewEconomicEvaluationPlanV1,
)
from study_anything.cbb.protocol.canonical import assert_safe_metadata
from study_anything.cbb.protocol.models import DeliveryScope


def default_review_economic_evaluation_plan() -> ReviewEconomicEvaluationPlanV1:
    """Return the unpriced personal-local plan used by deterministic rehearsals."""

    return ReviewEconomicEvaluationPlanV1(
        schema_version="review-economic-evaluation-plan-v1",
        plan_id="economic-plan:pilot-v0.1:personal-local",
        suite_id="pilot-v0.1",
        evaluation_perspective="local_project_owner",
        intervention_arm=BenchmarkArm.EXTERNAL_CLEARANCE,
        comparator_arms=[
            BenchmarkArm.NATIVE,
            BenchmarkArm.STRENGTHENED,
            BenchmarkArm.INTERNAL_CHECKLIST,
        ],
        human_review_intervention="boundary_reconstruction",
        human_review_comparator="full_review_reference",
        primary_outcome="false_clearances_avoided",
        guardrail_outcome="false_blocks_added",
        time_horizon="single_delivery_review",
        discounting="not_applicable",
        currency="USD",
        price_date=None,
        reviewer_time_value_usd_per_hour=None,
        delivery_delay_value_usd_per_hour=None,
        willingness_to_pay_per_false_clearance_avoided_usd=None,
        max_acceptable_false_block_rate_increase=0.05,
        minimum_acceptable_boundary_accuracy_difference=-0.05,
        raw_human_answers_included=False,
        general_cost_effectiveness_claim_allowed=False,
        maximum_scope=DeliveryScope.PERSONAL_LOCAL,
        claim_boundary=(
            "This plan compares incremental resource use and observed review outcomes for the "
            "frozen personal-local pilot. Monetary or general cost-effectiveness conclusions "
            "remain blocked until local opportunity costs are explicitly supplied and observed "
            "human evidence is complete."
        ),
    )


def human_evidence_status(
    expected_case_ids: Sequence[str],
    sessions: Sequence[HumanReviewSessionV1],
    adjudications: Sequence[BlindedAdjudicationReceiptV1],
    *,
    trial_index: int = 0,
) -> dict[str, Any]:
    """Summarize whether the real, blinded human evidence is ready for analysis."""

    expected = set(expected_case_ids)
    if not expected:
        raise ValueError("human evidence status requires at least one expected case")
    if len(expected) != len(expected_case_ids):
        raise ValueError("human evidence status received duplicate expected cases")

    relevant_sessions = [
        session
        for session in sessions
        if session.trial_index == trial_index and session.case_id in expected
    ]
    boundary_by_case = {
        session.case_id: session
        for session in relevant_sessions
        if session.review_mode == "boundary_reconstruction"
    }
    full_by_case = {
        session.case_id: session
        for session in relevant_sessions
        if session.review_mode == "full_review_reference"
    }
    adjudication_by_case = {
        receipt.case_id: receipt for receipt in adjudications if receipt.case_id in expected
    }
    session_keys = [
        (session.case_id, session.trial_index, session.review_mode)
        for session in relevant_sessions
    ]
    adjudication_case_ids = [
        receipt.case_id for receipt in adjudications if receipt.case_id in expected
    ]
    duplicate_session_key_count = len(session_keys) - len(set(session_keys))
    duplicate_adjudication_case_count = len(adjudication_case_ids) - len(
        set(adjudication_case_ids)
    )
    unexpected_session_case_ids = sorted(
        {session.case_id for session in sessions} - expected
    )
    unexpected_adjudication_case_ids = sorted(
        {receipt.case_id for receipt in adjudications} - expected
    )
    missing_boundary = sorted(expected - set(boundary_by_case))
    missing_full = sorted(expected - set(full_by_case))
    missing_adjudication = sorted(expected - set(adjudication_by_case))
    non_observed_session_count = sum(
        session.evidence_origin != "observed_human_session"
        for session in relevant_sessions
    )
    complete_case_count = sum(
        case_id in boundary_by_case
        and case_id in full_by_case
        and case_id in adjudication_by_case
        for case_id in expected
    )
    ready = not any(
        (
            missing_boundary,
            missing_full,
            missing_adjudication,
            unexpected_session_case_ids,
            unexpected_adjudication_case_ids,
        )
    ) and not any(
        (
            duplicate_session_key_count,
            duplicate_adjudication_case_count,
            non_observed_session_count,
        )
    )

    def _mode_summary(items: Sequence[HumanReviewSessionV1]) -> dict[str, Any]:
        measurements = [item.measurement for item in items]
        return {
            "session_count": len(items),
            "median_active_review_ms": (
                float(median(item.active_review_ms for item in measurements))
                if measurements
                else None
            ),
            "mean_boundary_accuracy": (
                float(
                    mean(
                        item.boundary_questions_correct / item.boundary_questions_total
                        for item in measurements
                    )
                )
                if measurements
                else None
            ),
            "unresolved_question_count": sum(
                item.unresolved_question_count for item in measurements
            ),
            "nasa_tlx_observation_count": sum(
                item.nasa_tlx_score is not None for item in measurements
            ),
            "reviewer_role_counts": dict(
                sorted(Counter(item.reviewer_role for item in measurements).items())
            ),
        }

    report = {
        "schema_version": "human-evidence-status-v1",
        "status": "ready" if ready else "incomplete",
        "suite_id": "pilot-v0.1",
        "trial_index": trial_index,
        "expected_case_count": len(expected),
        "complete_case_count": complete_case_count,
        "required": {
            "boundary_reconstruction_sessions": len(expected),
            "full_review_reference_sessions": len(expected),
            "blinded_adjudications": len(expected),
        },
        "observed": {
            "boundary_reconstruction": _mode_summary(list(boundary_by_case.values())),
            "full_review_reference": _mode_summary(list(full_by_case.values())),
            "blinded_adjudication_count": len(adjudication_by_case),
        },
        "missing": {
            "boundary_reconstruction_case_ids": missing_boundary,
            "full_review_reference_case_ids": missing_full,
            "blinded_adjudication_case_ids": missing_adjudication,
        },
        "integrity": {
            "duplicate_session_key_count": duplicate_session_key_count,
            "duplicate_adjudication_case_count": duplicate_adjudication_case_count,
            "non_observed_session_count": non_observed_session_count,
            "unexpected_session_case_ids": unexpected_session_case_ids,
            "unexpected_adjudication_case_ids": unexpected_adjudication_case_ids,
        },
        "ready_for_incremental_economic_evaluation": ready,
        "raw_answers_included": False,
        "reviewer_identity_collected": False,
        "maximum_scope": "personal_local",
        "claim_boundary": (
            "Readiness means the blinded human evidence inventory is complete and aggregate-only. "
            "It does not establish effectiveness, cost-effectiveness, reviewer independence, "
            "customer clearance, or production approval."
        ),
    }
    assert_safe_metadata(report, label="human evidence status")
    return report
