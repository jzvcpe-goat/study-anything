"""Deterministic assembly of observed benchmark source and reviewer captures."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Literal, TypeVar

from pydantic import BaseModel

from study_anything.cbb.benchmark.adapters import PILOT_SUITE_ID, benchmark_privacy
from study_anything.cbb.benchmark.fixtures import pilot_assets
from study_anything.cbb.benchmark.human_reconstruction import (
    boundary_questions,
    question_set_digest,
)
from study_anything.cbb.benchmark.models import (
    BenchmarkArm,
    BenchmarkSource,
    CandidateDeliveryV1,
    DecisionToolTraceV1,
    EvaluationStatus,
    ReviewExecutionProvenanceV1,
    ReviewerDecisionV1,
    ScorerExecutionReceiptV1,
    SupersededReviewAttemptV1,
)
from study_anything.cbb.benchmark.observed_runtime import superseded_attempt_trace_digest
from study_anything.cbb.benchmark.runner import tool_trace_digest
from study_anything.cbb.protocol.canonical import (
    assert_safe_metadata,
    canonical_sha256,
    pretty_json,
)


ModelT = TypeVar("ModelT", bound=BaseModel)


class ObservedAssemblyError(ValueError):
    """Raised when observed source captures cannot form one auditable pilot."""


@dataclass(frozen=True)
class ObservedSourceInput:
    benchmark_id: BenchmarkSource
    bundle_dir: Path
    capture_dir: Path


def assembly_evaluation_status(
    statuses: Iterable[EvaluationStatus],
    *,
    expected_decision_count: int,
) -> Literal[
    "four_arm_evaluation_complete",
    "four_arm_evaluation_complete_with_recorded_trial_outcomes",
    "four_arm_evaluation_incomplete",
]:
    """Separate missing/inconclusive coverage from retained failed outcomes."""

    values = list(statuses)
    if (
        len(values) != expected_decision_count
        or EvaluationStatus.INCONCLUSIVE in values
    ):
        return "four_arm_evaluation_incomplete"
    if EvaluationStatus.FAILED in values:
        return "four_arm_evaluation_complete_with_recorded_trial_outcomes"
    return "four_arm_evaluation_complete"


def _sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ObservedAssemblyError(f"missing observed artifact: {path.name}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ObservedAssemblyError(f"observed artifact must be an object: {path.name}")
    assert_safe_metadata(payload, label=path.name)
    return payload


def _read_model(path: Path, model_type: type[ModelT]) -> ModelT:
    return model_type.model_validate(_read_json(path))


def _read_jsonl(path: Path, model_type: type[ModelT]) -> list[ModelT]:
    if not path.is_file():
        raise ObservedAssemblyError(f"missing observed artifact: {path.name}")
    values: list[ModelT] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        assert_safe_metadata(payload, label=f"{path.name}:{line_number}")
        values.append(model_type.model_validate(payload))
    return values


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_safe_metadata(payload, label=path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Iterable[BaseModel]) -> None:
    rows = [
        json.dumps(
            value.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for value in values
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")


def _trace_bound_scorer(path: Path) -> ScorerExecutionReceiptV1:
    receipt = _read_model(path, ScorerExecutionReceiptV1)
    payload = receipt.model_dump(mode="json")
    payload.pop("trace_digest_sha256")
    if receipt.trace_digest_sha256 != canonical_sha256(payload):
        raise ObservedAssemblyError(f"scorer trace digest mismatch: {receipt.case_id}")
    return receipt


def _execution_trace_valid(receipt: ReviewExecutionProvenanceV1) -> bool:
    payload = receipt.model_dump(mode="json")
    payload.pop("trace_digest_sha256")
    return receipt.trace_digest_sha256 == canonical_sha256(payload)


def _expected_ids() -> dict[BenchmarkSource, tuple[str, ...]]:
    grouped: dict[BenchmarkSource, list[str]] = {source: [] for source in BenchmarkSource}
    for case, _ in pilot_assets():
        grouped[case.source.benchmark_id].append(case.case_id)
    return {source: tuple(sorted(case_ids)) for source, case_ids in grouped.items()}


def _exact_json_files(directory: Path, expected_ids: tuple[str, ...]) -> dict[str, Path]:
    files = {path.stem: path for path in directory.glob("*.json")}
    if set(files) != set(expected_ids):
        raise ObservedAssemblyError(
            f"{directory.name} must contain exactly the frozen source case IDs"
        )
    return files


def _validate_packet(
    packet: dict[str, Any], candidate: CandidateDeliveryV1
) -> tuple[str, str]:
    if (
        packet.get("case_id") != candidate.case_id
        or packet.get("reference_label_included") is not False
        or packet.get("hidden_tests_included") is not False
        or packet.get("official_scorer_result_included") is not False
    ):
        raise ObservedAssemblyError(f"reviewer packet isolation failed: {candidate.case_id}")
    candidate_view = packet.get("candidate")
    if not isinstance(candidate_view, dict):
        raise ObservedAssemblyError(f"reviewer candidate view missing: {candidate.case_id}")
    if candidate_view.get("candidate_digest_sha256") != canonical_sha256(candidate):
        raise ObservedAssemblyError(f"reviewer candidate digest mismatch: {candidate.case_id}")
    forbidden = {
        "scorer_outcome",
        "scorer_execution_origin",
        "official_scorer_executed",
        "scorer_trace_digest_sha256",
    }
    if forbidden.intersection(candidate_view):
        raise ObservedAssemblyError(f"reviewer packet leaks scorer metadata: {candidate.case_id}")
    visible = candidate_view.get("visible_evidence")
    if not isinstance(visible, list) or any(
        isinstance(item, dict) and item.get("evidence_type") == "scorer-result"
        for item in visible
    ):
        raise ObservedAssemblyError(f"reviewer packet leaks scorer evidence: {candidate.case_id}")
    material_digest = canonical_sha256(packet)
    questions = boundary_questions(packet)
    return material_digest, question_set_digest(
        questions,
        review_material_digest_sha256=material_digest,
    )


def assemble_observed_capture(
    output_dir: Path,
    *,
    sources: Iterable[ObservedSourceInput],
) -> dict[str, Any]:
    """Assemble 40 scorer-backed cases without manufacturing missing human evidence."""

    if output_dir.exists() and any(output_dir.iterdir()):
        raise ObservedAssemblyError("observed assembly output must be empty")
    source_items = list(sources)
    source_by_id = {item.benchmark_id: item for item in source_items}
    if len(source_by_id) != len(source_items) or set(source_by_id) != set(BenchmarkSource):
        raise ObservedAssemblyError("observed assembly requires each benchmark source exactly once")

    expected_ids_by_source = _expected_ids()
    candidates: dict[str, CandidateDeliveryV1] = {}
    packets: dict[str, dict[str, Any]] = {}
    scorers: dict[str, ScorerExecutionReceiptV1] = {}
    decisions: dict[str, ReviewerDecisionV1] = {}
    traces: dict[str, DecisionToolTraceV1] = {}
    provenance: dict[str, ReviewExecutionProvenanceV1] = {}
    superseded_attempts: dict[str, SupersededReviewAttemptV1] = {}
    source_summaries: list[dict[str, Any]] = []
    human_queue: list[dict[str, Any]] = []
    adjudication_queue: list[dict[str, Any]] = []
    model_identities: set[tuple[str, str]] = set()

    adjudication_protocol = {
        "schema_version": "blinded-clearance-adjudication-protocol-v1",
        "maximum_authority": "personal_local",
        "arm_decisions_accessible": False,
        "arm_identities_accessible": False,
        "official_scorer_is_supporting_not_sufficient": True,
        "required_outputs": [
            "disposition",
            "release_authorized",
            "maximum_scope",
            "rationale_codes",
        ],
    }
    adjudication_protocol_digest = canonical_sha256(adjudication_protocol)

    for benchmark_id in BenchmarkSource:
        source = source_by_id[benchmark_id]
        expected_ids = expected_ids_by_source[benchmark_id]
        source_manifest_path = source.bundle_dir / "manifest.json"
        capture_manifest_path = source.capture_dir / "capture-manifest.json"
        source_manifest = _read_json(source_manifest_path)
        capture_manifest = _read_json(capture_manifest_path)
        if (
            source_manifest.get("suite_id") != PILOT_SUITE_ID
            or source_manifest.get("official_scorer_executed") is not True
            or source_manifest.get("case_count") != len(expected_ids)
        ):
            raise ObservedAssemblyError(f"official scorer manifest invalid: {benchmark_id.value}")
        if (
            tuple(sorted(capture_manifest.get("case_ids", []))) != expected_ids
            or capture_manifest.get("captured_decision_count") != len(expected_ids) * len(BenchmarkArm)
            or capture_manifest.get("same_runtime_flags_for_all_arms") is not True
            or capture_manifest.get("workspace_and_thread_isolation_verified") is not True
            or capture_manifest.get("sandbox") != "read-only"
            or capture_manifest.get("ephemeral_sessions") is not True
        ):
            raise ObservedAssemblyError(f"review capture manifest invalid: {benchmark_id.value}")
        retry_history = capture_manifest.get("retry_history")
        if not isinstance(retry_history, dict) or (
            retry_history.get("append_only_superseded_attempts") is not True
            or retry_history.get("max_attempts_per_decision") != 1
        ):
            raise ObservedAssemblyError(f"retry policy is not frozen: {benchmark_id.value}")

        candidate_files = _exact_json_files(source.bundle_dir / "observed-candidates", expected_ids)
        packet_files = _exact_json_files(source.bundle_dir / "reviewer-packets", expected_ids)
        scorer_files = _exact_json_files(source.bundle_dir / "scorer-receipts", expected_ids)
        source_manifest_cases = {
            str(item.get("case_id")): item for item in source_manifest.get("cases", [])
        }
        if set(source_manifest_cases) != set(expected_ids):
            raise ObservedAssemblyError(f"source manifest case coverage failed: {benchmark_id.value}")

        source_decisions = _read_jsonl(
            source.capture_dir / "observed-decisions.jsonl", ReviewerDecisionV1
        )
        source_traces = _read_jsonl(
            source.capture_dir / "observed-tool-traces.jsonl", DecisionToolTraceV1
        )
        source_provenance = _read_jsonl(
            source.capture_dir / "observed-execution-provenance.jsonl",
            ReviewExecutionProvenanceV1,
        )
        source_superseded = _read_jsonl(
            source.capture_dir / "superseded-review-attempts.jsonl",
            SupersededReviewAttemptV1,
        )
        source_decisions_by_key = {
            (item.case_id, item.trial_index, item.arm): item for item in source_decisions
        }
        expected_decision_keys = {
            (case_id, 0, arm) for case_id in expected_ids for arm in BenchmarkArm
        }
        if (
            len(source_decisions_by_key) != len(source_decisions)
            or set(source_decisions_by_key) != expected_decision_keys
        ):
            raise ObservedAssemblyError(f"four-arm decision coverage failed: {benchmark_id.value}")
        source_traces_by_id = {item.decision_id: item for item in source_traces}
        source_provenance_by_id = {item.decision_id: item for item in source_provenance}
        if (
            len(source_traces_by_id) != len(source_traces)
            or len(source_provenance_by_id) != len(source_provenance)
            or set(source_traces_by_id) != {item.decision_id for item in source_decisions}
            or set(source_provenance_by_id) != {item.decision_id for item in source_decisions}
        ):
            raise ObservedAssemblyError(f"trace coverage failed: {benchmark_id.value}")

        for case_id in expected_ids:
            candidate = _read_model(candidate_files[case_id], CandidateDeliveryV1)
            packet = _read_json(packet_files[case_id])
            scorer = _trace_bound_scorer(scorer_files[case_id])
            candidate_digest = canonical_sha256(candidate)
            source_case = source_manifest_cases[case_id]
            if (
                candidate.case_id != case_id
                or candidate.evidence_origin != "observed_agent_run"
                or candidate.scorer_execution_origin != "observed_official_scorer"
                or candidate_digest != source_case.get("candidate_digest_sha256")
                or scorer.case_id != case_id
                or scorer.benchmark_id != benchmark_id
                or scorer.suite_id != PILOT_SUITE_ID
                or scorer.subject_digest_sha256 != candidate.subject_digest_sha256
                or scorer.source_environment_digest_sha256
                != candidate.source_snapshot_digest_sha256
                or scorer.outcome != candidate.scorer_outcome
                or scorer.trace_digest_sha256 != candidate.scorer_trace_digest_sha256
                or canonical_sha256(scorer)
                != source_case.get("scorer_receipt_digest_sha256")
            ):
                raise ObservedAssemblyError(f"candidate/scorer binding failed: {case_id}")
            material_digest, questions_digest = _validate_packet(packet, candidate)
            case_decisions = [
                source_decisions_by_key[(case_id, 0, arm)] for arm in BenchmarkArm
            ]
            if (
                {item.candidate_digest_sha256 for item in case_decisions}
                != {candidate_digest}
                or {item.context_digest_sha256 for item in case_decisions}
                != {candidate.context_digest_sha256}
                or {tuple(item.tool_permission_ids) for item in case_decisions}
                != {tuple(candidate.tool_permission_ids)}
                or len({item.budget for item in case_decisions}) != 1
                or len({(item.model_ref, item.model_version) for item in case_decisions}) != 1
            ):
                raise ObservedAssemblyError(f"paired fairness binding failed: {case_id}")
            model_identities.update((item.model_ref, item.model_version) for item in case_decisions)
            for decision in case_decisions:
                trace = source_traces_by_id[decision.decision_id]
                receipt = source_provenance_by_id[decision.decision_id]
                if (
                    trace.trace_digest_sha256 != tool_trace_digest(trace)
                    or trace.trace_digest_sha256 != decision.tool_trace_digest_sha256
                    or not _execution_trace_valid(receipt)
                    or receipt.trace_digest_sha256 != decision.execution_trace_digest_sha256
                    or receipt.candidate_digest_sha256 != candidate_digest
                    or receipt.context_digest_sha256 != candidate.context_digest_sha256
                    or receipt.tool_trace_digest_sha256 != trace.trace_digest_sha256
                    or receipt.budget != decision.budget
                    or receipt.usage != decision.usage
                ):
                    raise ObservedAssemblyError(
                        f"decision execution binding failed: {decision.decision_id}"
                    )
                if decision.decision_id in decisions:
                    raise ObservedAssemblyError(f"duplicate decision ID: {decision.decision_id}")
                decisions[decision.decision_id] = decision
                traces[trace.decision_id] = trace
                provenance[receipt.decision_id] = receipt

            candidates[case_id] = candidate
            packets[case_id] = packet
            scorers[case_id] = scorer
            human_queue.append(
                {
                    "case_id": case_id,
                    "trial_index": 0,
                    "candidate_digest_sha256": candidate_digest,
                    "review_material_digest_sha256": material_digest,
                    "question_set_digest_sha256": questions_digest,
                    "required_review_modes": [
                        "boundary_reconstruction",
                        "full_review_reference",
                    ],
                    "arm_decisions_accessible": False,
                    "official_scorer_result_accessible": False,
                }
            )
            adjudication_packet = {
                "schema_version": "blinded-adjudication-packet-v1",
                "suite_id": PILOT_SUITE_ID,
                "case_id": case_id,
                "candidate": candidate.model_dump(mode="json"),
                "scorer_receipt": scorer.model_dump(mode="json"),
                "protocol": adjudication_protocol,
                "adjudication_protocol_digest_sha256": adjudication_protocol_digest,
                "arm_decisions_accessible": False,
                "arm_identities_accessible": False,
                "model_reviewer_outputs_included": False,
                "privacy": benchmark_privacy().model_dump(mode="json"),
            }
            assert_safe_metadata(adjudication_packet, label=f"adjudication packet {case_id}")
            adjudication_queue.append(
                {
                    "case_id": case_id,
                    "candidate_digest_sha256": candidate_digest,
                    "scorer_receipt_digest_sha256": scorer.trace_digest_sha256,
                    "adjudication_packet_digest_sha256": canonical_sha256(
                        adjudication_packet
                    ),
                    "adjudication_protocol_digest_sha256": adjudication_protocol_digest,
                    "arm_decisions_accessible": False,
                    "arm_identities_accessible": False,
                }
            )
            _write_json(output_dir / "adjudication-packets" / f"{case_id}.json", adjudication_packet)

        for attempt in source_superseded:
            if attempt.trace_digest_sha256 != superseded_attempt_trace_digest(attempt):
                raise ObservedAssemblyError(
                    f"superseded attempt digest mismatch: {attempt.attempt_id}"
                )
            if attempt.attempt_id in superseded_attempts:
                raise ObservedAssemblyError(
                    f"duplicate superseded attempt ID: {attempt.attempt_id}"
                )
            superseded_attempts[attempt.attempt_id] = attempt

        status_counts = Counter(item.status.value for item in source_decisions)
        source_summaries.append(
            {
                "benchmark_id": benchmark_id.value,
                "case_count": len(expected_ids),
                "case_ids": list(expected_ids),
                "decision_status_counts": dict(sorted(status_counts.items())),
                "official_scorer_manifest_digest_sha256": _sha256_file(
                    source_manifest_path
                ),
                "capture_manifest_digest_sha256": _sha256_file(capture_manifest_path),
                "prior_retry_history_complete": retry_history.get(
                    "prior_retry_history_complete"
                ),
                "failed_retry_suppressed_count": retry_history.get(
                    "failed_retry_suppressed_count"
                ),
                "superseded_attempt_count": len(source_superseded),
            }
        )
        _write_json(
            output_dir / "source-scorer-manifests" / f"{benchmark_id.value}.json",
            source_manifest,
        )
        _write_json(
            output_dir / "source-capture-manifests" / f"{benchmark_id.value}.json",
            capture_manifest,
        )

    expected_all_ids = {case.case_id for case, _ in pilot_assets()}
    if set(candidates) != expected_all_ids or set(packets) != expected_all_ids:
        raise ObservedAssemblyError("assembled case coverage is not the frozen 40-case pilot")
    if len(model_identities) != 1:
        raise ObservedAssemblyError("all observed arms must use one pinned model identity")
    if len({item.workspace_identity_digest_sha256 for item in provenance.values()}) != len(
        provenance
    ) or len({item.provider_thread_id_digest_sha256 for item in provenance.values()}) != len(
        provenance
    ):
        raise ObservedAssemblyError("workspace or provider thread isolation is not unique")

    for case_id in sorted(expected_all_ids):
        _write_json(
            output_dir / "reviewer-packets" / f"{case_id}.json",
            packets[case_id],
        )
        (output_dir / "observed-candidates").mkdir(parents=True, exist_ok=True)
        (output_dir / "observed-candidates" / f"{case_id}.json").write_text(
            pretty_json(candidates[case_id]), encoding="utf-8"
        )
        (output_dir / "scorer-receipts").mkdir(parents=True, exist_ok=True)
        (output_dir / "scorer-receipts" / f"{case_id}.json").write_text(
            pretty_json(scorers[case_id]), encoding="utf-8"
        )

    ordered_decisions = sorted(
        decisions.values(), key=lambda item: (item.case_id, item.trial_index, item.arm.value)
    )
    ordered_traces = sorted(traces.values(), key=lambda item: item.decision_id)
    ordered_provenance = sorted(provenance.values(), key=lambda item: item.decision_id)
    ordered_scorers = sorted(scorers.values(), key=lambda item: item.case_id)
    ordered_superseded = sorted(
        superseded_attempts.values(),
        key=lambda item: (item.decision_id, item.attempt_sequence),
    )
    _write_jsonl(output_dir / "observed-decisions.jsonl", ordered_decisions)
    _write_jsonl(output_dir / "observed-tool-traces.jsonl", ordered_traces)
    _write_jsonl(
        output_dir / "observed-execution-provenance.jsonl", ordered_provenance
    )
    _write_jsonl(output_dir / "observed-scorer-receipts.jsonl", ordered_scorers)
    _write_jsonl(
        output_dir / "superseded-review-attempts.jsonl", ordered_superseded
    )
    _write_json(
        output_dir / "human-review-queue.json",
        {
            "schema_version": "human-review-queue-v1",
            "suite_id": PILOT_SUITE_ID,
            "case_count": len(human_queue),
            "sessions_required": len(human_queue) * 2,
            "items": sorted(human_queue, key=lambda item: str(item["case_id"])),
            "privacy": benchmark_privacy().model_dump(mode="json"),
        },
    )
    _write_json(
        output_dir / "blinded-adjudication-queue.json",
        {
            "schema_version": "blinded-adjudication-queue-v1",
            "suite_id": PILOT_SUITE_ID,
            "case_count": len(adjudication_queue),
            "adjudication_protocol_digest_sha256": adjudication_protocol_digest,
            "items": sorted(adjudication_queue, key=lambda item: str(item["case_id"])),
            "privacy": benchmark_privacy().model_dump(mode="json"),
        },
    )

    status_counts = Counter(item.status.value for item in ordered_decisions)
    external_inconclusive = sum(
        item.arm == BenchmarkArm.EXTERNAL_CLEARANCE
        and item.status == EvaluationStatus.INCONCLUSIVE
        for item in ordered_decisions
    )
    failed_decision_ids = [
        item.decision_id for item in ordered_decisions if item.status == EvaluationStatus.FAILED
    ]
    generated_at = max(item.completed_at for item in ordered_decisions)
    combined_files = [
        "observed-decisions.jsonl",
        "observed-tool-traces.jsonl",
        "observed-execution-provenance.jsonl",
        "observed-scorer-receipts.jsonl",
        "superseded-review-attempts.jsonl",
        "human-review-queue.json",
        "blinded-adjudication-queue.json",
    ]
    manifest = {
        "schema_version": "observed-benchmark-assembly-v1",
        "suite_id": PILOT_SUITE_ID,
        "status": assembly_evaluation_status(
            (item.status for item in ordered_decisions),
            expected_decision_count=len(expected_all_ids) * len(BenchmarkArm),
        ),
        "case_count": len(expected_all_ids),
        "official_scorer_receipt_count": len(ordered_scorers),
        "decision_count": len(ordered_decisions),
        "decision_status_counts": dict(sorted(status_counts.items())),
        "external_human_reconstruction_pending_count": external_inconclusive,
        "failed_decision_ids": failed_decision_ids,
        "model_identity": {
            "model_ref": next(iter(model_identities))[0],
            "model_version": next(iter(model_identities))[1],
        },
        "workspace_isolation_unique_count": len(
            {item.workspace_identity_digest_sha256 for item in ordered_provenance}
        ),
        "provider_thread_isolation_unique_count": len(
            {item.provider_thread_id_digest_sha256 for item in ordered_provenance}
        ),
        "source_summaries": source_summaries,
        "retry_history": {
            "all_new_attempts_append_only": True,
            "all_prior_retry_history_complete": all(
                item["prior_retry_history_complete"] is True for item in source_summaries
            ),
            "known_pre_ledger_history_limitation_disclosed": any(
                item["prior_retry_history_complete"] is not True
                for item in source_summaries
            ),
            "superseded_attempt_count": len(ordered_superseded),
        },
        "human_evidence": {
            "human_review_sessions_observed": 0,
            "full_review_reference_sessions_pending": len(expected_all_ids),
            "boundary_reconstruction_sessions_pending": len(expected_all_ids),
            "blinded_adjudications_pending": len(expected_all_ids),
            "synthetic_human_sessions_used": False,
        },
        "artifact_digests_sha256": {
            name: _sha256_file(output_dir / name) for name in combined_files
        },
        "generated_at": generated_at,
        "claim_boundary": {
            "maximum_scope": "personal_local",
            "current_claim": (
                "This assembly proves 40 official-scorer cases and 160 isolated four-arm "
                "review records were bound into one audit set. Human reconstruction, blinded "
                "adjudication, ablations, treatment-effect statistics, and efficacy claims remain pending."
            ),
            "delivery_clearance_effectiveness_claimed": False,
            "customer_delivery_validation_claimed": False,
            "production_approval_claimed": False,
        },
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }
    _write_json(output_dir / "assembly-manifest.json", manifest)
    return manifest


def verify_observed_assembly(output_dir: Path) -> dict[str, Any]:
    """Revalidate an assembled audit set without access to its source directories."""

    manifest = _read_json(output_dir / "assembly-manifest.json")
    if (
        manifest.get("schema_version") != "observed-benchmark-assembly-v1"
        or manifest.get("suite_id") != PILOT_SUITE_ID
        or manifest.get("case_count") != 40
        or manifest.get("official_scorer_receipt_count") != 40
        or manifest.get("decision_count") != 160
    ):
        raise ObservedAssemblyError("assembly manifest coverage is invalid")
    claim_boundary = manifest.get("claim_boundary")
    if not isinstance(claim_boundary, dict) or (
        claim_boundary.get("maximum_scope") != "personal_local"
        or claim_boundary.get("delivery_clearance_effectiveness_claimed") is not False
        or claim_boundary.get("customer_delivery_validation_claimed") is not False
        or claim_boundary.get("production_approval_claimed") is not False
    ):
        raise ObservedAssemblyError("assembly claim boundary is invalid")
    artifact_digests = manifest.get("artifact_digests_sha256")
    if not isinstance(artifact_digests, dict) or any(
        _sha256_file(output_dir / name) != digest
        for name, digest in artifact_digests.items()
        if isinstance(name, str) and isinstance(digest, str)
    ):
        raise ObservedAssemblyError("assembled artifact digest mismatch")

    expected_ids = {case.case_id for case, _ in pilot_assets()}
    candidate_files = _exact_json_files(output_dir / "observed-candidates", tuple(expected_ids))
    packet_files = _exact_json_files(output_dir / "reviewer-packets", tuple(expected_ids))
    scorer_files = _exact_json_files(output_dir / "scorer-receipts", tuple(expected_ids))
    adjudication_files = _exact_json_files(
        output_dir / "adjudication-packets", tuple(expected_ids)
    )
    candidates = {
        case_id: _read_model(path, CandidateDeliveryV1)
        for case_id, path in candidate_files.items()
    }
    packets = {case_id: _read_json(path) for case_id, path in packet_files.items()}
    scorers = {
        case_id: _trace_bound_scorer(path) for case_id, path in scorer_files.items()
    }
    decisions = _read_jsonl(output_dir / "observed-decisions.jsonl", ReviewerDecisionV1)
    traces = _read_jsonl(output_dir / "observed-tool-traces.jsonl", DecisionToolTraceV1)
    provenance = _read_jsonl(
        output_dir / "observed-execution-provenance.jsonl",
        ReviewExecutionProvenanceV1,
    )
    scorer_rows = _read_jsonl(
        output_dir / "observed-scorer-receipts.jsonl", ScorerExecutionReceiptV1
    )
    superseded = _read_jsonl(
        output_dir / "superseded-review-attempts.jsonl",
        SupersededReviewAttemptV1,
    )
    decisions_by_id = {item.decision_id: item for item in decisions}
    traces_by_id = {item.decision_id: item for item in traces}
    provenance_by_id = {item.decision_id: item for item in provenance}
    if (
        len(decisions_by_id) != 160
        or len(traces_by_id) != 160
        or len(provenance_by_id) != 160
        or set(traces_by_id) != set(decisions_by_id)
        or set(provenance_by_id) != set(decisions_by_id)
        or len({item.case_id for item in scorer_rows}) != 40
        or {item.case_id for item in scorer_rows} != expected_ids
    ):
        raise ObservedAssemblyError("assembled decision or trace coverage is invalid")

    case_arm_keys = {(item.case_id, item.trial_index, item.arm) for item in decisions}
    expected_case_arm_keys = {
        (case_id, 0, arm) for case_id in expected_ids for arm in BenchmarkArm
    }
    if case_arm_keys != expected_case_arm_keys:
        raise ObservedAssemblyError("assembled four-arm coverage is invalid")
    model_identities: set[tuple[str, str]] = set()
    for case_id in sorted(expected_ids):
        candidate = candidates[case_id]
        candidate_digest = canonical_sha256(candidate)
        _validate_packet(packets[case_id], candidate)
        scorer = scorers[case_id]
        if (
            scorer.subject_digest_sha256 != candidate.subject_digest_sha256
            or scorer.source_environment_digest_sha256
            != candidate.source_snapshot_digest_sha256
            or scorer.outcome != candidate.scorer_outcome
            or scorer.trace_digest_sha256 != candidate.scorer_trace_digest_sha256
        ):
            raise ObservedAssemblyError(f"assembled scorer binding failed: {case_id}")
        case_decisions = [item for item in decisions if item.case_id == case_id]
        if (
            {item.candidate_digest_sha256 for item in case_decisions}
            != {candidate_digest}
            or {item.context_digest_sha256 for item in case_decisions}
            != {candidate.context_digest_sha256}
            or {tuple(item.tool_permission_ids) for item in case_decisions}
            != {tuple(candidate.tool_permission_ids)}
            or len({item.budget for item in case_decisions}) != 1
        ):
            raise ObservedAssemblyError(f"assembled fairness binding failed: {case_id}")
        model_identities.update((item.model_ref, item.model_version) for item in case_decisions)
        for decision in case_decisions:
            trace = traces_by_id[decision.decision_id]
            receipt = provenance_by_id[decision.decision_id]
            if (
                trace.trace_digest_sha256 != tool_trace_digest(trace)
                or trace.trace_digest_sha256 != decision.tool_trace_digest_sha256
                or not _execution_trace_valid(receipt)
                or receipt.trace_digest_sha256 != decision.execution_trace_digest_sha256
                or receipt.candidate_digest_sha256 != candidate_digest
                or receipt.context_digest_sha256 != candidate.context_digest_sha256
                or receipt.tool_trace_digest_sha256 != trace.trace_digest_sha256
                or receipt.budget != decision.budget
                or receipt.usage != decision.usage
            ):
                raise ObservedAssemblyError(
                    f"assembled execution binding failed: {decision.decision_id}"
                )
        adjudication_packet = _read_json(adjudication_files[case_id])
        if (
            adjudication_packet.get("case_id") != case_id
            or adjudication_packet.get("arm_decisions_accessible") is not False
            or adjudication_packet.get("arm_identities_accessible") is not False
            or adjudication_packet.get("model_reviewer_outputs_included") is not False
        ):
            raise ObservedAssemblyError(f"adjudication blinding failed: {case_id}")

    if len(model_identities) != 1:
        raise ObservedAssemblyError("assembled model identity is not pinned")
    workspace_count = len(
        {item.workspace_identity_digest_sha256 for item in provenance}
    )
    provider_thread_count = len(
        {item.provider_thread_id_digest_sha256 for item in provenance}
    )
    if workspace_count != 160 or provider_thread_count != 160:
        raise ObservedAssemblyError("assembled session isolation is not unique")
    for attempt in superseded:
        if attempt.trace_digest_sha256 != superseded_attempt_trace_digest(attempt):
            raise ObservedAssemblyError(
                f"assembled superseded attempt digest failed: {attempt.attempt_id}"
            )

    human_queue = _read_json(output_dir / "human-review-queue.json")
    adjudication_queue = _read_json(output_dir / "blinded-adjudication-queue.json")
    if (
        human_queue.get("case_count") != 40
        or human_queue.get("sessions_required") != 80
        or len(human_queue.get("items", [])) != 40
        or any(
            item.get("arm_decisions_accessible") is not False
            or item.get("official_scorer_result_accessible") is not False
            for item in human_queue.get("items", [])
            if isinstance(item, dict)
        )
    ):
        raise ObservedAssemblyError("human review queue isolation is invalid")
    adjudication_items = {
        str(item.get("case_id")): item
        for item in adjudication_queue.get("items", [])
        if isinstance(item, dict)
    }
    if set(adjudication_items) != expected_ids:
        raise ObservedAssemblyError("blinded adjudication queue coverage is invalid")
    for case_id, item in adjudication_items.items():
        if (
            item.get("arm_decisions_accessible") is not False
            or item.get("arm_identities_accessible") is not False
            or item.get("adjudication_packet_digest_sha256")
            != canonical_sha256(_read_json(adjudication_files[case_id]))
        ):
            raise ObservedAssemblyError(f"blinded adjudication queue drifted: {case_id}")

    status_counts = Counter(item.status.value for item in decisions)
    if dict(sorted(status_counts.items())) != manifest.get("decision_status_counts"):
        raise ObservedAssemblyError("assembly status counts drifted")
    source_summaries = manifest.get("source_summaries")
    if not isinstance(source_summaries, list) or len(source_summaries) != 4:
        raise ObservedAssemblyError("assembly source summary coverage is invalid")
    for summary in source_summaries:
        if not isinstance(summary, dict):
            raise ObservedAssemblyError("assembly source summary is invalid")
        benchmark_id = str(summary.get("benchmark_id"))
        if (
            _sha256_file(output_dir / "source-scorer-manifests" / f"{benchmark_id}.json")
            != summary.get("official_scorer_manifest_digest_sha256")
            or _sha256_file(
                output_dir / "source-capture-manifests" / f"{benchmark_id}.json"
            )
            != summary.get("capture_manifest_digest_sha256")
        ):
            raise ObservedAssemblyError(f"assembly source manifest drifted: {benchmark_id}")

    report = {
        "schema_version": "observed-benchmark-assembly-verification-v1",
        "status": "pass",
        "assembly_status": manifest.get("status"),
        "case_count": 40,
        "official_scorer_receipt_count": 40,
        "decision_count": 160,
        "decision_status_counts": dict(sorted(status_counts.items())),
        "workspace_isolation_unique_count": workspace_count,
        "provider_thread_isolation_unique_count": provider_thread_count,
        "human_review_sessions_pending": 80,
        "blinded_adjudications_pending": 40,
        "failed_decision_ids": manifest.get("failed_decision_ids", []),
        "claim_boundary": claim_boundary,
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }
    assert_safe_metadata(report, label="observed assembly verification")
    return report
