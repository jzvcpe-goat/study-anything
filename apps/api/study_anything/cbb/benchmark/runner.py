"""Deterministic runner and observed-run importer for the paired benchmark."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Literal, Sequence, TypeVar

from pydantic import BaseModel

from study_anything.cbb.benchmark.ablation import validate_ablation_observation
from study_anything.cbb.benchmark.adapters import PILOT_SUITE_ID, benchmark_privacy
from study_anything.cbb.benchmark.fixtures import (
    benchmark_manifest,
    pilot_assets,
    validate_pilot_assets,
)
from study_anything.cbb.benchmark.economics import (
    default_review_economic_evaluation_plan,
)
from study_anything.cbb.benchmark.metrics import (
    build_result,
    confirmatory_power_analysis,
    cost_effect_analysis,
    missingness_sensitivity,
)
from study_anything.cbb.benchmark.models import (
    AblationObservationV1,
    AblationVariant,
    BenchmarkArm,
    BenchmarkCaseV1,
    BenchmarkResultV1,
    BlindedAdjudicationReceiptV1,
    CandidateDeliveryV1,
    ClearanceDisposition,
    DecisionToolTraceV1,
    EvaluationStatus,
    FairnessEnvelopeV1,
    HumanReconstructionMeasurementV1,
    HumanReviewSessionV1,
    PairedRunV1,
    ResourceBudgetV1,
    ResourceUsageV1,
    ReviewEconomicEvaluationPlanV1,
    ReviewEntryRoute,
    ReviewExecutionProvenanceV1,
    ReviewPresentationProfile,
    ReviewerDecisionV1,
    ScorerExecutionReceiptV1,
    ToolCallObservationV1,
)
from study_anything.cbb.benchmark.reports import render_html_report, render_markdown_report
from study_anything.cbb.protocol.canonical import (
    assert_safe_metadata,
    canonical_sha256,
    pretty_json,
)
from study_anything.cbb.protocol.models import DeliveryScope


BENCHMARK_TIMESTAMP = "2026-07-12T00:00:00Z"
MECHANISM_MODEL_REF = "deterministic-mechanism-fixture"
MECHANISM_MODEL_VERSION = "v0.1"
DEFAULT_ARMS = tuple(BenchmarkArm)
DEFAULT_BUDGET = ResourceBudgetV1(
    max_input_tokens=8_000,
    max_output_tokens=2_000,
    max_tool_calls=12,
    max_wall_time_ms=120_000,
    max_cost_usd=1.0,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class BenchmarkRunnerError(ValueError):
    """Raised when paired benchmark inputs violate the frozen methodology."""


def _json_line(model: BaseModel) -> str:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _write_jsonl(path: Path, models: Iterable[BaseModel]) -> None:
    lines = [_json_line(model) for model in models]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _load_jsonl(path: Path, model_type: type[ModelT]) -> list[ModelT]:
    loaded: list[ModelT] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        assert_safe_metadata(payload, label=f"{path.name}:{line_number}")
        loaded.append(model_type.model_validate(payload))
    return loaded


def _usage_for(arm: BenchmarkArm, case_index: int, trial_index: int) -> ResourceUsageV1:
    arm_offset = {
        BenchmarkArm.NATIVE: 0,
        BenchmarkArm.STRENGTHENED: 1,
        BenchmarkArm.INTERNAL_CHECKLIST: 2,
        BenchmarkArm.EXTERNAL_CLEARANCE: 3,
    }[arm]
    return ResourceUsageV1(
        input_tokens=2_000 + case_index * 3 + arm_offset * 140,
        output_tokens=350 + arm_offset * 45,
        tool_calls=2 + arm_offset,
        wall_time_ms=1_000 + case_index * 11 + trial_index * 7 + arm_offset * 240,
        cost_usd=round(0.01 + arm_offset * 0.003, 6),
    )


def tool_trace_digest(trace: DecisionToolTraceV1) -> str:
    payload = trace.model_dump(mode="json")
    payload.pop("trace_digest_sha256")
    return canonical_sha256(payload)


def fixture_tool_trace(
    case: BenchmarkCaseV1,
    candidate: CandidateDeliveryV1,
    *,
    arm: BenchmarkArm,
    case_index: int,
    trial_index: int,
) -> DecisionToolTraceV1:
    usage = _usage_for(arm, case_index, trial_index)
    calls = [
        ToolCallObservationV1(
            sequence=sequence,
            tool_permission_id=candidate.tool_permission_ids[
                sequence % len(candidate.tool_permission_ids)
            ],
            status="completed",
            wall_time_ms=max(1, usage.wall_time_ms // max(1, usage.tool_calls)),
            input_metadata_digest_sha256=canonical_sha256(
                {
                    "case_id": case.case_id,
                    "arm": arm.value,
                    "trial_index": trial_index,
                    "sequence": sequence,
                    "direction": "input",
                }
            ),
            output_metadata_digest_sha256=canonical_sha256(
                {
                    "case_id": case.case_id,
                    "arm": arm.value,
                    "trial_index": trial_index,
                    "sequence": sequence,
                    "direction": "output",
                }
            ),
            raw_arguments_included=False,
            raw_output_included=False,
        )
        for sequence in range(usage.tool_calls)
    ]
    payload = {
        "schema_version": "decision-tool-trace-v1",
        "decision_id": f"decision:{case.case_id}:{trial_index}:{arm.value}",
        "suite_id": PILOT_SUITE_ID,
        "case_id": case.case_id,
        "trial_index": trial_index,
        "arm": arm.value,
        "evidence_origin": "mechanism_fixture",
        "model_ref": MECHANISM_MODEL_REF,
        "model_version": MECHANISM_MODEL_VERSION,
        "calls": [call.model_dump(mode="json") for call in calls],
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }
    return DecisionToolTraceV1.model_validate(
        {**payload, "trace_digest_sha256": canonical_sha256(payload)}
    )


def _fixture_measurement(case_index: int, trial_index: int) -> HumanReconstructionMeasurementV1:
    return HumanReconstructionMeasurementV1(
        reviewer_role="mechanism-fixture-reviewer",
        qualification_scope=DeliveryScope.PERSONAL_LOCAL,
        active_review_ms=12_000 + case_index * 50 + trial_index * 10,
        boundary_questions_total=5,
        boundary_questions_correct=5,
        unresolved_question_count=0,
        nasa_tlx_score=35.0,
        raw_answers_included=False,
        passive_attention_only=False,
    )


def fixture_decision(
    case: BenchmarkCaseV1,
    candidate: CandidateDeliveryV1,
    *,
    arm: BenchmarkArm,
    case_index: int,
    trial_index: int,
) -> ReviewerDecisionV1:
    """Exercise all decision contracts without making an effectiveness claim."""

    blocking_failures = [
        item.summary_code
        for item in candidate.evidence
        if item.blocking and item.status.value != "passed"
    ]
    release_authorized = not blocking_failures
    producing_agent_controls_gate = arm != BenchmarkArm.EXTERNAL_CLEARANCE
    trace = fixture_tool_trace(
        case,
        candidate,
        arm=arm,
        case_index=case_index,
        trial_index=trial_index,
    )
    return ReviewerDecisionV1(
        schema_version="reviewer-decision-v1",
        decision_id=f"decision:{case.case_id}:{trial_index}:{arm.value}",
        suite_id=PILOT_SUITE_ID,
        case_id=case.case_id,
        candidate_digest_sha256=canonical_sha256(candidate),
        arm=arm,
        trial_index=trial_index,
        evidence_origin="mechanism_fixture",
        tool_trace_digest_sha256=trace.trace_digest_sha256,
        status=EvaluationStatus.COMPLETED,
        disposition=(
            ClearanceDisposition.CLEARED if release_authorized else ClearanceDisposition.HELD
        ),
        release_authorized=release_authorized,
        approved_scope=(
            DeliveryScope.PERSONAL_LOCAL if release_authorized else DeliveryScope.BLOCKED
        ),
        reason_codes=blocking_failures or ["all-blocking-evidence-passed"],
        requested_evidence=[],
        model_ref=MECHANISM_MODEL_REF,
        model_version=MECHANISM_MODEL_VERSION,
        harness_ref=f"benchmark-arm:{arm.value}:mechanism-fixture",
        tool_permission_ids=list(candidate.tool_permission_ids),
        context_digest_sha256=candidate.context_digest_sha256,
        budget=DEFAULT_BUDGET,
        usage=_usage_for(arm, case_index, trial_index),
        random_seed=20260712 + trial_index,
        hidden_labels_accessible=False,
        hidden_tests_accessible=False,
        producing_agent_can_modify_final_gate=producing_agent_controls_gate,
        producing_agent_can_approve_own_output=producing_agent_controls_gate,
        human_reconstruction=(
            _fixture_measurement(case_index, trial_index)
            if arm == BenchmarkArm.EXTERNAL_CLEARANCE
            else None
        ),
        completed_at=BENCHMARK_TIMESTAMP,
        privacy=benchmark_privacy(),
    )


def _fairness_envelope() -> FairnessEnvelopeV1:
    return FairnessEnvelopeV1(
        same_candidate=True,
        same_model_and_version=True,
        same_context=True,
        same_tool_permissions=True,
        same_budget=True,
        cost_normalized_comparison=False,
        isolated_workspaces=True,
        isolated_memories=True,
        hidden_labels_withheld=True,
        hidden_tests_withheld=True,
        fixed_seed_where_supported=True,
        native_control_not_weakened=True,
    )


def paired_run(
    case: BenchmarkCaseV1,
    candidate: CandidateDeliveryV1,
    decisions: Sequence[ReviewerDecisionV1],
    *,
    trial_index: int,
    evidence_origin: Literal["mechanism_fixture", "observed_agent_run"],
) -> PairedRunV1:
    statuses = {decision.status for decision in decisions}
    if statuses == {EvaluationStatus.COMPLETED} and set(
        decision.arm for decision in decisions
    ) == set(DEFAULT_ARMS):
        run_status: Literal["completed", "incomplete", "failed"] = "completed"
    elif EvaluationStatus.FAILED in statuses:
        run_status = "failed"
    else:
        run_status = "incomplete"
    completed_times = sorted(decision.completed_at for decision in decisions)
    return PairedRunV1(
        schema_version="paired-run-v1",
        run_id=f"pair:{case.case_id}:{trial_index}",
        suite_id=PILOT_SUITE_ID,
        case_id=case.case_id,
        candidate_digest_sha256=canonical_sha256(candidate),
        trial_index=trial_index,
        evidence_origin=evidence_origin,
        status=run_status,
        decisions=list(decisions),
        fairness=_fairness_envelope(),
        started_at=completed_times[0] if completed_times else BENCHMARK_TIMESTAMP,
        completed_at=(completed_times[-1] if run_status == "completed" else None),
        resume_key=f"{PILOT_SUITE_ID}:{case.case_id}:{trial_index}",
        privacy=benchmark_privacy(),
    )


def fixture_human_sessions(
    cases: Sequence[BenchmarkCaseV1], trials: int
) -> list[HumanReviewSessionV1]:
    sessions: list[HumanReviewSessionV1] = []
    for case_index, case in enumerate(cases):
        for trial_index in range(trials):
            boundary = _fixture_measurement(case_index, trial_index)
            full = boundary.model_copy(
                update={
                    "active_review_ms": 60_000 + case_index * 150 + trial_index * 20,
                    "nasa_tlx_score": 58.0,
                }
            )
            review_records: tuple[
                tuple[
                    Literal["full_review_reference", "boundary_reconstruction"],
                    HumanReconstructionMeasurementV1,
                ],
                ...,
            ] = (
                ("full_review_reference", full),
                ("boundary_reconstruction", boundary),
            )
            for review_mode, measurement in review_records:
                sessions.append(
                    HumanReviewSessionV1(
                        schema_version="human-review-session-v1",
                        session_id=f"review:{case.case_id}:{trial_index}:{review_mode}",
                        suite_id=PILOT_SUITE_ID,
                        case_id=case.case_id,
                        trial_index=trial_index,
                        review_mode=review_mode,
                        evidence_origin="mechanism_fixture",
                        collection_method="mechanism_fixture",
                        candidate_digest_sha256=None,
                        review_material_digest_sha256=None,
                        question_set_digest_sha256=None,
                        measurement_trace_digest_sha256=None,
                        measurement=measurement,
                        completed_at=BENCHMARK_TIMESTAMP,
                        privacy=benchmark_privacy(),
                    )
                )
    return sessions


def fixture_ablation(cases: Sequence[BenchmarkCaseV1], trials: int) -> list[AblationObservationV1]:
    flags = {
        AblationVariant.NATIVE_ONLY: (False, False, False, False, False),
        AblationVariant.DETERMINISTIC_CHECKS: (True, False, False, False, False),
        AblationVariant.HUMAN_RECONSTRUCTION: (False, True, False, False, False),
        AblationVariant.RECEIPT: (False, False, True, False, False),
        AblationVariant.PROPAGATION_GATE: (True, False, True, True, True),
        AblationVariant.FULL_CLEARANCE: (True, True, True, True, True),
    }
    observations: list[AblationObservationV1] = []
    for case in cases:
        for trial_index in range(trials):
            for variant, component_flags in flags.items():
                deterministic, human, receipt, independent, propagation = component_flags
                enforceable = deterministic or human or propagation
                authorized = case.reference.release_authorized or not enforceable
                component_policy_digest = canonical_sha256(
                    {
                        "schema_version": "ablation-component-policy-v1",
                        "variant": variant.value,
                        "components": component_flags,
                    }
                )
                receipt_digest = (
                    canonical_sha256(
                        {
                            "schema_version": "mechanism-ablation-receipt-v1",
                            "case_id": case.case_id,
                            "trial_index": trial_index,
                            "variant": variant.value,
                            "release_authorized": authorized,
                        }
                    )
                    if receipt
                    else None
                )
                observation_payload = {
                    "schema_version": "ablation-observation-v1",
                    "suite_id": PILOT_SUITE_ID,
                    "case_id": case.case_id,
                    "trial_index": trial_index,
                    "variant": variant.value,
                    "evidence_origin": "mechanism_fixture",
                    "derivation_method": "synthetic_component_rehearsal",
                    "candidate_digest_sha256": None,
                    "source_decision_id": None,
                    "source_decision_digest_sha256": None,
                    "source_human_session_id": None,
                    "source_human_trace_digest_sha256": None,
                    "tool_trace_digest_sha256": None,
                    "component_policy_digest_sha256": component_policy_digest,
                    "component_receipt_digest_sha256": receipt_digest,
                    "deterministic_checks_present": deterministic,
                    "human_reconstruction_present": human,
                    "receipt_present": receipt,
                    "independent_gate_present": independent,
                    "propagation_gate_present": propagation,
                    "release_authorized": authorized,
                    "approved_scope": (
                        DeliveryScope.PERSONAL_LOCAL.value
                        if authorized
                        else DeliveryScope.BLOCKED.value
                    ),
                    "reason_codes": [
                        "synthetic-component-path-rehearsal",
                        "not-observed-efficacy-evidence",
                    ],
                    "hidden_labels_accessible": False,
                    "efficacy_claim_allowed": False,
                    "privacy": benchmark_privacy().model_dump(mode="json"),
                }
                observations.append(
                    AblationObservationV1.model_validate(
                        {
                            **observation_payload,
                            "observation_trace_digest_sha256": canonical_sha256(
                                observation_payload
                            ),
                        }
                    )
                )
    return observations


def _unique_by_resume_key(runs: Sequence[PairedRunV1]) -> dict[str, PairedRunV1]:
    unique: dict[str, PairedRunV1] = {}
    for run in runs:
        if run.resume_key in unique:
            raise BenchmarkRunnerError(f"duplicate resume key: {run.resume_key}")
        unique[run.resume_key] = run
    return unique


def _observed_decisions(path: Path) -> dict[tuple[str, int, BenchmarkArm], ReviewerDecisionV1]:
    decisions: dict[tuple[str, int, BenchmarkArm], ReviewerDecisionV1] = {}
    for decision in _load_jsonl(path, ReviewerDecisionV1):
        key = (decision.case_id, decision.trial_index, decision.arm)
        if key in decisions:
            raise BenchmarkRunnerError(f"duplicate observed decision: {key}")
        decisions[key] = decision
    return decisions


def _observed_tool_traces(path: Path) -> dict[str, DecisionToolTraceV1]:
    traces: dict[str, DecisionToolTraceV1] = {}
    for trace in _load_jsonl(path, DecisionToolTraceV1):
        if trace.decision_id in traces:
            raise BenchmarkRunnerError(f"duplicate observed tool trace: {trace.decision_id}")
        traces[trace.decision_id] = trace
    return traces


def _observed_execution_provenance(
    path: Path,
) -> dict[str, ReviewExecutionProvenanceV1]:
    receipts: dict[str, ReviewExecutionProvenanceV1] = {}
    for receipt in _load_jsonl(path, ReviewExecutionProvenanceV1):
        if receipt.decision_id in receipts:
            raise BenchmarkRunnerError(
                f"duplicate observed execution provenance: {receipt.decision_id}"
            )
        payload = receipt.model_dump(mode="json")
        payload.pop("trace_digest_sha256")
        if receipt.trace_digest_sha256 != canonical_sha256(payload):
            raise BenchmarkRunnerError(
                f"observed execution provenance digest mismatch: {receipt.decision_id}"
            )
        receipts[receipt.decision_id] = receipt
    return receipts


def _trace_bound_receipts(
    path: Path,
    model_type: type[ModelT],
) -> dict[str, ModelT]:
    receipts: dict[str, ModelT] = {}
    for receipt in _load_jsonl(path, model_type):
        receipt_id = getattr(receipt, "receipt_id", None)
        trace_digest = getattr(receipt, "trace_digest_sha256", None)
        if not isinstance(receipt_id, str) or not isinstance(trace_digest, str):
            raise BenchmarkRunnerError(f"invalid trace-bound receipt: {path.name}")
        if receipt_id in receipts:
            raise BenchmarkRunnerError(f"duplicate trace-bound receipt: {receipt_id}")
        payload = receipt.model_dump(mode="json")
        payload.pop("trace_digest_sha256")
        if trace_digest != canonical_sha256(payload):
            raise BenchmarkRunnerError(f"trace-bound receipt digest mismatch: {receipt_id}")
        receipts[receipt_id] = receipt
    return receipts


def _validate_tool_trace_coverage(
    runs: Sequence[PairedRunV1], traces: Sequence[DecisionToolTraceV1]
) -> bool:
    traces_by_decision = {trace.decision_id: trace for trace in traces}
    decisions = [decision for run in runs for decision in run.decisions]
    if len(traces_by_decision) != len(traces) or set(traces_by_decision) != {
        item.decision_id for item in decisions
    }:
        return False
    for decision in decisions:
        trace = traces_by_decision[decision.decision_id]
        if trace.trace_digest_sha256 != tool_trace_digest(trace):
            return False
        if decision.tool_trace_digest_sha256 != trace.trace_digest_sha256:
            return False
        if (
            trace.case_id != decision.case_id
            or trace.trial_index != decision.trial_index
            or trace.arm != decision.arm
            or trace.evidence_origin != decision.evidence_origin
            or trace.model_ref != decision.model_ref
            or trace.model_version != decision.model_version
        ):
            return False
        if len(trace.calls) != decision.usage.tool_calls:
            return False
        if any(call.tool_permission_id not in decision.tool_permission_ids for call in trace.calls):
            return False
    return True


def _validate_execution_provenance_coverage(
    runs: Sequence[PairedRunV1],
    receipts: Sequence[ReviewExecutionProvenanceV1],
) -> bool:
    receipts_by_decision = {receipt.decision_id: receipt for receipt in receipts}
    decisions = [decision for run in runs for decision in run.decisions]
    if len(receipts_by_decision) != len(receipts) or set(receipts_by_decision) != {
        item.decision_id for item in decisions
    }:
        return False
    if len({receipt.workspace_identity_digest_sha256 for receipt in receipts}) != len(receipts):
        return False
    if len({receipt.provider_thread_id_digest_sha256 for receipt in receipts}) != len(receipts):
        return False
    if any(
        receipt.provider_thread_id_digest_sha256 == sha256(b"").hexdigest() for receipt in receipts
    ):
        return False
    for decision in decisions:
        receipt = receipts_by_decision[decision.decision_id]
        payload = receipt.model_dump(mode="json")
        payload.pop("trace_digest_sha256")
        if receipt.trace_digest_sha256 != canonical_sha256(payload):
            return False
        if decision.execution_trace_digest_sha256 != receipt.trace_digest_sha256:
            return False
        if (
            receipt.case_id != decision.case_id
            or receipt.trial_index != decision.trial_index
            or receipt.arm != decision.arm
            or receipt.candidate_digest_sha256 != decision.candidate_digest_sha256
            or receipt.context_digest_sha256 != decision.context_digest_sha256
            or receipt.model_ref != decision.model_ref
            or receipt.model_version != decision.model_version
            or receipt.harness_ref != decision.harness_ref
            or receipt.tool_trace_digest_sha256 != decision.tool_trace_digest_sha256
            or receipt.budget != decision.budget
            or receipt.usage != decision.usage
        ):
            return False
    return True


def load_observed_assets(
    case_dir: Path,
    candidate_dir: Path,
    scorer_receipts: Sequence[ScorerExecutionReceiptV1],
    adjudication_receipts: Sequence[BlindedAdjudicationReceiptV1],
) -> list[tuple[BenchmarkCaseV1, CandidateDeliveryV1]]:
    expected_assets = pilot_assets()
    expected_by_id = {case.case_id: case for case, _ in expected_assets}
    expected_ids = set(expected_by_id)
    case_files = {path.stem: path for path in case_dir.glob("*.json")}
    candidate_files = {path.stem: path for path in candidate_dir.glob("*.json")}
    if set(case_files) != expected_ids or set(candidate_files) != expected_ids:
        raise BenchmarkRunnerError(
            "observed case and candidate directories must contain exactly the frozen 40 IDs"
        )
    scorers_by_case = {receipt.case_id: receipt for receipt in scorer_receipts}
    adjudications_by_case = {receipt.case_id: receipt for receipt in adjudication_receipts}
    if (
        len(scorers_by_case) != len(scorer_receipts)
        or len(adjudications_by_case) != len(adjudication_receipts)
        or set(scorers_by_case) != expected_ids
        or set(adjudications_by_case) != expected_ids
    ):
        raise BenchmarkRunnerError(
            "observed scorer and adjudication receipts must cover exactly the frozen 40 IDs"
        )

    assets: list[tuple[BenchmarkCaseV1, CandidateDeliveryV1]] = []
    for case_id in sorted(expected_ids):
        case_payload = json.loads(case_files[case_id].read_text(encoding="utf-8"))
        candidate_payload = json.loads(candidate_files[case_id].read_text(encoding="utf-8"))
        assert_safe_metadata(case_payload, label=f"observed oracle {case_id}")
        assert_safe_metadata(candidate_payload, label=f"observed candidate {case_id}")
        case = BenchmarkCaseV1.model_validate(case_payload)
        candidate = CandidateDeliveryV1.model_validate(candidate_payload)
        expected = expected_by_id[case_id]
        if (
            case.candidate_assignment != expected.candidate_assignment
            or case.candidate_recipe_code != expected.candidate_recipe_code
            or case.candidate_recipe_digest_sha256 != expected.candidate_recipe_digest_sha256
            or case.selection_protocol_digest_sha256 != expected.selection_protocol_digest_sha256
            or case.selection_locked_at != expected.selection_locked_at
        ):
            raise BenchmarkRunnerError(
                f"observed candidate assignment drifted after preregistration: {case_id}"
            )
        observed_source_identity = case.source.model_dump(mode="json")
        expected_source_identity = expected.source.model_dump(mode="json")
        for payload in (observed_source_identity, expected_source_identity):
            payload.pop("environment_digest_sha256")
            payload.pop("environment_digest_basis")
            payload.pop("third_party_asset_terms_reviewed")
        if observed_source_identity != expected_source_identity:
            raise BenchmarkRunnerError(f"observed source identity drifted: {case_id}")
        if case.source.environment_digest_basis != "acquired_artifact_digests":
            raise BenchmarkRunnerError(
                f"observed source environment is not artifact-backed: {case_id}"
            )
        if (
            expected.source.third_party_asset_terms_reviewed
            and not case.source.third_party_asset_terms_reviewed
        ):
            raise BenchmarkRunnerError(f"observed source lost third-party asset review: {case_id}")
        if candidate.source_snapshot_digest_sha256 != case.source.environment_digest_sha256:
            raise BenchmarkRunnerError(
                f"observed candidate source snapshot is not bound: {case_id}"
            )
        if candidate.evidence_origin != "observed_agent_run":
            raise BenchmarkRunnerError(f"observed candidate origin is invalid: {case_id}")
        if (
            case.reference.adjudication_basis
            != "observed_official_scorer_plus_blinded_clearance_adjudication"
        ):
            raise BenchmarkRunnerError(f"observed reference basis is invalid: {case_id}")
        scorer = scorers_by_case[case_id]
        scorer_payload = scorer.model_dump(mode="json")
        scorer_payload.pop("trace_digest_sha256")
        if scorer.trace_digest_sha256 != canonical_sha256(scorer_payload):
            raise BenchmarkRunnerError(f"observed scorer receipt digest mismatch: {case_id}")
        if (
            scorer.suite_id != case.suite_id
            or scorer.benchmark_id != case.source.benchmark_id
            or scorer.upstream_task_id != case.source.upstream_task_id
            or scorer.subject_digest_sha256 != candidate.subject_digest_sha256
            or scorer.source_environment_digest_sha256 != case.source.environment_digest_sha256
            or scorer.scorer_source_uri != case.source.scorer_source_uri
            or scorer.scorer_source_revision != case.source.scorer_source_revision
            or scorer.official_scorer_ref != case.source.official_scorer_ref
            or scorer.outcome != candidate.scorer_outcome
            or candidate.scorer_trace_digest_sha256 != scorer.trace_digest_sha256
        ):
            raise BenchmarkRunnerError(f"observed scorer receipt binding failed: {case_id}")
        scorer_evidence = [
            item for item in candidate.evidence if item.evidence_type == "scorer-result"
        ]
        if (
            len(scorer_evidence) != 1
            or scorer_evidence[0].evidence_ref != f"scorer-receipt:{scorer.receipt_id}"
            or scorer_evidence[0].evidence_digest_sha256 != scorer.trace_digest_sha256
        ):
            raise BenchmarkRunnerError(f"observed scorer evidence binding failed: {case_id}")
        adjudication = adjudications_by_case[case_id]
        adjudication_payload = adjudication.model_dump(mode="json")
        adjudication_payload.pop("trace_digest_sha256")
        if adjudication.trace_digest_sha256 != canonical_sha256(adjudication_payload):
            raise BenchmarkRunnerError(f"observed adjudication receipt digest mismatch: {case_id}")
        if (
            adjudication.suite_id != case.suite_id
            or adjudication.candidate_digest_sha256 != canonical_sha256(candidate)
            or adjudication.scorer_receipt_digest_sha256 != scorer.trace_digest_sha256
            or adjudication.disposition != case.reference.disposition
            or adjudication.release_authorized != case.reference.release_authorized
            or adjudication.maximum_scope != case.reference.maximum_scope
            or adjudication.rationale_codes != case.reference.rationale_codes
            or case.reference.adjudication_trace_digest_sha256 != adjudication.trace_digest_sha256
        ):
            raise BenchmarkRunnerError(f"observed adjudication receipt binding failed: {case_id}")
        assets.append((case, candidate))
    validate_pilot_assets(assets)
    return assets


def _validate_session_coverage(
    sessions: Sequence[HumanReviewSessionV1], cases: Sequence[BenchmarkCaseV1], trials: int
) -> bool:
    expected = {
        (case.case_id, trial, mode)
        for case in cases
        for trial in range(trials)
        for mode in ("full_review_reference", "boundary_reconstruction")
    }
    actual_items = [(item.case_id, item.trial_index, item.review_mode) for item in sessions]
    traces_valid = all(
        session.evidence_origin != "observed_human_session"
        or session.measurement_trace_digest_sha256 == human_review_trace_digest(session)
        for session in sessions
    )
    collection_valid = all(
        session.evidence_origin != "observed_human_session"
        or (
            session.review_mode == "boundary_reconstruction"
            and session.collection_method == "interactive_scored_boundary"
            and session.question_set_digest_sha256 is not None
        )
        or (
            session.review_mode == "full_review_reference"
            and session.collection_method
            in {"interactive_full_review", "external_observed_measurement"}
            and (
                session.collection_method != "interactive_full_review"
                or session.question_set_digest_sha256 is not None
            )
        )
        for session in sessions
    )
    return (
        len(actual_items) == len(expected)
        and set(actual_items) == expected
        and traces_valid
        and collection_valid
    )


def human_review_trace_digest(session: HumanReviewSessionV1) -> str:
    return canonical_sha256(
        {
            "case_id": session.case_id,
            "trial_index": session.trial_index,
            "review_mode": session.review_mode,
            "collection_method": session.collection_method,
            "candidate_digest_sha256": session.candidate_digest_sha256,
            "review_material_digest_sha256": session.review_material_digest_sha256,
            "question_set_digest_sha256": session.question_set_digest_sha256,
            "measurement": session.measurement.model_dump(mode="json"),
            "completed_at": session.completed_at,
        }
    )


def _validate_ablation_coverage(
    observations: Sequence[AblationObservationV1],
    cases: Sequence[BenchmarkCaseV1],
    trials: int,
) -> bool:
    for observation in observations:
        validate_ablation_observation(observation)
    expected = {
        (case.case_id, trial, variant)
        for case in cases
        for trial in range(trials)
        for variant in AblationVariant
    }
    actual_items = [(item.case_id, item.trial_index, item.variant) for item in observations]
    return len(actual_items) == len(expected) and set(actual_items) == expected


def _validate_human_session_binding(
    sessions: Sequence[HumanReviewSessionV1], runs: Sequence[PairedRunV1]
) -> bool:
    boundary_sessions = {
        (session.case_id, session.trial_index): session
        for session in sessions
        if session.review_mode == "boundary_reconstruction"
    }
    for run in runs:
        external = next(
            (item for item in run.decisions if item.arm == BenchmarkArm.EXTERNAL_CLEARANCE),
            None,
        )
        if external is None:
            continue
        session = boundary_sessions.get((run.case_id, run.trial_index))
        if (
            session is None
            or external.human_reconstruction != session.measurement
            or (
                session.evidence_origin == "observed_human_session"
                and session.candidate_digest_sha256 != external.candidate_digest_sha256
            )
        ):
            return False
    return True


def _failure_report(
    cases: Sequence[BenchmarkCaseV1], runs: Sequence[PairedRunV1], trials: int
) -> dict[str, Any]:
    by_key = {(run.case_id, run.trial_index): run for run in runs}
    failures: list[dict[str, Any]] = []
    structural_failure_count = 0
    recorded_noncompleted_decision_count = 0
    for case in cases:
        for trial_index in range(trials):
            run = by_key.get((case.case_id, trial_index))
            if run is None:
                structural_failure_count += 1
                failures.append(
                    {
                        "case_id": case.case_id,
                        "trial_index": trial_index,
                        "failure_type": "missing-paired-run",
                    }
                )
                continue
            for decision in run.decisions:
                if decision.status != EvaluationStatus.COMPLETED:
                    recorded_noncompleted_decision_count += 1
                    failures.append(
                        {
                            "case_id": case.case_id,
                            "trial_index": trial_index,
                            "arm": decision.arm.value,
                            "failure_type": decision.status.value,
                            "reason_codes": decision.reason_codes,
                        }
                    )
            missing_arms = sorted(
                arm.value for arm in set(DEFAULT_ARMS) - {item.arm for item in run.decisions}
            )
            if missing_arms:
                structural_failure_count += 1
                failures.append(
                    {
                        "case_id": case.case_id,
                        "trial_index": trial_index,
                        "failure_type": "missing-arms",
                        "missing_arms": missing_arms,
                    }
                )
    collection_complete = structural_failure_count == 0
    status = (
        "incomplete"
        if not collection_complete
        else "complete_with_recorded_trial_outcomes"
        if recorded_noncompleted_decision_count
        else "pass"
    )
    payload = {
        "schema_version": "benchmark-failures-v1",
        "status": status,
        "collection_complete": collection_complete,
        "structural_failure_count": structural_failure_count,
        "recorded_noncompleted_decision_count": recorded_noncompleted_decision_count,
        "failure_count": len(failures),
        "failures": failures,
    }
    assert_safe_metadata(payload, label="benchmark failures")
    return payload


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_if_equal_or_new(path: Path, content: str) -> None:
    if path.is_file() and path.read_text(encoding="utf-8") != content:
        raise BenchmarkRunnerError(f"frozen case artifact drifted: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def reviewer_candidate_view(candidate: CandidateDeliveryV1) -> dict[str, Any]:
    """Return the candidate evidence reviewers may see without oracle leakage."""

    visible_evidence = [
        item.model_dump(mode="json")
        for item in candidate.evidence
        if item.evidence_type != "scorer-result"
    ]
    payload = {
        "schema_version": "reviewer-candidate-view-v1",
        "suite_id": candidate.suite_id,
        "case_id": candidate.case_id,
        "candidate_id": candidate.candidate_id,
        "candidate_digest_sha256": canonical_sha256(candidate),
        "subject_digest_sha256": candidate.subject_digest_sha256,
        "source_snapshot_digest_sha256": candidate.source_snapshot_digest_sha256,
        "context_digest_sha256": candidate.context_digest_sha256,
        "task_summary_code": candidate.task_summary_code,
        "declared_risk_level": candidate.declared_risk_level,
        "target_scope": candidate.target_scope.value,
        "intended_recipient_role": candidate.intended_recipient_role,
        "risk_owner_role": candidate.risk_owner_role,
        "prohibited_use_codes": list(candidate.prohibited_use_codes),
        "visible_evidence": visible_evidence,
        "tool_permission_ids": list(candidate.tool_permission_ids),
        "official_scorer_result_included": False,
        "reference_label_included": False,
        "hidden_tests_included": False,
        "privacy": candidate.privacy.model_dump(mode="json"),
    }
    assert_safe_metadata(payload, label=f"reviewer candidate view {candidate.case_id}")
    return payload


def _ablation_summary(observations: Sequence[AblationObservationV1]) -> dict[str, Any]:
    summary = []
    for variant in AblationVariant:
        items = [item for item in observations if item.variant == variant]
        summary.append(
            {
                "variant": variant.value,
                "observation_count": len(items),
                "authorized_count": sum(item.release_authorized for item in items),
                "evidence_origin": (items[0].evidence_origin if items else "not_available"),
                "efficacy_claim_allowed": False,
            }
        )
    origins = {item.evidence_origin for item in observations}
    observed_replay = origins == {"observed_component_replay"}
    return {
        "schema_version": "benchmark-ablation-summary-v1",
        "status": "complete"
        if all(item["observation_count"] for item in summary)
        else "incomplete",
        "variants": summary,
        "evidence_origin": next(iter(origins)) if len(origins) == 1 else "mixed-or-missing",
        "behavioral_counterfactual_claim_allowed": False,
        "claim_boundary": (
            "Trace-bound observed component replays estimate final-decision transformations, "
            "not how the model would behave under six independently executed treatments."
            if observed_replay
            else "Mechanism ablations prove component wiring only; observed evidence is required."
        ),
    }


def run_benchmark(
    output_dir: Path,
    *,
    trials: int = 1,
    resume: bool = False,
    mode: Literal["mechanism-fixture", "observed"] = "mechanism-fixture",
    observed_case_dir: Path | None = None,
    observed_candidate_dir: Path | None = None,
    observed_decisions_path: Path | None = None,
    observed_tool_traces_path: Path | None = None,
    observed_execution_provenance_path: Path | None = None,
    observed_scorer_receipts_path: Path | None = None,
    observed_adjudication_receipts_path: Path | None = None,
    observed_human_sessions_path: Path | None = None,
    observed_ablation_path: Path | None = None,
    economic_plan: ReviewEconomicEvaluationPlanV1 | None = None,
) -> BenchmarkResultV1:
    if trials < 1:
        raise BenchmarkRunnerError("trials must be positive")
    if output_dir.exists() and any(output_dir.iterdir()) and not resume:
        raise BenchmarkRunnerError("output directory is not empty; use --resume or a new directory")
    if mode == "observed" and (
        observed_decisions_path is None
        or observed_case_dir is None
        or observed_candidate_dir is None
        or observed_tool_traces_path is None
        or observed_execution_provenance_path is None
        or observed_scorer_receipts_path is None
        or observed_adjudication_receipts_path is None
    ):
        raise BenchmarkRunnerError(
            "observed mode requires observed cases, candidates, reviewer decisions, tool traces, "
            "execution provenance, scorer receipts, and adjudication receipts"
        )

    economic_plan = economic_plan or default_review_economic_evaluation_plan()
    if economic_plan.suite_id != PILOT_SUITE_ID:
        raise BenchmarkRunnerError("economic plan suite does not match pilot-v0.1")

    if mode == "observed":
        assert observed_case_dir is not None
        assert observed_candidate_dir is not None
        assert observed_scorer_receipts_path is not None
        assert observed_adjudication_receipts_path is not None
        scorer_receipts_by_id = _trace_bound_receipts(
            observed_scorer_receipts_path, ScorerExecutionReceiptV1
        )
        adjudication_receipts_by_id = _trace_bound_receipts(
            observed_adjudication_receipts_path, BlindedAdjudicationReceiptV1
        )
        scorer_receipts = sorted(scorer_receipts_by_id.values(), key=lambda item: item.case_id)
        adjudication_receipts = sorted(
            adjudication_receipts_by_id.values(), key=lambda item: item.case_id
        )
        assets = load_observed_assets(
            observed_case_dir,
            observed_candidate_dir,
            scorer_receipts,
            adjudication_receipts,
        )
        candidate_evidence_basis: Literal["mechanism_fixture", "observed_official_scorer"] = (
            "observed_official_scorer"
        )
        reference_evidence_basis: Literal["mechanism_fixture", "observed_blinded_adjudication"] = (
            "observed_blinded_adjudication"
        )
        manifest_evidence_basis: Literal["mechanism_fixture", "observed_official_scorer"] = (
            "observed_official_scorer"
        )
    else:
        assets = pilot_assets()
        scorer_receipts = []
        adjudication_receipts = []
        candidate_evidence_basis = "mechanism_fixture"
        reference_evidence_basis = "mechanism_fixture"
        manifest_evidence_basis = "mechanism_fixture"
    runtime_manifest = benchmark_manifest(assets, evidence_basis=manifest_evidence_basis)
    cases = [case for case, _ in assets]
    candidates = {case.case_id: candidate for case, candidate in assets}
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_if_equal_or_new(
        output_dir / "economic-evaluation-plan.json",
        pretty_json(economic_plan),
    )
    _write_if_equal_or_new(output_dir / "benchmark-manifest.json", pretty_json(runtime_manifest))
    for case, candidate in assets:
        reviewer_packet = {
            "schema_version": "reviewer-case-packet-v1",
            "suite_id": case.suite_id,
            "case_id": case.case_id,
            "target_scope": case.target_scope.value,
            "source": case.source.model_dump(mode="json"),
            "candidate": reviewer_candidate_view(candidate),
            "official_scorer_result_included": False,
            "reference_label_included": False,
            "hidden_tests_included": False,
        }
        assert_safe_metadata(reviewer_packet, label=f"reviewer packet {case.case_id}")
        _write_if_equal_or_new(
            output_dir / "cases" / f"{case.case_id}.json",
            json.dumps(
                reviewer_packet,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

    existing_path = output_dir / "paired-runs.jsonl"
    existing = _load_jsonl(existing_path, PairedRunV1) if resume and existing_path.is_file() else []
    expected_origin: Literal["mechanism_fixture", "observed_agent_run"] = (
        "mechanism_fixture" if mode == "mechanism-fixture" else "observed_agent_run"
    )
    if any(run.evidence_origin != expected_origin for run in existing):
        raise BenchmarkRunnerError("resume input execution origin differs from requested mode")
    runs_by_key = _unique_by_resume_key(existing)
    observed = _observed_decisions(observed_decisions_path) if observed_decisions_path else {}
    observed_traces = (
        _observed_tool_traces(observed_tool_traces_path) if observed_tool_traces_path else {}
    )
    observed_provenance = (
        _observed_execution_provenance(observed_execution_provenance_path)
        if observed_execution_provenance_path
        else {}
    )
    expected_observed_keys = {
        (case.case_id, trial_index, arm)
        for case in cases
        for trial_index in range(trials)
        for arm in DEFAULT_ARMS
    }
    unexpected_observed = sorted(set(observed) - expected_observed_keys)
    if unexpected_observed:
        raise BenchmarkRunnerError(
            f"observed decisions contain unexpected keys: {unexpected_observed}"
        )

    for case_index, case in enumerate(cases):
        candidate = candidates[case.case_id]
        for trial_index in range(trials):
            resume_key = f"{PILOT_SUITE_ID}:{case.case_id}:{trial_index}"
            current = runs_by_key.get(resume_key)
            if current is not None and current.status == "completed":
                continue
            if mode == "mechanism-fixture":
                decisions = [
                    fixture_decision(
                        case,
                        candidate,
                        arm=arm,
                        case_index=case_index,
                        trial_index=trial_index,
                    )
                    for arm in DEFAULT_ARMS
                ]
                evidence_origin: Literal["mechanism_fixture", "observed_agent_run"] = (
                    "mechanism_fixture"
                )
            else:
                decisions = [
                    observed[(case.case_id, trial_index, arm)]
                    for arm in DEFAULT_ARMS
                    if (case.case_id, trial_index, arm) in observed
                ]
                if not decisions:
                    continue
                evidence_origin = "observed_agent_run"
            runs_by_key[resume_key] = paired_run(
                case,
                candidate,
                decisions,
                trial_index=trial_index,
                evidence_origin=evidence_origin,
            )

    runs = sorted(runs_by_key.values(), key=lambda item: (item.case_id, item.trial_index))
    _write_jsonl(existing_path, runs)

    if mode == "mechanism-fixture":
        case_indexes = {case.case_id: index for index, case in enumerate(cases)}
        traces = [
            fixture_tool_trace(
                next(case for case in cases if case.case_id == decision.case_id),
                candidates[decision.case_id],
                arm=decision.arm,
                case_index=case_indexes[decision.case_id],
                trial_index=decision.trial_index,
            )
            for run in runs
            for decision in run.decisions
        ]
    else:
        traces = sorted(observed_traces.values(), key=lambda item: item.decision_id)
    _write_jsonl(output_dir / "tool-call-traces.jsonl", traces)
    tool_trace_coverage = _validate_tool_trace_coverage(runs, traces)
    execution_provenance = sorted(observed_provenance.values(), key=lambda item: item.decision_id)
    _write_jsonl(output_dir / "review-execution-provenance.jsonl", execution_provenance)
    _write_jsonl(output_dir / "scorer-execution-receipts.jsonl", scorer_receipts)
    _write_jsonl(output_dir / "blinded-adjudication-receipts.jsonl", adjudication_receipts)
    execution_provenance_coverage = (
        mode == "mechanism-fixture"
        or _validate_execution_provenance_coverage(runs, execution_provenance)
    )

    if mode == "mechanism-fixture":
        sessions = fixture_human_sessions(cases, trials)
        ablations = fixture_ablation(cases, trials)
    else:
        sessions = (
            _load_jsonl(observed_human_sessions_path, HumanReviewSessionV1)
            if observed_human_sessions_path
            else []
        )
        ablations = (
            _load_jsonl(observed_ablation_path, AblationObservationV1)
            if observed_ablation_path
            else []
        )
    _write_jsonl(output_dir / "human-review-sessions.jsonl", sessions)
    _write_jsonl(output_dir / "ablation-runs.jsonl", ablations)

    session_coverage = _validate_session_coverage(
        sessions, cases, trials
    ) and _validate_human_session_binding(sessions, runs)
    ablation_coverage = _validate_ablation_coverage(ablations, cases, trials)
    ablation_origins = {item.evidence_origin for item in ablations}
    if ablation_coverage and len(ablation_origins) == 1:
        ablation_basis: Literal[
            "mechanism_fixture", "observed_component_replay", "not_available"
        ] = next(iter(ablation_origins))
    else:
        ablation_basis = "not_available"

    generated_at = max(
        [run.completed_at for run in runs if run.completed_at is not None] or [BENCHMARK_TIMESTAMP]
    )
    manifest_digest = canonical_sha256(runtime_manifest)
    paired_runs_digest = canonical_sha256(
        {"paired_runs": [run.model_dump(mode="json") for run in runs]}
    )
    result = build_result(
        cases,
        runs,
        human_review_sessions=(sessions if session_coverage else ()),
        trials_per_case=trials,
        run_evidence_basis=expected_origin,
        candidate_evidence_basis=candidate_evidence_basis,
        reference_evidence_basis=reference_evidence_basis,
        ablation_evidence_basis=ablation_basis,
        ablation_variant_count=(len(AblationVariant) if ablation_coverage else 0),
        ablation_complete=ablation_coverage,
        tool_trace_count=len(traces),
        tool_trace_coverage_complete=(tool_trace_coverage and execution_provenance_coverage),
        manifest_digest_sha256=manifest_digest,
        paired_runs_digest_sha256=paired_runs_digest,
        generated_at=generated_at,
    )
    failures = _failure_report(cases, runs, trials)
    if not tool_trace_coverage:
        failures["failures"].append(
            {
                "failure_type": "tool-trace-coverage-incomplete",
                "expected_decision_count": sum(len(run.decisions) for run in runs),
                "observed_trace_count": len(traces),
            }
        )
        failures["failure_count"] = len(failures["failures"])
        failures["structural_failure_count"] += 1
        failures["collection_complete"] = False
        failures["status"] = "incomplete"
    if not execution_provenance_coverage:
        failures["failures"].append(
            {
                "failure_type": "execution-provenance-coverage-incomplete",
                "expected_decision_count": sum(len(run.decisions) for run in runs),
                "observed_execution_receipt_count": len(execution_provenance),
            }
        )
        failures["failure_count"] = len(failures["failures"])
        failures["structural_failure_count"] += 1
        failures["collection_complete"] = False
        failures["status"] = "incomplete"
    ablation_summary = _ablation_summary(ablations)
    power_analysis = confirmatory_power_analysis(
        cases,
        runs,
        empirical_interpretation_allowed=result.status == "pilot_complete",
    )
    cost_basis_counts: dict[str, int] = (
        dict(Counter(item.cost_basis for item in execution_provenance))
        if mode == "observed"
        else {"synthetic_fixture": sum(len(run.decisions) for run in runs)}
    )
    cost_effect = cost_effect_analysis(
        cases,
        runs,
        result=result,
        cost_basis_counts=cost_basis_counts,
        human_review_sessions=sessions,
        economic_plan=economic_plan,
    )
    statistical_analysis = {
        "schema_version": "benchmark-statistical-analysis-v1",
        "status": result.status,
        "evidence_basis": result.evidence_basis,
        "candidate_evidence_basis": result.candidate_evidence_basis,
        "reference_evidence_basis": result.reference_evidence_basis,
        "methods": {
            "primary_endpoint": "false_clearance_rate",
            "paired_binary_test": "two-sided exact McNemar on dangerous cases",
            "effect_interval": "deterministic paired bootstrap 95 percent interval",
            "time_and_cost_test": "Wilcoxon signed-rank where nonzero paired differences exist",
            "binomial_intervals": "95 percent Wilson score intervals",
        },
        "pairwise_analyses": [item.model_dump(mode="json") for item in result.pairwise_analyses],
        "missingness_sensitivity": missingness_sensitivity(cases, runs),
        "confirmatory_inference_allowed": False,
        "power_analysis_required": True,
        "power_analysis_ref": {
            "path": "power-analysis.json",
            "digest_sha256": canonical_sha256(power_analysis),
        },
        "cost_effect_analysis_ref": {
            "path": "cost-effect-analysis.json",
            "digest_sha256": canonical_sha256(cost_effect),
        },
        "economic_evaluation_plan_ref": {
            "path": "economic-evaluation-plan.json",
            "digest_sha256": canonical_sha256(economic_plan),
        },
    }
    claim_boundary = {
        "schema_version": "benchmark-claim-boundary-v1",
        "status": result.status,
        "evidence_basis": result.evidence_basis,
        "candidate_evidence_basis": result.candidate_evidence_basis,
        "reference_evidence_basis": result.reference_evidence_basis,
        "tool_trace_coverage_complete": result.tool_trace_coverage_complete,
        "execution_provenance_coverage_complete": execution_provenance_coverage,
        **result.claim_boundary.model_dump(mode="json"),
        "observed_human_session_coverage": session_coverage and mode == "observed",
        "observed_ablation_coverage": ablation_coverage and mode == "observed",
    }
    for payload, label in (
        (statistical_analysis, "benchmark statistics"),
        (claim_boundary, "benchmark claim boundary"),
        (ablation_summary, "benchmark ablation"),
        (power_analysis, "benchmark power analysis"),
        (cost_effect, "benchmark cost-effect analysis"),
    ):
        assert_safe_metadata(payload, label=label)

    (output_dir / "metrics.json").write_text(pretty_json(result), encoding="utf-8")
    (output_dir / "statistical-analysis.json").write_text(
        json.dumps(statistical_analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "claim-boundary.json").write_text(
        json.dumps(claim_boundary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "ablation-summary.json").write_text(
        json.dumps(ablation_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "power-analysis.json").write_text(
        json.dumps(power_analysis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "cost-effect-analysis.json").write_text(
        json.dumps(cost_effect, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_markdown = render_markdown_report(
        result=result,
        manifest=runtime_manifest,
        failures=failures,
        ablation_summary=ablation_summary,
        power_analysis=power_analysis,
        cost_effect_analysis=cost_effect,
        trials=trials,
    )
    (output_dir / "benchmark-report.md").write_text(report_markdown, encoding="utf-8")
    (output_dir / "benchmark-report.html").write_text(
        render_html_report(report_markdown), encoding="utf-8"
    )

    receipt_inputs = [
        "economic-evaluation-plan.json",
        "benchmark-manifest.json",
        "paired-runs.jsonl",
        "tool-call-traces.jsonl",
        "review-execution-provenance.jsonl",
        "scorer-execution-receipts.jsonl",
        "blinded-adjudication-receipts.jsonl",
        "human-review-sessions.jsonl",
        "ablation-runs.jsonl",
        "metrics.json",
        "statistical-analysis.json",
        "failures.json",
        "claim-boundary.json",
        "ablation-summary.json",
        "power-analysis.json",
        "cost-effect-analysis.json",
        "benchmark-report.md",
        "benchmark-report.html",
    ]
    reproducibility = {
        "schema_version": "benchmark-reproducibility-receipt-v1",
        "suite_id": PILOT_SUITE_ID,
        "status": "pass" if failures["collection_complete"] else "incomplete",
        "evidence_basis": result.evidence_basis,
        "candidate_evidence_basis": result.candidate_evidence_basis,
        "reference_evidence_basis": result.reference_evidence_basis,
        "runner_ref": "study_anything.cbb.benchmark.runner:v0.1",
        "source_manifest_digest_sha256": manifest_digest,
        "paired_runs_digest_sha256": paired_runs_digest,
        "artifact_digests_sha256": {
            name: _sha256_file(output_dir / name) for name in receipt_inputs
        },
        "resume": {
            "resume_key": "suite_id:case_id:trial_index",
            "duplicate_completed_trials": False,
            "completed_trials_reused": resume,
        },
        "isolation": {
            "oracle_passed_to_reviewers": False,
            "hidden_tests_passed_to_reviewers": False,
            "producing_agent_can_modify_external_gate": False,
            "upstream_sources_mutated": False,
        },
        "claim_boundary": claim_boundary,
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }
    assert_safe_metadata(reproducibility, label="benchmark reproducibility receipt")
    (output_dir / "reproducibility-receipt.json").write_text(
        json.dumps(reproducibility, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def record_human_review_session(
    *,
    suite_id: str = PILOT_SUITE_ID,
    case_id: str,
    trial_index: int,
    review_mode: Literal["full_review_reference", "boundary_reconstruction"],
    reviewer_role: str,
    active_review_ms: int,
    correct_answers: int,
    unresolved_questions: int,
    nasa_tlx_score: float | None,
    completed_at: str,
    candidate_digest_sha256: str,
    review_material_digest_sha256: str,
    collection_method: Literal[
        "interactive_scored_boundary",
        "interactive_full_review",
        "external_observed_measurement",
    ] = "external_observed_measurement",
    question_set_digest_sha256: str | None = None,
    presentation_profile: ReviewPresentationProfile = "technical_codes",
    review_entry_route: ReviewEntryRoute = "legacy_unspecified",
    review_preflight_policy_digest_sha256: str | None = None,
) -> HumanReviewSessionV1:
    measurement = HumanReconstructionMeasurementV1(
        reviewer_role=reviewer_role,
        qualification_scope=DeliveryScope.PERSONAL_LOCAL,
        presentation_profile=presentation_profile,
        professional_qualification_claimed=False,
        review_entry_route=review_entry_route,
        review_preflight_method=(
            "questionnaire_v1"
            if review_preflight_policy_digest_sha256 is not None
            else "legacy_unspecified"
        ),
        review_preflight_policy_digest_sha256=review_preflight_policy_digest_sha256,
        raw_preflight_answers_included=False,
        active_review_ms=active_review_ms,
        boundary_questions_total=5,
        boundary_questions_correct=correct_answers,
        unresolved_question_count=unresolved_questions,
        nasa_tlx_score=nasa_tlx_score,
        raw_answers_included=False,
        passive_attention_only=False,
    )
    return HumanReviewSessionV1(
        schema_version="human-review-session-v1",
        session_id=f"review:{case_id}:{trial_index}:{review_mode}",
        suite_id=suite_id,
        case_id=case_id,
        trial_index=trial_index,
        review_mode=review_mode,
        evidence_origin="observed_human_session",
        collection_method=collection_method,
        candidate_digest_sha256=candidate_digest_sha256,
        review_material_digest_sha256=review_material_digest_sha256,
        question_set_digest_sha256=question_set_digest_sha256,
        measurement_trace_digest_sha256=canonical_sha256(
            {
                "case_id": case_id,
                "trial_index": trial_index,
                "review_mode": review_mode,
                "collection_method": collection_method,
                "candidate_digest_sha256": candidate_digest_sha256,
                "review_material_digest_sha256": review_material_digest_sha256,
                "question_set_digest_sha256": question_set_digest_sha256,
                "measurement": measurement.model_dump(mode="json"),
                "completed_at": completed_at,
            }
        ),
        measurement=measurement,
        completed_at=completed_at,
        privacy=benchmark_privacy(),
    )


def median_review_time(sessions: Sequence[HumanReviewSessionV1], review_mode: str) -> float | None:
    values = [
        session.measurement.active_review_ms
        for session in sessions
        if session.review_mode == review_mode
    ]
    return float(median(values)) if values else None
