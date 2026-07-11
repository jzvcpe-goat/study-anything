"""Strict contracts for the personal-local Delivery Clearance MVP."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from study_anything.cbb.protocol.models import (
    ClaimBoundaryV1,
    DeliveryScope,
    PrivacyBoundaryV1,
    StrictProtocolModel,
    parse_timestamp,
)


PERSONAL_CONFIG_SCHEMA_VERSION: Literal["delivery-clearance.personal-config.v1"] = (
    "delivery-clearance.personal-config.v1"
)
PROJECT_SNAPSHOT_SCHEMA_VERSION: Literal["delivery-clearance.project-snapshot.v1"] = (
    "delivery-clearance.project-snapshot.v1"
)
CHECK_RUN_SCHEMA_VERSION: Literal["delivery-clearance.personal-check-run.v1"] = (
    "delivery-clearance.personal-check-run.v1"
)
BOUNDARY_RECONSTRUCTION_SCHEMA_VERSION: Literal[
    "delivery-clearance.personal-boundary-reconstruction.v1"
] = (
    "delivery-clearance.personal-boundary-reconstruction.v1"
)
PERSONAL_RECEIPT_SCHEMA_VERSION: Literal["delivery-clearance.personal-receipt.v1"] = (
    "delivery-clearance.personal-receipt.v1"
)

SHA256_PATTERN = r"^[0-9a-f]{64}$"
CHECK_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,79}$"


class PersonalHardBoundariesV1(StrictProtocolModel):
    production_mutation_allowed: Literal[False] = False
    external_delivery_allowed: Literal[False] = False
    irreversible_effects_allowed: Literal[False] = False


class PersonalCheckConfigV1(StrictProtocolModel):
    check_id: str = Field(pattern=CHECK_ID_PATTERN)
    argv: list[str] = Field(min_length=1, max_length=32)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    required: Literal[True] = True

    @model_validator(mode="after")
    def validate_argv(self) -> PersonalCheckConfigV1:
        if any(not item or len(item) > 500 for item in self.argv):
            raise ValueError("check argv entries must be non-empty and at most 500 characters")
        return self


class PersonalClearanceConfigV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": PERSONAL_CONFIG_SCHEMA_VERSION},
    )

    schema_version: Literal["delivery-clearance.personal-config.v1"]
    project_id: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=1000)
    non_goals: list[str] = Field(min_length=1, max_length=20)
    critical_failure_path: str = Field(min_length=1, max_length=2000)
    rollback_trigger: str = Field(min_length=1, max_length=1000)
    rollback_strategy: str = Field(min_length=1, max_length=2000)
    evidence_limitations: list[str] = Field(min_length=1, max_length=20)
    maximum_scope: Literal["personal_local"] = "personal_local"
    recipient_kind: Literal["self"] = "self"
    validity_hours: int = Field(default=24, ge=1, le=168)
    hard_boundaries: PersonalHardBoundariesV1
    checks: list[PersonalCheckConfigV1] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_unique_checks(self) -> PersonalClearanceConfigV1:
        check_ids = [item.check_id for item in self.checks]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError("personal clearance config contains duplicate check ids")
        return self


class PersonalProjectSnapshotV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": PROJECT_SNAPSHOT_SCHEMA_VERSION},
    )

    schema_version: Literal["delivery-clearance.project-snapshot.v1"]
    project_ref: str = Field(min_length=1, max_length=160)
    subject_ref: str = Field(min_length=1, max_length=160)
    subject_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    config_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    head_state: Literal["committed", "unborn"]
    head_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40,64}$")
    branch_ref_sha256: str = Field(pattern=SHA256_PATTERN)
    staged_diff_sha256: str = Field(pattern=SHA256_PATTERN)
    staged_diff_bytes: int = Field(ge=0)
    unstaged_diff_sha256: str = Field(pattern=SHA256_PATTERN)
    unstaged_diff_bytes: int = Field(ge=0)
    untracked_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    untracked_file_count: int = Field(ge=0)
    untracked_total_bytes: int = Field(ge=0)
    submodule_state_sha256: str = Field(pattern=SHA256_PATTERN)
    dirty: bool
    captured_at: str = Field(min_length=1, max_length=64)
    artifact_directory_excluded: Literal[".delivery-clearance/artifacts"]

    @model_validator(mode="after")
    def validate_snapshot(self) -> PersonalProjectSnapshotV1:
        parse_timestamp(self.captured_at)
        if self.head_state == "committed" and self.head_commit is None:
            raise ValueError("committed snapshot requires a head commit")
        if self.head_state == "unborn" and self.head_commit is not None:
            raise ValueError("unborn snapshot cannot include a head commit")
        return self


class PersonalCheckResultV1(StrictProtocolModel):
    check_id: str = Field(pattern=CHECK_ID_PATTERN)
    status: Literal["passed", "failed", "not_run", "error", "timeout"]
    required: Literal[True]
    argv_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    executable_name: str = Field(min_length=1, max_length=160)
    exit_code: int | None
    duration_ms: int = Field(ge=0)
    stdout_sha256: str = Field(pattern=SHA256_PATTERN)
    stdout_bytes: int = Field(ge=0)
    stderr_sha256: str = Field(pattern=SHA256_PATTERN)
    stderr_bytes: int = Field(ge=0)
    executed_at: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_execution_state(self) -> PersonalCheckResultV1:
        if self.executed_at is not None:
            parse_timestamp(self.executed_at)
        if self.status == "not_run":
            if self.executed_at is not None or self.exit_code is not None:
                raise ValueError("not-run check cannot include execution metadata")
        elif self.executed_at is None:
            raise ValueError("executed check requires executed_at")
        if self.status == "passed" and self.exit_code != 0:
            raise ValueError("passed check requires exit code zero")
        if self.status == "failed" and (self.exit_code is None or self.exit_code == 0):
            raise ValueError("failed check requires a non-zero exit code")
        return self


class PersonalCheckRunV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": CHECK_RUN_SCHEMA_VERSION},
    )

    schema_version: Literal["delivery-clearance.personal-check-run.v1"]
    project_ref: str = Field(min_length=1, max_length=160)
    checks_requested: bool
    all_required_checks_passed: bool
    project_state_mutated_during_checks: bool
    before_subject_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    after_subject_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    results: list[PersonalCheckResultV1] = Field(min_length=1)
    claim_boundary: ClaimBoundaryV1
    privacy: PrivacyBoundaryV1

    @model_validator(mode="after")
    def validate_check_run(self) -> PersonalCheckRunV1:
        passed = all(item.status == "passed" for item in self.results)
        if self.all_required_checks_passed != passed:
            raise ValueError("check-run aggregate does not match individual results")
        if not self.checks_requested and any(item.status != "not_run" for item in self.results):
            raise ValueError("non-requested checks must remain not_run")
        if self.project_state_mutated_during_checks != (
            self.before_subject_digest_sha256 != self.after_subject_digest_sha256
        ):
            raise ValueError("check-run mutation flag does not match project-state digests")
        return self


class PersonalBoundaryReconstructionV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": BOUNDARY_RECONSTRUCTION_SCHEMA_VERSION},
    )

    schema_version: Literal["delivery-clearance.personal-boundary-reconstruction.v1"]
    project_ref: str = Field(min_length=1, max_length=160)
    config_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    reviewer_kind: Literal["self"]
    risk_owner_kind: Literal["self"]
    responsibility_accepted_for_this_run: bool
    active_reconstruction_complete: bool
    unresolved_config_fields: list[str]
    purpose: str = Field(min_length=1, max_length=1000)
    non_goals: list[str] = Field(min_length=1, max_length=20)
    critical_failure_path: str = Field(min_length=1, max_length=2000)
    rollback_trigger: str = Field(min_length=1, max_length=1000)
    rollback_strategy: str = Field(min_length=1, max_length=2000)
    evidence_limitations: list[str] = Field(min_length=1, max_length=20)
    observed_at: str = Field(min_length=1, max_length=64)
    valid_until: str = Field(min_length=1, max_length=64)
    independent_review_performed: Literal[False]
    claim_boundary: ClaimBoundaryV1
    privacy: PrivacyBoundaryV1

    @model_validator(mode="after")
    def validate_reconstruction(self) -> PersonalBoundaryReconstructionV1:
        observed_at = parse_timestamp(self.observed_at)
        valid_until = parse_timestamp(self.valid_until)
        if valid_until <= observed_at:
            raise ValueError("personal reconstruction must expire after observation")
        expected_complete = (
            self.responsibility_accepted_for_this_run
            and not self.unresolved_config_fields
        )
        if self.active_reconstruction_complete != expected_complete:
            raise ValueError("active reconstruction state is inconsistent")
        return self


class PersonalClearanceReceiptV1(StrictProtocolModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        json_schema_extra={"$id": PERSONAL_RECEIPT_SCHEMA_VERSION},
    )

    schema_version: Literal["delivery-clearance.personal-receipt.v1"]
    receipt_id: str = Field(min_length=1, max_length=160)
    project_ref: str = Field(min_length=1, max_length=160)
    subject_ref: str = Field(min_length=1, max_length=160)
    subject_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    config_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    snapshot_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    check_run_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    boundary_reconstruction_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    policy_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    evidence_bundle_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    qualified_reconstruction_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    gate_decision_digest_sha256: str = Field(pattern=SHA256_PATTERN)
    gate_decision_ref: str = Field(min_length=1, max_length=160)
    status: Literal["allow", "block", "needs_evidence"]
    approved_scope: DeliveryScope
    reasons: list[str]
    missing_evidence_types: list[str]
    responsibility_accepted_for_this_run: bool
    independent_review_performed: Literal[False]
    configured_check_count: int = Field(ge=1)
    all_required_checks_passed: bool
    project_state_mutated_during_checks: bool
    issued_at: str = Field(min_length=1, max_length=64)
    expires_at: str = Field(min_length=1, max_length=64)
    claim_boundary: ClaimBoundaryV1
    privacy: PrivacyBoundaryV1

    @model_validator(mode="after")
    def validate_receipt(self) -> PersonalClearanceReceiptV1:
        issued_at = parse_timestamp(self.issued_at)
        expires_at = parse_timestamp(self.expires_at)
        if expires_at <= issued_at:
            raise ValueError("personal clearance receipt must expire after issue")
        if self.status == "allow":
            if self.approved_scope != DeliveryScope.PERSONAL_LOCAL:
                raise ValueError("personal clearance can only allow personal_local")
            if self.reasons or self.missing_evidence_types:
                raise ValueError("allowed personal clearance cannot include blocking state")
            if not self.responsibility_accepted_for_this_run:
                raise ValueError("allowed personal clearance requires responsibility acceptance")
            if not self.all_required_checks_passed:
                raise ValueError("allowed personal clearance requires passing checks")
            if self.project_state_mutated_during_checks:
                raise ValueError("allowed personal clearance cannot follow check mutation")
        elif self.approved_scope != DeliveryScope.BLOCKED:
            raise ValueError("non-allow personal clearance must remain blocked")
        if self.claim_boundary.maximum_scope != self.approved_scope:
            raise ValueError("personal receipt claim boundary must equal approved scope")
        return self


PERSONAL_CLEARANCE_MODELS = {
    PERSONAL_CONFIG_SCHEMA_VERSION: PersonalClearanceConfigV1,
    PROJECT_SNAPSHOT_SCHEMA_VERSION: PersonalProjectSnapshotV1,
    CHECK_RUN_SCHEMA_VERSION: PersonalCheckRunV1,
    BOUNDARY_RECONSTRUCTION_SCHEMA_VERSION: PersonalBoundaryReconstructionV1,
    PERSONAL_RECEIPT_SCHEMA_VERSION: PersonalClearanceReceiptV1,
}
