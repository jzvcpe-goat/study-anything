"""Synthetic-only fixtures for audit intake; none can close the real audit."""

from __future__ import annotations

from base64 import urlsafe_b64encode
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Literal, cast

from study_anything.cbb.audit.intake import (
    audit_ready_receipt,
    audit_report_digest,
    audit_report_payload,
    evaluate_external_audit_intake,
)
from study_anything.cbb.audit.models import (
    AuditAffectedSurfaceV1,
    AuditDetachedSignatureV1,
    AuditEvidenceBindingV1,
    AuditExpectedScopeV1,
    AuditFindingCountsV1,
    AuditFindingEvidenceV1,
    AuditFindingPrivacyV1,
    AuditRemediationV1,
    AuditReportClaimBoundaryV1,
    AuditReportSignatureMetadataV1,
    AuditRetestV1,
    AuditSourceClass,
    AuditorTrustRecordV1,
    ExternalAuditIntakeEnvelopeV1,
    ExternalAuditIntakeReceiptV1,
    ExternalSecurityAuditFindingV1,
    ExternalSecurityAuditReportV1,
)
from study_anything.cbb.protocol.canonical import canonical_sha256, model_payload, schema_text
from study_anything.cbb.protocol.models import PrivacyBoundaryV1


FIXTURE_ROOT = Path("fixtures") / "cbb-external-audit-intake"
PINNED_SCOPE_COMMIT = "1ada8ffa6318b91e38ec69bc5cd14dc294950518"
PINNED_AUDIT_PACK_SHA256 = (
    "a511697dd3cdec593b71dfdc8968b39ae8ff3a373bb348337733374fac4bc0f5"
)
EVALUATED_AT = "2026-07-14T00:00:00Z"


def _b64url(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def fixture_private_key() -> Any:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"delivery-clearance-external-audit-intake-fixture").digest()
    )


def _public_key_bytes(private_key: Any) -> bytes:
    from cryptography.hazmat.primitives import serialization

    return cast(
        bytes,
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ),
    )


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


def _plan(root: Path) -> dict[str, Any]:
    payload = json.loads(
        (root / "security" / "audit" / "audit-plan.json").read_text(encoding="utf-8")
    )
    if not isinstance(payload, dict):
        raise ValueError("audit plan must be a JSON object")
    return cast(dict[str, Any], payload)


def expected_scope(root: Path) -> AuditExpectedScopeV1:
    conformance = json.loads(
        (
            root
            / "platform"
            / "generated"
            / "study-anything-cbb-v1-conformance-pack.json"
        ).read_text(encoding="utf-8")
    )
    audit_plan_path = root / "security" / "audit" / "audit-plan.json"
    plan = _plan(root)
    return AuditExpectedScopeV1(
        repository="jzvcpe-goat/study-anything",
        scope_commit=PINNED_SCOPE_COMMIT,
        audit_pack_sha256=PINNED_AUDIT_PACK_SHA256,
        conformance_pack_sha256=conformance["archive_sha256"],
        audit_plan_sha256=hashlib.sha256(audit_plan_path.read_bytes()).hexdigest(),
        required_scope_areas=[area["id"] for area in plan["scope_areas"]],
        repository_actor_refs=[
            "jzvcpe-goat",
            "study-anything-maintainers",
            "repository-maintainer",
        ],
        trusted_auditor_fingerprints=[],
    )


def _finding(
    scope_commit: str,
    *,
    status: Literal["open", "remediated", "verified", "risk_accepted"] = "open",
) -> ExternalSecurityAuditFindingV1:
    return ExternalSecurityAuditFindingV1(
        schema_version="external-security-audit-finding-v1",
        finding_id="AUD-0001",
        status=status,
        severity="high",
        title="Synthetic high-severity intake fixture",
        category="fixture-boundary",
        scope_commit=scope_commit,
        affected_surface=AuditAffectedSurfaceV1(
            component="audit-intake-fixture",
            public_reference="fixtures/cbb-external-audit-intake/open-high.json",
        ),
        evidence=[
            AuditFindingEvidenceV1(
                artifact_ref="fixture:synthetic-observation",
                sha256="1" * 64,
                observation="Synthetic metadata used only to exercise remediation state.",
            )
        ],
        impact_summary="Synthetic fixture; no real vulnerability or customer impact is claimed.",
        remediation=AuditRemediationV1(
            owner="fixture-owner",
            target_date="2026-08-01",
            commit_ref=None,
        ),
        retest=AuditRetestV1(required=True, status="not_started"),
        privacy=AuditFindingPrivacyV1(
            metadata_only_public_record=True,
            real_secrets_included=False,
            customer_payloads_included=False,
            private_exploit_details_included=False,
        ),
    )


