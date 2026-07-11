"""Deterministic external-audit report intake without repository self-certification."""

from __future__ import annotations

from base64 import urlsafe_b64decode
from collections import Counter
import hashlib
from typing import Any

from study_anything.cbb.audit.models import (
    AuditExpectedScopeV1,
    AuditFindingCountsV1,
    AuditIntakeState,
    AuditSourceClass,
    ExternalAuditIntakeEnvelopeV1,
    ExternalAuditIntakeReceiptV1,
    ExternalSecurityAuditReportV1,
)
from study_anything.cbb.protocol.canonical import canonical_json_bytes, canonical_sha256
from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    DeliveryScope,
    PrivacyBoundaryV1,
    parse_timestamp,
)


AUDIT_INTAKE_NOT_CLAIMED = [
    "production approval",
    "legal or compliance certification",
    "general AI correctness",
    "vulnerability-free software",
    "external identity from signature possession alone",
    "audit closure from a synthetic fixture",
    "delivery authority",
]


def _privacy() -> PrivacyBoundaryV1:
    return PrivacyBoundaryV1(
        metadata_only=True,
        raw_source_text_included=False,
        raw_report_text_included=False,
        raw_customer_payload_included=False,
        attention_stream_included=False,
        model_prompts_included=False,
        model_credentials_included=False,
        cookies_or_bearer_tokens_included=False,
        signed_urls_included=False,
        production_mutation_performed=False,
        automatic_customer_send_performed=False,
    )


