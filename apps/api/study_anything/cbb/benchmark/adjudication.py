"""Arm-blinded human clearance adjudication for observed benchmark candidates."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Callable

from study_anything.cbb.benchmark.adapters import PILOT_SUITE_ID, benchmark_privacy
from study_anything.cbb.benchmark.fixtures import pilot_assets
from study_anything.cbb.benchmark.models import (
    BenchmarkCaseV1,
    BlindedAdjudicationReceiptV1,
    CandidateDeliveryV1,
    ClearanceDisposition,
    ScorerExecutionReceiptV1,
)
from study_anything.cbb.protocol.canonical import (
    assert_safe_metadata,
    canonical_sha256,
    pretty_json,
)
from study_anything.cbb.protocol.models import DeliveryScope, parse_timestamp


RATIONALE_CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")


class BlindedAdjudicationError(ValueError):
    """Raised when an adjudication packet or answer violates blinding."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _contains_forbidden_key(value: object, forbidden: set[str]) -> bool:
    if isinstance(value, dict):
        return bool(forbidden.intersection(value)) or any(
            _contains_forbidden_key(item, forbidden) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(item, forbidden) for item in value)
    return False


def validate_blinded_adjudication_packet(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise BlindedAdjudicationError("adjudication packet must be a JSON object")
    assert_safe_metadata(payload, label="blinded adjudication packet")
    if (
        payload.get("schema_version") != "blinded-adjudication-packet-v1"
        or payload.get("suite_id") != PILOT_SUITE_ID
        or payload.get("arm_decisions_accessible") is not False
        or payload.get("arm_identities_accessible") is not False
        or payload.get("model_reviewer_outputs_included") is not False
    ):
        raise BlindedAdjudicationError("adjudication packet does not preserve arm blinding")
    if _contains_forbidden_key(
        payload,
        {
            "arm_decisions",
            "arm_identities",
            "reviewer_decisions",
            "paired_runs",
        },
    ):
        raise BlindedAdjudicationError("adjudication packet contains experimental-arm output")
    candidate_payload = payload.get("candidate")
    scorer_payload = payload.get("scorer_receipt")
    protocol = payload.get("protocol")
    if not isinstance(candidate_payload, dict) or not isinstance(scorer_payload, dict):
        raise BlindedAdjudicationError("adjudication packet is missing candidate or scorer")
    if not isinstance(protocol, dict):
        raise BlindedAdjudicationError("adjudication packet is missing its protocol")
    candidate = CandidateDeliveryV1.model_validate(candidate_payload)
    scorer = ScorerExecutionReceiptV1.model_validate(scorer_payload)
    scorer_trace_payload = scorer.model_dump(mode="json")
    scorer_trace_payload.pop("trace_digest_sha256")
    if scorer.trace_digest_sha256 != canonical_sha256(scorer_trace_payload):
        raise BlindedAdjudicationError("adjudication scorer trace digest mismatch")
    if (
        candidate.case_id != payload.get("case_id")
        or scorer.case_id != candidate.case_id
        or scorer.subject_digest_sha256 != candidate.subject_digest_sha256
        or scorer.source_environment_digest_sha256
        != candidate.source_snapshot_digest_sha256
        or scorer.outcome != candidate.scorer_outcome
        or scorer.trace_digest_sha256 != candidate.scorer_trace_digest_sha256
        or payload.get("adjudication_protocol_digest_sha256")
        != canonical_sha256(protocol)
    ):
        raise BlindedAdjudicationError("adjudication candidate/scorer binding failed")
    return payload


def load_blinded_adjudication_packet(path: Path) -> dict[str, Any]:
    return validate_blinded_adjudication_packet(
        json.loads(path.read_text(encoding="utf-8"))
    )


def blinded_adjudication_trace_digest(receipt: BlindedAdjudicationReceiptV1) -> str:
    payload = receipt.model_dump(mode="json")
    payload.pop("trace_digest_sha256")
    return canonical_sha256(payload)


def validate_blinded_adjudication_receipt(
    receipt: BlindedAdjudicationReceiptV1,
) -> BlindedAdjudicationReceiptV1:
    if receipt.trace_digest_sha256 != blinded_adjudication_trace_digest(receipt):
        raise BlindedAdjudicationError("adjudication receipt trace digest mismatch")
    return receipt


def _load_adjudication_receipts(
    path: Path,
) -> dict[str, BlindedAdjudicationReceiptV1]:
    if not path.is_file():
        raise BlindedAdjudicationError("adjudication receipt JSONL does not exist")
    receipts: dict[str, BlindedAdjudicationReceiptV1] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        receipt = validate_blinded_adjudication_receipt(
            BlindedAdjudicationReceiptV1.model_validate(json.loads(line))
        )
        if receipt.case_id in receipts:
            raise BlindedAdjudicationError(
                f"duplicate adjudication case at line {line_number}"
            )
        receipts[receipt.case_id] = receipt
    return receipts


def materialize_observed_oracles(
    assembly_dir: Path,
    adjudication_receipts_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Bind all 40 blinded adjudications into immutable observed reference cases."""

    if output_dir.exists() and (
        not output_dir.is_dir() or any(output_dir.iterdir())
    ):
        raise BlindedAdjudicationError("observed oracle output must be empty")
    expected_assets = pilot_assets()
    expected_cases = {case.case_id: case for case, _ in expected_assets}
    expected_ids = set(expected_cases)
    packet_paths = {
        path.stem: path for path in (assembly_dir / "adjudication-packets").glob("*.json")
    }
    candidate_paths = {
        path.stem: path for path in (assembly_dir / "observed-candidates").glob("*.json")
    }
    scorer_paths = {
        path.stem: path for path in (assembly_dir / "scorer-receipts").glob("*.json")
    }
    if (
        set(packet_paths) != expected_ids
        or set(candidate_paths) != expected_ids
        or set(scorer_paths) != expected_ids
    ):
        raise BlindedAdjudicationError(
            "observed assembly must provide exactly 40 packet, candidate, and scorer files"
        )
    receipts = _load_adjudication_receipts(adjudication_receipts_path)
    if set(receipts) != expected_ids:
        missing = sorted(expected_ids - set(receipts))
        extra = sorted(set(receipts) - expected_ids)
        raise BlindedAdjudicationError(
            f"adjudication coverage must be exactly 40; missing={missing}; extra={extra}"
        )

    cases: list[BenchmarkCaseV1] = []
    disagreements: list[str] = []
    for case_id in sorted(expected_ids):
        packet = load_blinded_adjudication_packet(packet_paths[case_id])
        candidate = CandidateDeliveryV1.model_validate(
            json.loads(candidate_paths[case_id].read_text(encoding="utf-8"))
        )
        scorer = ScorerExecutionReceiptV1.model_validate(
            json.loads(scorer_paths[case_id].read_text(encoding="utf-8"))
        )
        validate_blinded_adjudication_packet(packet)
        receipt = receipts[case_id]
        packet_candidate = CandidateDeliveryV1.model_validate(packet["candidate"])
        packet_scorer = ScorerExecutionReceiptV1.model_validate(packet["scorer_receipt"])
        if (
            packet_candidate != candidate
            or packet_scorer != scorer
            or receipt.candidate_digest_sha256 != canonical_sha256(candidate)
            or receipt.scorer_receipt_digest_sha256 != scorer.trace_digest_sha256
            or receipt.adjudication_protocol_digest_sha256
            != packet.get("adjudication_protocol_digest_sha256")
        ):
            raise BlindedAdjudicationError(
                f"adjudication receipt does not bind the assembled evidence: {case_id}"
            )
        expected = expected_cases[case_id]
        if (
            receipt.disposition != expected.reference.disposition
            or receipt.release_authorized != expected.reference.release_authorized
            or receipt.maximum_scope != expected.reference.maximum_scope
        ):
            disagreements.append(case_id)
            continue
        source_payload = expected.source.model_dump(mode="json")
        source_payload.update(
            {
                "environment_digest_sha256": candidate.source_snapshot_digest_sha256,
                "environment_digest_basis": "acquired_artifact_digests",
            }
        )
        case_payload = expected.model_dump(mode="json")
        case_payload.update(
            {
                "source": source_payload,
                "candidate_digest_sha256": canonical_sha256(candidate),
                "reference": {
                    "disposition": receipt.disposition.value,
                    "release_authorized": receipt.release_authorized,
                    "maximum_scope": receipt.maximum_scope.value,
                    "rationale_codes": receipt.rationale_codes,
                    "adjudication_basis": (
                        "observed_official_scorer_plus_blinded_clearance_adjudication"
                    ),
                    "adjudication_trace_digest_sha256": receipt.trace_digest_sha256,
                },
            }
        )
        cases.append(BenchmarkCaseV1.model_validate(case_payload))

    if disagreements:
        raise BlindedAdjudicationError(
            "blinded adjudication disagrees with preregistered authority for: "
            + ", ".join(disagreements)
        )
    if len(cases) != 40:
        raise BlindedAdjudicationError("observed oracle materialization is incomplete")

    manifest = {
        "schema_version": "observed-oracle-materialization-v1",
        "suite_id": PILOT_SUITE_ID,
        "status": "complete",
        "case_count": len(cases),
        "safe_case_count": sum(case.reference.release_authorized for case in cases),
        "dangerous_case_count": sum(
            not case.reference.release_authorized for case in cases
        ),
        "adjudication_receipts_digest_sha256": canonical_sha256(
            {
                "receipts": [
                    receipts[case.case_id].model_dump(mode="json") for case in cases
                ]
            }
        ),
        "case_set_digest_sha256": canonical_sha256(
            {"cases": [case.model_dump(mode="json") for case in cases]}
        ),
        "disagreement_count": 0,
        "arm_decisions_accessible_to_adjudicators": False,
        "maximum_scope": DeliveryScope.PERSONAL_LOCAL.value,
        "effectiveness_claim_allowed": False,
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }
    assert_safe_metadata(manifest, label="observed oracle materialization")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.staging-",
            dir=output_dir.parent,
        )
    )
    try:
        cases_dir = staging_dir / "cases"
        cases_dir.mkdir()
        for case in cases:
            (cases_dir / f"{case.case_id}.json").write_text(
                pretty_json(case), encoding="utf-8"
            )
        (staging_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if output_dir.exists():
            output_dir.rmdir()
        staging_dir.replace(output_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    return manifest


def record_blinded_adjudication(
    packet: dict[str, Any],
    *,
    disposition: ClearanceDisposition,
    rationale_codes: list[str],
    adjudicator_role: str,
    started_at: str,
    completed_at: str,
) -> BlindedAdjudicationReceiptV1:
    packet = validate_blinded_adjudication_packet(packet)
    if not rationale_codes or any(
        RATIONALE_CODE_PATTERN.fullmatch(code) is None for code in rationale_codes
    ):
        raise BlindedAdjudicationError("rationale codes must be bounded lowercase identifiers")
    if len(set(rationale_codes)) != len(rationale_codes):
        raise BlindedAdjudicationError("rationale codes must not be duplicated")
    if parse_timestamp(completed_at) < parse_timestamp(started_at):
        raise BlindedAdjudicationError("adjudication completion precedes its start")
    assert_safe_metadata(
        {"adjudicator_role": adjudicator_role, "rationale_codes": rationale_codes},
        label="blinded adjudication answer",
    )
    candidate = CandidateDeliveryV1.model_validate(packet.get("candidate"))
    scorer = ScorerExecutionReceiptV1.model_validate(packet.get("scorer_receipt"))
    protocol_digest = packet.get("adjudication_protocol_digest_sha256")
    if not isinstance(protocol_digest, str):
        raise BlindedAdjudicationError("adjudication protocol digest is missing")
    release_authorized = disposition in {
        ClearanceDisposition.CLEARED,
        ClearanceDisposition.RESTRICTED,
    }
    maximum_scope = (
        DeliveryScope.PERSONAL_LOCAL if release_authorized else DeliveryScope.BLOCKED
    )
    payload = {
        "schema_version": "blinded-adjudication-receipt-v1",
        "receipt_id": f"adjudication:{candidate.case_id}:0",
        "suite_id": PILOT_SUITE_ID,
        "case_id": candidate.case_id,
        "candidate_digest_sha256": canonical_sha256(candidate),
        "scorer_receipt_digest_sha256": scorer.trace_digest_sha256,
        "adjudication_protocol_digest_sha256": protocol_digest,
        "disposition": disposition.value,
        "release_authorized": release_authorized,
        "maximum_scope": maximum_scope.value,
        "rationale_codes": rationale_codes,
        "adjudicator_role": adjudicator_role,
        "qualification_scope": DeliveryScope.PERSONAL_LOCAL.value,
        "arm_decisions_accessible": False,
        "arm_identities_accessible": False,
        "raw_adjudication_notes_included": False,
        "started_at": started_at,
        "completed_at": completed_at,
        "privacy": benchmark_privacy().model_dump(mode="json"),
    }
    receipt = BlindedAdjudicationReceiptV1.model_validate(
        {**payload, "trace_digest_sha256": canonical_sha256(payload)}
    )
    return validate_blinded_adjudication_receipt(receipt)


def run_interactive_adjudication(
    packet: dict[str, Any],
    *,
    adjudicator_role: str,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[[str], None] = print,
    display_label: str | None = None,
) -> BlindedAdjudicationReceiptV1:
    """Collect one arm-blinded adjudication without retaining free-form notes."""

    packet = validate_blinded_adjudication_packet(packet)
    candidate = CandidateDeliveryV1.model_validate(packet.get("candidate"))
    scorer = ScorerExecutionReceiptV1.model_validate(packet.get("scorer_receipt"))
    print_fn(f"Adjudication: {display_label or 'blinded-item'}")
    print_fn(
        "Boundary: "
        f"scope={candidate.target_scope.value}; "
        f"recipient={candidate.intended_recipient_role}; "
        f"risk_owner={candidate.risk_owner_role}"
    )
    print_fn(f"Task: {candidate.task_summary_code}; risk={candidate.declared_risk_level}")
    print_fn("Evidence:")
    for evidence in candidate.evidence:
        print_fn(
            f"- {evidence.evidence_type}: {evidence.status.value} / "
            f"{evidence.summary_code}; blocking={str(evidence.blocking).lower()}"
        )
    print_fn(
        "Official scorer: "
        f"{scorer.outcome.value}; executed={str(scorer.official_scorer_executed).lower()}"
    )
    print_fn("Experimental arm identities and decisions are not available in this flow.")
    started_at = _utc_now()
    choices = {
        "1": ClearanceDisposition.CLEARED,
        "2": ClearanceDisposition.RESTRICTED,
        "3": ClearanceDisposition.HELD,
        "4": ClearanceDisposition.DENIED,
    }
    while True:
        answer = input_fn("decision [1=clear,2=restrict,3=hold,4=deny]: ").strip()
        if answer in choices:
            break
    while True:
        raw_codes = input_fn("rationale codes [comma-separated lowercase identifiers]: ").strip()
        rationale_codes = [item.strip() for item in raw_codes.split(",") if item.strip()]
        if (
            rationale_codes
            and len(set(rationale_codes)) == len(rationale_codes)
            and all(
                RATIONALE_CODE_PATTERN.fullmatch(code) is not None
                for code in rationale_codes
            )
        ):
            break
        print_fn(
            "Provide unique codes such as scorer-passed or blocking-evidence-failed."
        )
    return record_blinded_adjudication(
        packet,
        disposition=choices[answer],
        rationale_codes=rationale_codes,
        adjudicator_role=adjudicator_role,
        started_at=started_at,
        completed_at=_utc_now(),
    )