def _counts(findings: list[ExternalSecurityAuditFindingV1]) -> AuditFindingCountsV1:
    counts = Counter(finding.severity for finding in findings)
    return AuditFindingCountsV1(
        critical=counts["critical"],
        high=counts["high"],
        medium=counts["medium"],
        low=counts["low"],
        informational=counts["informational"],
    )


def _report(
    root: Path,
    *,
    envelope_id: str,
    source_class: AuditSourceClass,
    scope_commit: str | None = None,
    organization: str = "Synthetic Audit Fixture Lab",
    reviewer: str = "fixture-human-reviewer",
    scope_areas: list[str] | None = None,
    findings: list[ExternalSecurityAuditFindingV1] | None = None,
    decision: str = "pass",
) -> tuple[ExternalSecurityAuditReportV1, AuditDetachedSignatureV1, AuditorTrustRecordV1]:
    expected = expected_scope(root)
    report_scope = scope_commit or expected.scope_commit
    finding_items = findings or []
    payload: dict[str, Any] = {
        "schema_version": "external-security-audit-report-v1",
        "audit_status": "completed_by_independent_auditor",
        "decision": decision,
        "repository": expected.repository,
        "scope_commit": report_scope,
        "auditor": {
            "organization": organization,
            "lead_human_reviewer": reviewer,
            "independence_attested": True,
        },
        "review_period": {
            "started_at": "2026-07-12T00:00:00Z",
            "completed_at": "2026-07-13T00:00:00Z",
        },
        "scope_areas": scope_areas or list(expected.required_scope_areas),
        "evidence_bindings": model_payload(
            AuditEvidenceBindingV1(
                protocol_version="1.0.0",
                audit_pack_ref="platform/generated/study-anything-external-security-audit-pack.zip",
                audit_pack_sha256=expected.audit_pack_sha256,
                conformance_pack_ref="platform/generated/study-anything-cbb-v1-conformance-pack.zip",
                conformance_pack_sha256=expected.conformance_pack_sha256,
                audit_plan_ref="security/audit/audit-plan.json",
                audit_plan_sha256=expected.audit_plan_sha256,
            )
        ),
        "finding_refs": [finding.finding_id for finding in finding_items],
        "finding_counts": model_payload(_counts(finding_items)),
        "claim_boundary": model_payload(
            AuditReportClaimBoundaryV1(
                audit_completed=True,
                production_certification=False,
                legal_certification=False,
                general_model_correctness=False,
            )
        ),
    }
    report_digest = canonical_sha256(payload)
    payload["signature"] = model_payload(
        AuditReportSignatureMetadataV1(
            method="other",
            report_sha256=report_digest,
            signature_ref=f"detached:{envelope_id}",
        )
    )
    report = ExternalSecurityAuditReportV1.model_validate(payload)
    private_key = fixture_private_key()
    public_key = _public_key_bytes(private_key)
    signature = private_key.sign(audit_report_payload(report))
    detached = AuditDetachedSignatureV1(
        algorithm="ed25519",
        public_key_encoding="ed25519-raw-base64url",
        public_key=_b64url(public_key),
        public_key_fingerprint_sha256=hashlib.sha256(public_key).hexdigest(),
        signed_payload_sha256=audit_report_digest(report),
        signature=_b64url(signature),
    )
    trust = AuditorTrustRecordV1(
        organization=organization,
        lead_human_reviewer=reviewer,
        public_key_fingerprint_sha256=hashlib.sha256(public_key).hexdigest(),
        identity_status="synthetic_fixture",
        independence_attestation_ref="fixture-only:no-external-identity",
        independent_from_repository=False,
        fixture_only=True,
    )
    return report, detached, trust


