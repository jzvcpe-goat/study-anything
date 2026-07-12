"""Strict contracts for plugin evidence used by personal-local clearance."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    DeliveryScope,
    PrivacyBoundaryV1,
    StrictProtocolModel,
    parse_timestamp,
)


PLUGIN_EVIDENCE_SCHEMA_VERSION: Literal["delivery-clearance.plugin-evidence.v1"] = (
    "delivery-clearance.plugin-evidence.v1"
)
PLUGIN_EVIDENCE_DECISION_SCHEMA_VERSION: Literal[
    "delivery-clearance.plugin-evidence-decision.v1"
] = "delivery-clearance.plugin-evidence-decision.v1"

SHA256_PATTERN = r"^[0-9a-f]{64}$"
PLUGIN_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,119}$"
EVIDENCE_ID_PATTERN = r"^[a-z0-9][a-z0-9._:-]{0,159}$"


class PluginCapability(StrEnum):
    LOCAL_READ = "local_read"
    LOCAL_WRITE = "local_write"
    EXTERNAL_READ = "external_read"
    EXTERNAL_WRITE = "external_write"
    INTERACTIVE_UI = "interactive_ui"
    PROFESSIONAL_JUDGMENT = "professional_judgment"


class PluginRuntimeStatus(StrEnum):
    READY = "ready"
    FAILED = "failed"
    TIMEOUT = "timeout"
    NOT_RUN = "not_run"


class PluginEvidenceStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class PluginCheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"
    NOT_RUN = "not_run"


class PluginInputSourceClass(StrEnum):
    GIT_BOUND = "git_bound"
    LOCAL_UNBOUND = "local_unbound"
    EXTERNAL_MUTABLE = "external_mutable"


class PluginPackageEvidenceV1(StrictProtocolModel):
    plugin_id: str = Field(pattern=PLUGIN_ID_PATTERN)
    plugin_version: str = Field(min_length=1, max_length=80)
    package_digest_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    manifest_digest_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)


class PluginRuntimeEvidenceV1(StrictProtocolModel):
    status: PluginRuntimeStatus
    dependency_check: PluginEvidenceStatus
    execution_digest_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    observed_at: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_runtime(self) -> PluginRuntimeEvidenceV1:
        if self.observed_at is not None:
            parse_timestamp(self.observed_at)
        if self.status == PluginRuntimeStatus.READY:
            if self.execution_digest_sha256 is None or self.observed_at is None:
                raise ValueError("ready plugin runtime requires bound execution evidence")
        if self.status == PluginRuntimeStatus.NOT_RUN and (
            self.execution_digest_sha256 is not None or self.observed_at is not None
        ):
            raise ValueError("not-run plugin runtime cannot include execution evidence")
        return self


class PluginInputEvidenceV1(StrictProtocolModel):
    input_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    source_class: PluginInputSourceClass
    content_digest_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    observed_at: str = Field(min_length=1, max_length=64)
    valid_until: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_input_window(self) -> PluginInputEvidenceV1:
        observed = parse_timestamp(self.observed_at)
        if self.valid_until is not None:
            valid_until = parse_timestamp(self.valid_until)
            if valid_until <= observed:
                raise ValueError("plugin input validity must end after observation")
        return self


class PluginEffectEvidenceV1(StrictProtocolModel):
    project_git_mutation_observed: bool
    project_mutation_bound_to_subject_digest: bool
    post_run_subject_digest_sha256: str | None = Field(
        default=None,
        pattern=SHA256_PATTERN,
    )
    network_access_observed: bool
    external_mutation_observed: bool
    credentials_used: bool

    @model_validator(mode="after")
    def validate_project_binding(self) -> PluginEffectEvidenceV1:
        if self.project_mutation_bound_to_subject_digest != (
            self.post_run_subject_digest_sha256 is not None
        ):
            raise ValueError("project mutation binding must match its subject digest")
        return self


class PluginCheckEvidenceV1(StrictProtocolModel):
    check_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    status: PluginCheckStatus
    required: Literal[True] = True
    result_digest_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    observed_at: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_check(self) -> PluginCheckEvidenceV1:
        if self.observed_at is not None:
            parse_timestamp(self.observed_at)
        if self.status == PluginCheckStatus.PASSED:
            if self.result_digest_sha256 is None or self.observed_at is None:
                raise ValueError("passed plugin check requires a bound result")
        if self.status == PluginCheckStatus.NOT_RUN and (
            self.result_digest_sha256 is not None or self.observed_at is not None
        ):
            raise ValueError("not-run plugin check cannot include result evidence")
        return self


class PluginNativeVerificationV1(StrictProtocolModel):
    status: PluginEvidenceStatus
    verifier_kind: str | None = Field(default=None, min_length=1, max_length=120)
    verification_digest_sha256: str | None = Field(
        default=None,
        pattern=SHA256_PATTERN,
    )
    observed_at: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_native_verification(self) -> PluginNativeVerificationV1:
        if self.observed_at is not None:
            parse_timestamp(self.observed_at)
        details_present = (
            self.verifier_kind is not None,
            self.verification_digest_sha256 is not None,
            self.observed_at is not None,
        )
        if self.status == PluginEvidenceStatus.PASSED and not all(details_present):
            raise ValueError("passed native verification requires bound verifier evidence")
        if self.status == PluginEvidenceStatus.NOT_APPLICABLE and any(details_present):
            raise ValueError("not-applicable native verification cannot include evidence")
        return self


class PluginDomainEvidenceV1(StrictProtocolModel):
    status: PluginEvidenceStatus
    domain_profile_ref: str | None = Field(default=None, min_length=1, max_length=200)
    domain_profile_digest_sha256: str | None = Field(
        default=None,
        pattern=SHA256_PATTERN,
    )
    evaluator_digest_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    qualified_reconstruction: PluginEvidenceStatus

    @model_validator(mode="after")
    def validate_domain_evidence(self) -> PluginDomainEvidenceV1:
        details_present = (
            self.domain_profile_ref is not None,
            self.domain_profile_digest_sha256 is not None,
            self.evaluator_digest_sha256 is not None,
        )
        if self.status == PluginEvidenceStatus.PASSED:
            if not all(details_present):
                raise ValueError("passed domain evidence requires a profile and evaluator")
            if self.qualified_reconstruction != PluginEvidenceStatus.PASSED:
                raise ValueError("passed domain evidence requires qualified reconstruction")
        if self.status == PluginEvidenceStatus.NOT_APPLICABLE:
            if (
                any(details_present)
                or self.qualified_reconstruction != PluginEvidenceStatus.NOT_APPLICABLE
            ):
                raise ValueError("not-applicable domain evidence cannot imply domain authority")
        return self


class PluginEvidencePrivacyV1(StrictProtocolModel):
    protocol_boundary: PrivacyBoundaryV1
    plugin_source_included: Literal[False]
    raw_check_output_included: Literal[False]
    external_input_content_included: Literal[False]
    local_absolute_paths_included: Literal[False]


class PluginEvidenceBundleV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": PLUGIN_EVIDENCE_SCHEMA_VERSION},
    )

    schema_version: Literal["delivery-clearance.plugin-evidence.v1"]
    evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    requested_scope: Literal["personal_local"] = "personal_local"
    plugin: PluginPackageEvidenceV1
    capabilities: list[PluginCapability] = Field(min_length=1, max_length=12)
    runtime: PluginRuntimeEvidenceV1
    inputs: list[PluginInputEvidenceV1] = Field(max_length=100)
    effects: PluginEffectEvidenceV1
    checks: list[PluginCheckEvidenceV1] = Field(min_length=1, max_length=100)
    native_verification: PluginNativeVerificationV1
    domain_evidence: PluginDomainEvidenceV1
    observed_at: str = Field(min_length=1, max_length=64)
    valid_until: str = Field(min_length=1, max_length=64)
    privacy: PluginEvidencePrivacyV1

    @model_validator(mode="after")
    def validate_bundle(self) -> PluginEvidenceBundleV1:
        observed = parse_timestamp(self.observed_at)
        valid_until = parse_timestamp(self.valid_until)
        if valid_until <= observed:
            raise ValueError("plugin evidence bundle must expire after observation")
        if len(self.capabilities) != len(set(self.capabilities)):
            raise ValueError("plugin evidence contains duplicate capabilities")
        input_ids = [item.input_id for item in self.inputs]
        if len(input_ids) != len(set(input_ids)):
            raise ValueError("plugin evidence contains duplicate input ids")
        check_ids = [item.check_id for item in self.checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("plugin evidence contains duplicate check ids")
        return self


PLUGIN_DECISION_CHECKS = frozenset(
    {
        "bundle_not_expired",
        "package_digest_bound",
        "manifest_digest_bound",
        "runtime_ready",
        "runtime_dependencies_verified",
        "required_checks_passed",
        "inputs_bound",
        "external_inputs_fresh",
        "no_external_write_capability",
        "no_external_mutation",
        "no_credentials_used",
        "network_usage_declared",
        "project_mutation_bound",
        "native_verification_sufficient",
        "domain_evidence_sufficient",
    }
)


class PluginEvidenceDecisionV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": PLUGIN_EVIDENCE_DECISION_SCHEMA_VERSION},
    )

    schema_version: Literal["delivery-clearance.plugin-evidence-decision.v1"]
    decision_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    evidence_ref: str = Field(pattern=EVIDENCE_ID_PATTERN)
    evidence_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    plugin_id: str = Field(pattern=PLUGIN_ID_PATTERN)
    status: Literal["allow_personal_local", "needs_evidence", "block"]
    approved_scope: DeliveryScope
    checks: dict[str, bool]
    reasons: list[str]
    missing_evidence: list[str]
    evaluated_at: str = Field(min_length=1, max_length=64)
    valid_until: str = Field(min_length=1, max_length=64)
    manifest_or_install_state_sufficient: Literal[False]
    customer_delivery_authorized: Literal[False]
    production_authorized: Literal[False]
    external_action_authorized: Literal[False]
    claim_boundary: ClaimBoundaryV1
    privacy: PluginEvidencePrivacyV1

    @model_validator(mode="after")
    def validate_decision(self) -> PluginEvidenceDecisionV1:
        evaluated = parse_timestamp(self.evaluated_at)
        valid_until = parse_timestamp(self.valid_until)
        if valid_until <= evaluated and self.status == "allow_personal_local":
            raise ValueError("allowed plugin evidence must remain inside its validity window")
        if set(self.checks) != PLUGIN_DECISION_CHECKS:
            raise ValueError("plugin evidence decision has an incomplete check set")
        if self.status == "allow_personal_local":
            if self.approved_scope != DeliveryScope.PERSONAL_LOCAL:
                raise ValueError("plugin evidence can allow only personal_local")
            if not all(self.checks.values()) or self.reasons or self.missing_evidence:
                raise ValueError("allowed plugin evidence cannot retain blocking state")
        elif self.approved_scope != DeliveryScope.BLOCKED:
            raise ValueError("non-allow plugin evidence must remain blocked")
        if self.status == "needs_evidence" and not self.missing_evidence:
            raise ValueError("needs-evidence decision requires named missing evidence")
        if self.status == "block" and not self.reasons:
            raise ValueError("blocked plugin evidence requires a reason")
        if self.claim_boundary.maximum_scope != self.approved_scope:
            raise ValueError("plugin evidence claim boundary must equal approved scope")
        return self


PLUGIN_EVIDENCE_MODELS = {
    PLUGIN_EVIDENCE_SCHEMA_VERSION: PluginEvidenceBundleV1,
    PLUGIN_EVIDENCE_DECISION_SCHEMA_VERSION: PluginEvidenceDecisionV1,
}
