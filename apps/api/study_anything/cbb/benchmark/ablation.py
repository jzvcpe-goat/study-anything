"""Trace-bound observed component replays for the six benchmark ablations."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

from study_anything.cbb.benchmark.adapters import PILOT_SUITE_ID, benchmark_privacy
from study_anything.cbb.benchmark.fixtures import pilot_assets
from study_anything.cbb.benchmark.models import (
    AblationObservationV1,
    AblationVariant,
    BenchmarkArm,
    CandidateDeliveryV1,
    DecisionToolTraceV1,
    EvaluationStatus,
    HumanReviewSessionV1,
    ReviewerDecisionV1,
)
from study_anything.cbb.protocol.canonical import assert_safe_metadata, canonical_sha256
from study_anything.cbb.protocol.models import DeliveryScope


class ObservedAblationError(ValueError):
    """Raised when observed evidence cannot support a complete component replay."""


COMPONENT_FLAGS: dict[AblationVariant, tuple[bool, bool, bool, bool, bool]] = {
    AblationVariant.NATIVE_ONLY: (False, False, False, False, False),
    AblationVariant.DETERMINISTIC_CHECKS: (True, False, False, False, False),
    AblationVariant.HUMAN_RECONSTRUCTION: (False, True, False, False, False),
    AblationVariant.RECEIPT: (False, False, True, False, False),
    AblationVariant.PROPAGATION_GATE: (True, False, True, True, True),
    AblationVariant.FULL_CLEARANCE: (True, True, True, True, True),
}


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


def tool_trace_digest(trace: DecisionToolTraceV1) -> str:
    payload = trace.model_dump(mode="json")
    payload.pop("trace_digest_sha256")
    return canonical_sha256(payload)


def ablation_observation_trace_digest(observation: AblationObservationV1) -> str:
    payload = observation.model_dump(mode="json")
    payload.pop("observation_trace_digest_sha256")
    return canonical_sha256(payload)


def validate_ablation_observation(
    observation: AblationObservationV1,
) -> AblationObservationV1:
    if (
        observation.observation_trace_digest_sha256
        != ablation_observation_trace_digest(observation)
    ):
        raise ObservedAblationError("ablation observation trace digest mismatch")
    assert_safe_metadata(
        observation.model_dump(mode="json"),
        label=f"ablation observation {observation.case_id}",
    )
    return observation


def _load_jsonl(path: Path, model: type[Any]) -> list[Any]:
    if not path.is_file():
        raise ObservedAblationError(f"missing observed input: {path.name}")
    values: list[Any] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            values.append(model.model_validate_json(line))
        except ValueError as exc:
            raise ObservedAblationError(
                f"invalid {path.name} row {line_number}: {exc}"
            ) from exc
    return values


def _component_policy(variant: AblationVariant) -> dict[str, Any]:
    rules = {
        AblationVariant.NATIVE_ONLY: "preserve-native-authority",
        AblationVariant.DETERMINISTIC_CHECKS: (
            "native-authority-and-no-visible-blocking-evidence"
        ),
        AblationVariant.HUMAN_RECONSTRUCTION: (
            "native-authority-and-complete-boundary-reconstruction"
        ),
        AblationVariant.RECEIPT: "preserve-native-authority-and-wrap-receipt",
        AblationVariant.PROPAGATION_GATE: (
            "fail-closed-when-human-reconstruction-component-is-withheld"
        ),
        AblationVariant.FULL_CLEARANCE: "use-observed-independent-clearance-decision",
    }
    return {
        "schema_version": "ablation-component-policy-v1",
        "variant": variant.value,
        "component_flags": COMPONENT_FLAGS[variant],
        "decision_rule": rules[variant],
        "maximum_scope": DeliveryScope.PERSONAL_LOCAL.value,
        "hidden_labels_accessible": False,
    }


def _component_outcome(
    variant: AblationVariant,
    *,
    native: ReviewerDecisionV1,
    external: ReviewerDecisionV1,
    blocking_codes: list[str],
    human: HumanReviewSessionV1,
) -> tuple[bool, list[str]]:
    human_passed = (
        human.measurement.boundary_questions_correct
        == human.measurement.boundary_questions_total
        and human.measurement.unresolved_question_count == 0
    )
    if variant == AblationVariant.NATIVE_ONLY:
        return native.release_authorized, ["observed-native-decision"]
    if variant == AblationVariant.DETERMINISTIC_CHECKS:
        authorized = native.release_authorized and not blocking_codes
        return authorized, (
            blocking_codes
            if blocking_codes
            else [
                "native-and-deterministic-checks-passed"
                if authorized
                else "native-decision-held"
            ]
        )
    if variant == AblationVariant.HUMAN_RECONSTRUCTION:
        authorized = native.release_authorized and human_passed
        return authorized, [
            "native-and-human-reconstruction-passed"
            if authorized
            else (
                "human-boundary-reconstruction-incomplete"
                if not human_passed
                else "native-decision-held"
            )
        ]
    if variant == AblationVariant.RECEIPT:
        return native.release_authorized, ["receipt-only-no-authority-change"]
    if variant == AblationVariant.PROPAGATION_GATE:
        return False, ["human-reconstruction-withheld-by-ablation"]
    return external.release_authorized, list(external.reason_codes)


def build_observed_ablation(
    assembly_dir: Path,
    human_sessions_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Replay six fixed component policies over observed, trace-bound evidence."""

    if output_dir.exists() and (
        not output_dir.is_dir() or any(output_dir.iterdir())
    ):
        raise ObservedAblationError("observed ablation output must be empty")
    expected_ids = {case.case_id for case, _ in pilot_assets()}
    packet_paths = {
        path.stem: path for path in (assembly_dir / "reviewer-packets").glob("*.json")
    }
    candidate_paths = {
        path.stem: path for path in (assembly_dir / "observed-candidates").glob("*.json")
    }
    if set(packet_paths) != expected_ids or set(candidate_paths) != expected_ids:
        raise ObservedAblationError(
            "observed assembly must contain exactly 40 reviewer packets and candidates"
        )

    decisions = _load_jsonl(
        assembly_dir / "observed-decisions.jsonl", ReviewerDecisionV1
    )
    traces = _load_jsonl(
        assembly_dir / "observed-tool-traces.jsonl", DecisionToolTraceV1
    )
    sessions = _load_jsonl(human_sessions_path, HumanReviewSessionV1)
    decisions_by_key = {
        (item.case_id, item.trial_index, item.arm): item for item in decisions
    }
    traces_by_decision = {item.decision_id: item for item in traces}
    boundary_sessions = {
        (item.case_id, item.trial_index): item
        for item in sessions
        if item.review_mode == "boundary_reconstruction"
    }
    expected_decisions = {
        (case_id, 0, arm) for case_id in expected_ids for arm in BenchmarkArm
    }
    expected_sessions = {(case_id, 0) for case_id in expected_ids}
    if (
        len(decisions_by_key) != len(decisions)
        or set(decisions_by_key) != expected_decisions
    ):
        raise ObservedAblationError("observed decisions must cover exactly 40 by four arms")
    if len(traces_by_decision) != len(traces) or set(traces_by_decision) != {
        item.decision_id for item in decisions
    }:
        raise ObservedAblationError("observed tool traces do not bind every decision")
    if (
        len(boundary_sessions) != len(
            [item for item in sessions if item.review_mode == "boundary_reconstruction"]
        )
        or set(boundary_sessions) != expected_sessions
    ):
        raise ObservedAblationError(
            "observed ablation requires exactly 40 boundary-reconstruction sessions"
        )

    observations: list[AblationObservationV1] = []
    for case_id in sorted(expected_ids):
        packet = json.loads(packet_paths[case_id].read_text(encoding="utf-8"))
        candidate = CandidateDeliveryV1.model_validate_json(
            candidate_paths[case_id].read_text(encoding="utf-8")
        )
        assert_safe_metadata(packet, label=f"ablation reviewer packet {case_id}")
        packet_candidate = packet.get("candidate")
        candidate_digest = canonical_sha256(candidate)
        if (
            not isinstance(packet_candidate, dict)
            or packet.get("reference_label_included") is not False
            or packet.get("hidden_tests_included") is not False
            or packet.get("official_scorer_result_included") is not False
            or packet_candidate.get("candidate_digest_sha256") != candidate_digest
        ):
            raise ObservedAblationError(f"reviewer packet binding failed: {case_id}")
        visible_evidence = packet_candidate.get("visible_evidence")
        if not isinstance(visible_evidence, list):
            raise ObservedAblationError(f"visible evidence is invalid: {case_id}")
        blocking_codes = [
            str(item.get("summary_code", "visible-evidence-invalid"))
            for item in visible_evidence
            if isinstance(item, dict)
            and item.get("blocking") is True
            and item.get("status") != "passed"
        ]
        native = decisions_by_key[(case_id, 0, BenchmarkArm.NATIVE)]
        external = decisions_by_key[(case_id, 0, BenchmarkArm.EXTERNAL_CLEARANCE)]
        human = boundary_sessions[(case_id, 0)]
        if (
            native.status != EvaluationStatus.COMPLETED
            or external.status != EvaluationStatus.COMPLETED
        ):
            raise ObservedAblationError(
                f"native and external decisions must be completed: {case_id}"
            )
        if (
            human.evidence_origin != "observed_human_session"
            or human.collection_method != "interactive_scored_boundary"
            or human.candidate_digest_sha256 != candidate_digest
            or human.review_material_digest_sha256 != canonical_sha256(packet)
            or human.measurement_trace_digest_sha256 != human_review_trace_digest(human)
            or external.human_reconstruction != human.measurement
        ):
            raise ObservedAblationError(f"human reconstruction binding failed: {case_id}")

        for variant in AblationVariant:
            source_decision = (
                external if variant == AblationVariant.FULL_CLEARANCE else native
            )
            trace = traces_by_decision[source_decision.decision_id]
            if (
                source_decision.candidate_digest_sha256 != candidate_digest
                or source_decision.tool_trace_digest_sha256 != tool_trace_digest(trace)
            ):
                raise ObservedAblationError(
                    f"source decision trace binding failed: {case_id} / {variant.value}"
                )
            deterministic, has_human, has_receipt, independent, propagation = (
                COMPONENT_FLAGS[variant]
            )
            authorized, reason_codes = _component_outcome(
                variant,
                native=native,
                external=external,
                blocking_codes=blocking_codes,
                human=human,
            )
            policy_digest = canonical_sha256(_component_policy(variant))
            receipt_digest = (
                canonical_sha256(
                    {
                        "schema_version": "observed-ablation-component-receipt-v1",
                        "case_id": case_id,
                        "trial_index": 0,
                        "variant": variant.value,
                        "candidate_digest_sha256": candidate_digest,
                        "source_decision_digest_sha256": canonical_sha256(
                            source_decision
                        ),
                        "component_policy_digest_sha256": policy_digest,
                        "release_authorized": authorized,
                    }
                )
                if has_receipt
                else None
            )
            payload = {
                "schema_version": "ablation-observation-v1",
                "suite_id": PILOT_SUITE_ID,
                "case_id": case_id,
                "trial_index": 0,
                "variant": variant.value,
                "evidence_origin": "observed_component_replay",
                "derivation_method": "deterministic_observed_component_replay",
                "candidate_digest_sha256": candidate_digest,
                "source_decision_id": source_decision.decision_id,
                "source_decision_digest_sha256": canonical_sha256(source_decision),
                "source_human_session_id": human.session_id if has_human else None,
                "source_human_trace_digest_sha256": (
                    human.measurement_trace_digest_sha256 if has_human else None
                ),
                "tool_trace_digest_sha256": source_decision.tool_trace_digest_sha256,
                "component_policy_digest_sha256": policy_digest,
                "component_receipt_digest_sha256": receipt_digest,
                "deterministic_checks_present": deterministic,
                "human_reconstruction_present": has_human,
                "receipt_present": has_receipt,
                "independent_gate_present": independent,
                "propagation_gate_present": propagation,
                "release_authorized": authorized,
                "approved_scope": (
                    DeliveryScope.PERSONAL_LOCAL.value
                    if authorized
                    else DeliveryScope.BLOCKED.value
                ),
                "reason_codes": reason_codes,
                "hidden_labels_accessible": False,
                "efficacy_claim_allowed": False,
                "privacy": benchmark_privacy().model_dump(mode="json"),
            }
            observations.append(
                validate_ablation_observation(
                    AblationObservationV1.model_validate(
                        {
                            **payload,
                            "observation_trace_digest_sha256": canonical_sha256(payload),
                        }
                    )
                )
            )

    expected_observation_count = len(expected_ids) * len(AblationVariant)
    if len(observations) != expected_observation_count:
        raise ObservedAblationError("observed ablation coverage is incomplete")
    manifest = {
        "schema_version": "observed-ablation-manifest-v1",
        "suite_id": PILOT_SUITE_ID,
        "status": "complete",
        "case_count": len(expected_ids),
        "variant_count": len(AblationVariant),
        "observation_count": len(observations),
        "boundary_reconstruction_session_count": len(boundary_sessions),
        "evidence_origin": "observed_component_replay",
        "derivation_method": "deterministic_observed_component_replay",
        "observation_set_digest_sha256": canonical_sha256(
            {"observations": [item.model_dump(mode="json") for item in observations]}
        ),
        "maximum_scope": DeliveryScope.PERSONAL_LOCAL.value,
        "behavioral_counterfactual_claim_allowed": False,
        "general_effectiveness_claim_allowed": False,
        "claim_boundary": (
            "These trace-bound replays estimate final-decision component effects over observed "
            "candidates. They are not six independent model executions and do not establish how "
            "the producing model would behave under each component configuration."
        ),
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }
    assert_safe_metadata(manifest, label="observed ablation manifest")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.staging-", dir=output_dir.parent
        )
    )
    try:
        (staging_dir / "ablation-runs.jsonl").write_text(
            "".join(
                json.dumps(
                    item.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
                for item in observations
            ),
            encoding="utf-8",
        )
        (staging_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        if output_dir.exists():
            output_dir.rmdir()
        staging_dir.replace(output_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return manifest