def _envelope(
    root: Path,
    case_id: str,
    *,
    source_class: AuditSourceClass = AuditSourceClass.SYNTHETIC_FIXTURE,
    scope_commit: str | None = None,
    organization: str = "Synthetic Audit Fixture Lab",
    reviewer: str = "fixture-human-reviewer",
    scope_areas: list[str] | None = None,
    findings: list[ExternalSecurityAuditFindingV1] | None = None,
    decision: str = "pass",
) -> ExternalAuditIntakeEnvelopeV1:
    envelope_id = f"audit-intake-envelope:{case_id}"
    report, detached, trust = _report(
        root,
        envelope_id=envelope_id,
        source_class=source_class,
        scope_commit=scope_commit,
        organization=organization,
        reviewer=reviewer,
        scope_areas=scope_areas,
        findings=findings,
        decision=decision,
    )
    return ExternalAuditIntakeEnvelopeV1(
        schema_version="external-security-audit-intake-envelope-v1",
        envelope_id=envelope_id,
        source_class=source_class,
        report=report,
        findings=findings or [],
        detached_signature=detached,
        auditor_trust=trust,
        submitted_at="2026-07-13T12:00:00Z",
        privacy=_privacy(),
    )


def build_audit_intake_cases(root: Path) -> dict[str, dict[str, Any]]:
    expected = expected_scope(root)
    ready = audit_ready_receipt(expected, evaluated_at=EVALUATED_AT)
    envelopes: dict[str, ExternalAuditIntakeEnvelopeV1] = {
        "synthetic-valid": _envelope(root, "synthetic-valid"),
        "wrong-commit": _envelope(root, "wrong-commit", scope_commit="0" * 40),
        "incomplete-scope": _envelope(
            root,
            "incomplete-scope",
            scope_areas=list(expected.required_scope_areas[:-1]),
        ),
        "self-certified": _envelope(
            root,
            "self-certified",
            source_class=AuditSourceClass.EXTERNAL_SHAPE_FIXTURE,
            organization="jzvcpe-goat",
            reviewer="repository-maintainer",
        ),
        "open-high": _envelope(
            root,
            "open-high",
            source_class=AuditSourceClass.EXTERNAL_SHAPE_FIXTURE,
            findings=[_finding(expected.scope_commit)],
            decision="conditional_pass",
        ),
    }
    invalid_signature = deepcopy(model_payload(_envelope(root, "invalid-signature")))
    original_signature = invalid_signature["detached_signature"]["signature"]
    invalid_signature["detached_signature"]["signature"] = (
        ("A" if original_signature[0] != "A" else "B") + original_signature[1:]
    )
    envelopes["invalid-signature"] = ExternalAuditIntakeEnvelopeV1.model_validate(
        invalid_signature
    )

    result: dict[str, dict[str, Any]] = {
        "audit-ready": {
            "case_id": "audit-ready",
            "fixture_class": "no_external_report",
            "expected_scope": model_payload(expected),
            "envelope": None,
            "receipt": model_payload(ready),
            "expected": {
                "state": ready.state.value,
                "audit_closure_accepted": False,
                "report_execution_completed": False,
            },
        }
    }
    for case_id, envelope in envelopes.items():
        receipt = evaluate_external_audit_intake(
            expected,
            envelope,
            evaluated_at=EVALUATED_AT,
        )
        result[case_id] = {
            "case_id": case_id,
            "fixture_class": (
                "synthetic_signature_fixture"
                if envelope.source_class == AuditSourceClass.SYNTHETIC_FIXTURE
                else "synthetic_negative_external_shape"
            ),
            "expected_scope": model_payload(expected),
            "envelope": model_payload(envelope),
            "receipt": model_payload(receipt),
            "expected": {
                "state": receipt.state.value,
                "audit_closure_accepted": False,
                "report_execution_completed": False,
            },
        }
    return result


def asset_outputs(root: Path) -> dict[Path, str]:
    schema_dir = root / "platform" / "schemas" / "security"
    fixture_dir = root / FIXTURE_ROOT
    outputs = {
        schema_dir
        / "external-security-audit-intake-envelope-v1.schema.json": schema_text(
            ExternalAuditIntakeEnvelopeV1
        ),
        schema_dir
        / "external-security-audit-intake-receipt-v1.schema.json": schema_text(
            ExternalAuditIntakeReceiptV1
        ),
    }
    outputs.update(
        {
            fixture_dir / f"{case_id}.json": json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
            for case_id, payload in build_audit_intake_cases(root).items()
        }
    )
    return outputs
