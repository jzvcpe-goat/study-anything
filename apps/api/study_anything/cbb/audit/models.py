"""Strict contracts for externally signed audit-report intake and closure state."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    PrivacyBoundaryV1,
    StrictProtocolModel,
    parse_timestamp,
)


AUDIT_INTAKE_ENVELOPE_SCHEMA_VERSION: Literal[
    "external-security-audit-intake-envelope-v1"
] = "external-security-audit-intake-envelope-v1"
AUDIT_INTAKE_RECEIPT_SCHEMA_VERSION: Literal[
    "external-security-audit-intake-receipt-v1"
] = "external-security-audit-intake-receipt-v1"
Sha256Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class AuditSourceClass(StrEnum):
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    EXTERNAL_SHAPE_FIXTURE = "external_shape_fixture"
    EXTERNAL_REPORT = "external_report"


class AuditIntakeState(StrEnum):
    AUDIT_READY = "audit_ready"
    REJECTED = "rejected"
    SYNTHETIC_VALIDATED = "synthetic_validated"
    AUDIT_RECEIVED = "audit_received"
    REMEDIATION_PENDING = "remediation_pending"
    AUDIT_CLOSED = "audit_closed"


class AuditEvidenceBindingV1(StrictProtocolModel):
    protocol_version: Literal["1.0.0"]
    audit_pack_ref: str = Field(min_length=1, max_length=500)
    audit_pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conformance_pack_ref: str = Field(min_length=1, max_length=500)
    conformance_pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_plan_ref: str = Field(min_length=1, max_length=500)
    audit_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AuditFindingEvidenceV1(StrictProtocolModel):
    artifact_ref: str = Field(min_length=2, max_length=240)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation: str = Field(min_length=3, max_length=500)


class AuditAffectedSurfaceV1(StrictProtocolModel):
    component: str = Field(min_length=2, max_length=120)
    public_reference: str = Field(min_length=2, max_length=240)


class AuditRemediationV1(StrictProtocolModel):
    owner: str = Field(min_length=2, max_length=120)
    target_date: str
    commit_ref: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")

    @model_validator(mode="after")
    def validate_target_date(self) -> AuditRemediationV1:
        date.fromisoformat(self.target_date)
        return self


class AuditRetestV1(StrictProtocolModel):
    required: bool
    status: Literal["not_started", "passed", "failed", "not_required"]

    @model_validator(mode="after")
    def validate_retest(self) -> AuditRetestV1:
        if self.required and self.status == "not_required":
            raise ValueError("required retest cannot be marked not_required")
        if not self.required and self.status not in {"not_required", "passed"}:
            raise ValueError("optional retest cannot claim an incomplete execution")
        return self


class AuditFindingPrivacyV1(StrictProtocolModel):
    metadata_only_public_record: Literal[True]
    real_secrets_included: Literal[False]
    customer_payloads_included: Literal[False]
    private_exploit_details_included: Literal[False]


class ExternalSecurityAuditFindingV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": "external-security-audit-finding-v1"},
    )

    schema_version: Literal["external-security-audit-finding-v1"]
    finding_id: str = Field(pattern=r"^AUD-[0-9]{4}$")
    status: Literal["open", "remediated", "verified", "risk_accepted"]
    severity: Literal["critical", "high", "medium", "low", "informational"]
    title: str = Field(min_length=5, max_length=160)
    category: str = Field(min_length=3, max_length=80)
    scope_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    affected_surface: AuditAffectedSurfaceV1
    evidence: list[AuditFindingEvidenceV1] = Field(min_length=1)
    impact_summary: str = Field(min_length=3, max_length=1000)
    remediation: AuditRemediationV1
    retest: AuditRetestV1
    privacy: AuditFindingPrivacyV1

    @model_validator(mode="after")
    def validate_finding(self) -> ExternalSecurityAuditFindingV1:
        if self.severity in {"critical", "high"} and self.status == "risk_accepted":
            raise ValueError("critical and high findings cannot close through risk acceptance")
        if self.status == "verified" and self.retest.required and self.retest.status != "passed":
            raise ValueError("verified finding requires a passed mandatory retest")
        return self


class AuditFindingCountsV1(StrictProtocolModel):
    critical: int = Field(ge=0)
    high: int = Field(ge=0)
    medium: int = Field(ge=0)
    low: int = Field(ge=0)
    informational: int = Field(ge=0)


class AuditReportSignatureMetadataV1(StrictProtocolModel):
    method: Literal["gpg", "minisign", "sigstore", "other"]
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature_ref: str = Field(min_length=3, max_length=240)


class AuditReportClaimBoundaryV1(StrictProtocolModel):
    audit_completed: Literal[True]
    production_certification: Literal[False]
    legal_certification: Literal[False]
    general_model_correctness: Literal[False]


class ExternalSecurityAuditReportV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": "external-security-audit-report-v1"},
    )

    schema_version: Literal["external-security-audit-report-v1"]
    audit_status: Literal["completed_by_independent_auditor"]
    decision: Literal["pass", "conditional_pass", "fail"]
    repository: Literal["jzvcpe-goat/study-anything"]
    scope_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    auditor: dict[str, str | bool]
    review_period: dict[str, str]
    scope_areas: list[str] = Field(min_length=1)
    evidence_bindings: AuditEvidenceBindingV1
    finding_refs: list[str]
    finding_counts: AuditFindingCountsV1
    signature: AuditReportSignatureMetadataV1
    claim_boundary: AuditReportClaimBoundaryV1

    @model_validator(mode="after")
    def validate_report(self) -> ExternalSecurityAuditReportV1:
        expected_auditor_keys = {
            "organization",
            "lead_human_reviewer",
            "independence_attested",
        }
        if set(self.auditor) != expected_auditor_keys:
            raise ValueError("audit report auditor fields are incomplete or unknown")
        if self.auditor["independence_attested"] is not True:
            raise ValueError("audit report requires independent human attestation")
        if not str(self.auditor["organization"]).strip() or not str(
            self.auditor["lead_human_reviewer"]
        ).strip():
            raise ValueError("audit report requires named external actors")
        if set(self.review_period) != {"started_at", "completed_at"}:
            raise ValueError("audit report review period fields are incomplete")
        if parse_timestamp(self.review_period["completed_at"]) <= parse_timestamp(
            self.review_period["started_at"]
        ):
            raise ValueError("audit completion must follow audit start")
        if len(self.scope_areas) != len(set(self.scope_areas)):
            raise ValueError("audit report scope areas must be unique")
        if len(self.finding_refs) != len(set(self.finding_refs)):
            raise ValueError("audit report finding refs must be unique")
        if any(not ref.startswith("AUD-") for ref in self.finding_refs):
            raise ValueError("audit report finding ref is malformed")
        return self


class AuditDetachedSignatureV1(StrictProtocolModel):
    algorithm: Literal["ed25519"]
    public_key_encoding: Literal["ed25519-raw-base64url"]
    public_key: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    public_key_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signed_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature: str = Field(pattern=r"^[A-Za-z0-9_-]{86}$")


class AuditorTrustRecordV1(StrictProtocolModel):
    organization: str = Field(min_length=2, max_length=160)
    lead_human_reviewer: str = Field(min_length=2, max_length=160)
    public_key_fingerprint_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_status: Literal["synthetic_fixture", "externally_attested"]
    independence_attestation_ref: str = Field(min_length=3, max_length=500)
    independent_from_repository: bool
    fixture_only: bool

    @model_validator(mode="after")
    def validate_identity_state(self) -> AuditorTrustRecordV1:
        if self.identity_status == "synthetic_fixture":
            if not self.fixture_only or self.independent_from_repository:
                raise ValueError("synthetic auditor identity cannot claim external independence")
        elif self.fixture_only or not self.independent_from_repository:
            raise ValueError("external auditor identity requires independent attestation")
        return self


class AuditExpectedScopeV1(StrictProtocolModel):
    repository: Literal["jzvcpe-goat/study-anything"]
    scope_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    audit_pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conformance_pack_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    audit_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_scope_areas: list[str] = Field(min_length=1)
    repository_actor_refs: list[str] = Field(min_length=1)
    trusted_auditor_fingerprints: list[Sha256Fingerprint] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_expected_scope(self) -> AuditExpectedScopeV1:
        if len(self.required_scope_areas) != len(set(self.required_scope_areas)):
            raise ValueError("required audit scope areas must be unique")
        if len(self.trusted_auditor_fingerprints) != len(
            set(self.trusted_auditor_fingerprints)
        ):
            raise ValueError("trusted auditor fingerprints must be unique")
        return self


class ExternalAuditIntakeEnvelopeV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": AUDIT_INTAKE_ENVELOPE_SCHEMA_VERSION},
    )

    schema_version: Literal["external-security-audit-intake-envelope-v1"]
    envelope_id: str = Field(min_length=1, max_length=200)
    source_class: AuditSourceClass
    report: ExternalSecurityAuditReportV1
    findings: list[ExternalSecurityAuditFindingV1]
    detached_signature: AuditDetachedSignatureV1
    auditor_trust: AuditorTrustRecordV1
    submitted_at: str = Field(min_length=1, max_length=64)
    privacy: PrivacyBoundaryV1

    @model_validator(mode="after")
    def validate_envelope(self) -> ExternalAuditIntakeEnvelopeV1:
        parse_timestamp(self.submitted_at)
        organization = str(self.report.auditor["organization"])
        reviewer = str(self.report.auditor["lead_human_reviewer"])
        if organization != self.auditor_trust.organization or reviewer != self.auditor_trust.lead_human_reviewer:
            raise ValueError("auditor identity does not match report")
        if (
            self.detached_signature.public_key_fingerprint_sha256
            != self.auditor_trust.public_key_fingerprint_sha256
        ):
            raise ValueError("audit signer fingerprint does not match trust record")
        if self.source_class in {
            AuditSourceClass.SYNTHETIC_FIXTURE,
            AuditSourceClass.EXTERNAL_SHAPE_FIXTURE,
        }:
            if self.auditor_trust.identity_status != "synthetic_fixture":
                raise ValueError("synthetic intake requires a fixture-only identity")
        elif self.auditor_trust.identity_status != "externally_attested":
            raise ValueError("external report requires externally attested identity")
        finding_ids = [finding.finding_id for finding in self.findings]
        if sorted(finding_ids) != sorted(self.report.finding_refs):
            raise ValueError("audit finding documents do not match report refs")
        if any(finding.scope_commit != self.report.scope_commit for finding in self.findings):
            raise ValueError("audit finding scope commit does not match report")
        return self


class ExternalAuditIntakeReceiptV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": AUDIT_INTAKE_RECEIPT_SCHEMA_VERSION},
    )

    schema_version: Literal["external-security-audit-intake-receipt-v1"]
    receipt_id: str = Field(min_length=1, max_length=200)
    state: AuditIntakeState
    source_class: AuditSourceClass | None
    scope_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    report_digest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    signature_verified: bool
    external_identity_attested: bool
    report_execution_completed: bool
    audit_closure_accepted: bool
    decision: Literal["pass", "conditional_pass", "fail"] | None
    finding_counts: AuditFindingCountsV1
    open_critical_high_count: int = Field(ge=0)
    checks: dict[str, bool] = Field(min_length=1)
    blocking_reasons: list[str]
    next_required_actions: list[str] = Field(min_length=1)
    delivery_authority_granted: Literal[False]
    production_certification_granted: Literal[False]
    claim_boundary: ClaimBoundaryV1
    privacy: PrivacyBoundaryV1
    evaluated_at: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_receipt(self) -> ExternalAuditIntakeReceiptV1:
        parse_timestamp(self.evaluated_at)
        if self.state == AuditIntakeState.AUDIT_CLOSED:
            if (
                not self.audit_closure_accepted
                or not self.report_execution_completed
                or not self.signature_verified
                or not self.external_identity_attested
                or self.source_class != AuditSourceClass.EXTERNAL_REPORT
                or self.open_critical_high_count
            ):
                raise ValueError("audit closure requires valid independent external evidence")
        elif self.audit_closure_accepted:
            raise ValueError("non-closed audit intake cannot accept closure")
        if self.state == AuditIntakeState.SYNTHETIC_VALIDATED and self.report_execution_completed:
            raise ValueError("synthetic fixture cannot claim completed external audit execution")
        return self