def _decode_base64url(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        return urlsafe_b64decode(value + padding)
    except Exception as exc:  # noqa: BLE001 - normalize detached-signature failure.
        raise ValueError("invalid audit signature encoding") from exc


def audit_report_payload(report: ExternalSecurityAuditReportV1) -> bytes:
    payload = report.model_dump(mode="json")
    payload.pop("signature")
    return canonical_json_bytes(payload)


def audit_report_digest(report: ExternalSecurityAuditReportV1) -> str:
    return canonical_sha256(
        {
            key: value
            for key, value in report.model_dump(mode="json").items()
            if key != "signature"
        }
    )


def _verify_detached_signature(envelope: ExternalAuditIntakeEnvelopeV1) -> bool:
    signature = envelope.detached_signature
    payload = audit_report_payload(envelope.report)
    digest = audit_report_digest(envelope.report)
    if signature.signed_payload_sha256 != digest:
        return False
    if envelope.report.signature.report_sha256 != digest:
        return False
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        public_key_bytes = _decode_base64url(signature.public_key)
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(_decode_base64url(signature.signature), payload)
    except (ImportError, InvalidSignature, ValueError):
        return False
    return True


def _public_key_fingerprint_valid(envelope: ExternalAuditIntakeEnvelopeV1) -> bool:
    try:
        public_key = _decode_base64url(envelope.detached_signature.public_key)
    except ValueError:
        return False
    return (
        hashlib.sha256(public_key).hexdigest()
        == envelope.detached_signature.public_key_fingerprint_sha256
    )


def _finding_counts(envelope: ExternalAuditIntakeEnvelopeV1) -> AuditFindingCountsV1:
    counts = Counter(finding.severity for finding in envelope.findings)
    return AuditFindingCountsV1(
        critical=counts["critical"],
        high=counts["high"],
        medium=counts["medium"],
        low=counts["low"],
        informational=counts["informational"],
    )


def _normalized_actor(value: Any) -> str:
    return str(value).strip().casefold()


def audit_ready_receipt(
    expected_scope: AuditExpectedScopeV1,
    *,
    evaluated_at: str,
) -> ExternalAuditIntakeReceiptV1:
    parse_timestamp(evaluated_at)
    digest = canonical_sha256(
        {
            "state": AuditIntakeState.AUDIT_READY.value,
            "expected_scope": expected_scope.model_dump(mode="json"),
            "evaluated_at": evaluated_at,
        }
    )
    return ExternalAuditIntakeReceiptV1(
        schema_version="external-security-audit-intake-receipt-v1",
        receipt_id=f"external-audit-intake:{digest[:32]}",
        state=AuditIntakeState.AUDIT_READY,
        source_class=None,
        scope_commit=expected_scope.scope_commit,
        report_digest_sha256=None,
        signature_verified=False,
        external_identity_attested=False,
        report_execution_completed=False,
        audit_closure_accepted=False,
        decision=None,
        finding_counts=AuditFindingCountsV1(
            critical=0,
            high=0,
            medium=0,
            low=0,
            informational=0,
        ),
        open_critical_high_count=0,
        checks={"pinned_scope_ready": True, "external_report_present": False},
        blocking_reasons=["external_signed_report_not_received"],
        next_required_actions=[
            "assign an independent human auditor",
            "pin the independently verified auditor public-key fingerprint",
            "return a signed report bound to the pinned commit and package digests",
        ],
        delivery_authority_granted=False,
        production_certification_granted=False,
        claim_boundary=ClaimBoundaryV1(
            current_claim="The exact scope is ready to receive an external audit report.",
            maximum_scope=DeliveryScope.BLOCKED,
            not_claimed=AUDIT_INTAKE_NOT_CLAIMED,
        ),
        privacy=_privacy(),
        evaluated_at=evaluated_at,
    )


def evaluate_external_audit_intake(
    expected_scope: AuditExpectedScopeV1,
    envelope: ExternalAuditIntakeEnvelopeV1,
    *,
    evaluated_at: str,
) -> ExternalAuditIntakeReceiptV1:
    """Validate a detached report and resolve intake state without granting delivery scope."""

    parse_timestamp(evaluated_at)
    report = envelope.report
    counts = _finding_counts(envelope)
    reported_counts = report.finding_counts.model_dump(mode="json")
    actual_counts = counts.model_dump(mode="json")
    actors = {_normalized_actor(item) for item in expected_scope.repository_actor_refs}
    organization = _normalized_actor(report.auditor["organization"])
    reviewer = _normalized_actor(report.auditor["lead_human_reviewer"])
    report_completed_at = parse_timestamp(report.review_period["completed_at"])
    submitted_at = parse_timestamp(envelope.submitted_at)
    required_scope = set(expected_scope.required_scope_areas)
    observed_scope = set(report.scope_areas)
    open_critical_high = sum(
        1
        for finding in envelope.findings
        if finding.severity in {"critical", "high"} and finding.status != "verified"
    )
    all_required_retests_passed = all(
        not finding.retest.required or finding.retest.status == "passed"
        for finding in envelope.findings
    )
    all_findings_closed = all(
        finding.status in {"verified", "risk_accepted"}
        for finding in envelope.findings
    )
    signature_verified = _verify_detached_signature(envelope)
    public_key_fingerprint_valid = _public_key_fingerprint_valid(envelope)
    signer_trusted_by_expected_scope = (
        envelope.detached_signature.public_key_fingerprint_sha256
        in expected_scope.trusted_auditor_fingerprints
    )
    external_identity_attested = (
        envelope.source_class == AuditSourceClass.EXTERNAL_REPORT
        and envelope.auditor_trust.identity_status == "externally_attested"
        and envelope.auditor_trust.independent_from_repository
        and not envelope.auditor_trust.fixture_only
        and public_key_fingerprint_valid
        and signer_trusted_by_expected_scope
    )
    checks = {
        "repository_matches": report.repository == expected_scope.repository,
        "scope_commit_matches": report.scope_commit == expected_scope.scope_commit,
        "audit_pack_digest_matches": (
            report.evidence_bindings.audit_pack_sha256
            == expected_scope.audit_pack_sha256
        ),
        "conformance_pack_digest_matches": (
            report.evidence_bindings.conformance_pack_sha256
            == expected_scope.conformance_pack_sha256
        ),
        "audit_plan_digest_matches": (
            report.evidence_bindings.audit_plan_sha256
            == expected_scope.audit_plan_sha256
        ),
        "required_scope_complete": required_scope.issubset(observed_scope),
        "signature_reference_matches": (
            report.signature.signature_ref == f"detached:{envelope.envelope_id}"
        ),
        "detached_signature_verified": signature_verified,
        "public_key_fingerprint_valid": public_key_fingerprint_valid,
        "signer_fingerprint_matches": (
            envelope.detached_signature.public_key_fingerprint_sha256
            == envelope.auditor_trust.public_key_fingerprint_sha256
        ),
        "source_identity_class_consistent": (
            envelope.source_class
            in {
                AuditSourceClass.SYNTHETIC_FIXTURE,
                AuditSourceClass.EXTERNAL_SHAPE_FIXTURE,
            }
            and envelope.auditor_trust.fixture_only
        )
        or external_identity_attested,
        "signer_trusted_for_source_class": (
            envelope.source_class != AuditSourceClass.EXTERNAL_REPORT
            or signer_trusted_by_expected_scope
        ),
        "repository_self_certification_rejected": (
            organization not in actors and reviewer not in actors
        ),
        "finding_refs_match": sorted(report.finding_refs)
        == sorted(finding.finding_id for finding in envelope.findings),
        "finding_counts_match": reported_counts == actual_counts,
        "finding_scope_matches": all(
            finding.scope_commit == expected_scope.scope_commit
            for finding in envelope.findings
        ),
        "submitted_after_completion": submitted_at >= report_completed_at,
        "critical_high_closed": open_critical_high == 0,
        "required_retests_passed": all_required_retests_passed,
        "all_findings_closed": all_findings_closed,
        "decision_is_pass": report.decision == "pass",
    }
    hard_checks = {
        key: checks[key]
        for key in (
            "repository_matches",
            "scope_commit_matches",
            "audit_pack_digest_matches",
            "conformance_pack_digest_matches",
            "audit_plan_digest_matches",
            "required_scope_complete",
            "signature_reference_matches",
            "detached_signature_verified",
            "public_key_fingerprint_valid",
            "signer_fingerprint_matches",
            "source_identity_class_consistent",
            "signer_trusted_for_source_class",
            "repository_self_certification_rejected",
            "finding_refs_match",
            "finding_counts_match",
            "finding_scope_matches",
            "submitted_after_completion",
        )
    }
    hard_failures = sorted(key for key, passed in hard_checks.items() if not passed)

    if hard_failures:
        state = AuditIntakeState.REJECTED
        report_execution_completed = False
        closure = False
        next_actions = ["correct rejected audit evidence and resubmit"]
    elif envelope.source_class == AuditSourceClass.SYNTHETIC_FIXTURE:
        state = AuditIntakeState.SYNTHETIC_VALIDATED
        report_execution_completed = False
        closure = False
        next_actions = ["obtain a report from an independently attested external auditor"]
    elif envelope.source_class == AuditSourceClass.EXTERNAL_SHAPE_FIXTURE:
        state = (
            AuditIntakeState.REMEDIATION_PENDING
            if open_critical_high or report.decision == "fail"
            else AuditIntakeState.SYNTHETIC_VALIDATED
        )
        report_execution_completed = False
        closure = False
        next_actions = ["replace fixture-shaped evidence with a real external report"]
    elif open_critical_high or report.decision == "fail":
        state = AuditIntakeState.REMEDIATION_PENDING
        report_execution_completed = True
        closure = False
        next_actions = [
            "remediate every critical and high finding",
            "obtain required independent retests",
        ]
    elif (
        report.decision != "pass"
        or not all_required_retests_passed
        or not all_findings_closed
    ):
        state = AuditIntakeState.AUDIT_RECEIVED
        report_execution_completed = True
        closure = False
        next_actions = ["resolve remaining findings and submit a signed closure addendum"]
    else:
        state = AuditIntakeState.AUDIT_CLOSED
        report_execution_completed = True
        closure = True
        next_actions = ["retain signed evidence and continue outcome monitoring"]

    digest = audit_report_digest(report)
    receipt_digest = canonical_sha256(
        {
            "expected_scope": expected_scope.model_dump(mode="json"),
            "envelope_id": envelope.envelope_id,
            "report_digest_sha256": digest,
            "state": state.value,
            "checks": checks,
            "evaluated_at": evaluated_at,
        }
    )
    return ExternalAuditIntakeReceiptV1(
        schema_version="external-security-audit-intake-receipt-v1",
        receipt_id=f"external-audit-intake:{receipt_digest[:32]}",
        state=state,
        source_class=envelope.source_class,
        scope_commit=expected_scope.scope_commit,
        report_digest_sha256=digest,
        signature_verified=signature_verified,
        external_identity_attested=external_identity_attested,
        report_execution_completed=report_execution_completed,
        audit_closure_accepted=closure,
        decision=report.decision,
        finding_counts=counts,
        open_critical_high_count=open_critical_high,
        checks=checks,
        blocking_reasons=hard_failures,
        next_required_actions=next_actions,
        delivery_authority_granted=False,
        production_certification_granted=False,
        claim_boundary=ClaimBoundaryV1(
            current_claim=(
                "This receipt records whether an externally supplied audit report can "
                "enter the repository audit state machine."
            ),
            maximum_scope=DeliveryScope.BLOCKED,
            not_claimed=AUDIT_INTAKE_NOT_CLAIMED,
        ),
        privacy=_privacy(),
        evaluated_at=evaluated_at,
    )
