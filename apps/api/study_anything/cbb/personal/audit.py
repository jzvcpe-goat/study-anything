"""Local, deterministic Delivery Clearance for one operator's own Git project."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from html import escape
import json
import os
from pathlib import Path
import stat
import subprocess
import time
from typing import Any, Literal, Mapping

from pydantic import ValidationError

from study_anything.cbb.kernel.gate import evaluate_gate
from study_anything.cbb.personal.models import (
    BOUNDARY_RECONSTRUCTION_SCHEMA_VERSION,
    CHECK_RUN_SCHEMA_VERSION,
    PERSONAL_CONFIG_SCHEMA_VERSION,
    PERSONAL_RECEIPT_SCHEMA_VERSION,
    PROJECT_SNAPSHOT_SCHEMA_VERSION,
    PersonalBoundaryReconstructionV1,
    PersonalCheckConfigV1,
    PersonalCheckResultV1,
    PersonalCheckRunV1,
    PersonalClearanceConfigV1,
    PersonalClearanceReceiptV1,
    PersonalHardBoundariesV1,
    PersonalProjectSnapshotV1,
)
from study_anything.cbb.protocol.canonical import (
    assert_safe_metadata,
    canonical_sha256,
    pretty_json,
)
from study_anything.cbb.protocol.models import (
    EVIDENCE_BUNDLE_SCHEMA_VERSION,
    QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION,
    TRUST_POLICY_SCHEMA_VERSION,
    ClaimBoundaryV1,
    DeliveryScenarioClass,
    DeliveryScenarioV1,
    DeliveryScope,
    EvidenceBundleV1,
    EvidenceItemV1,
    EvidenceRequirementV1,
    GateDecisionV1,
    HumanCapabilityProfileV1,
    MinimumReconstructableUnitV1,
    ModelCapabilityProfileV1,
    MruResultV1,
    PrivacyBoundaryV1,
    QualifiedReconstructionV1,
    RecipientContractV1,
    ReconstructionBoundaryType,
    RiskBudgetV1,
    RiskOwnerContractV1,
    SafeguardRequirementV1,
    TrustPolicyV1,
    parse_timestamp,
)


CONFIG_RELATIVE_PATH = Path(".delivery-clearance/personal-clearance.json")
ARTIFACT_RELATIVE_DIR = Path(".delivery-clearance/artifacts")
ARTIFACT_EXCLUDE_PATHSPEC = ":(exclude).delivery-clearance/artifacts/**"
ARTIFACT_FILENAMES = {
    "snapshot": "project-snapshot.json",
    "check_run": "check-results.json",
    "boundary": "human-reconstruction.json",
    "policy": "trust-policy.json",
    "evidence": "evidence-bundle.json",
    "reconstruction": "qualified-reconstruction.json",
    "decision": "gate-decision.json",
    "receipt": "personal-clearance-receipt.json",
    "html": "personal-clearance-report.html",
}

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
PERSONAL_NOT_CLAIMED = [
    "AI correctness",
    "external delivery authority",
    "production approval",
    "independent review",
    "legal, security, or compliance certification",
    "OS-level sandboxing or network isolation of configured checks",
]


class PersonalClearanceError(RuntimeError):
    """Raised when a personal clearance cannot be built or verified."""


@dataclass(frozen=True)
class PersonalAuditArtifacts:
    snapshot: PersonalProjectSnapshotV1
    check_run: PersonalCheckRunV1
    boundary: PersonalBoundaryReconstructionV1
    policy: TrustPolicyV1
    evidence: EvidenceBundleV1
    reconstruction: QualifiedReconstructionV1
    decision: GateDecisionV1
    receipt: PersonalClearanceReceiptV1


def _timestamp(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise PersonalClearanceError("evaluated time must include a UTC offset")
    return current.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def _claim(scope: DeliveryScope, current_claim: str) -> ClaimBoundaryV1:
    return ClaimBoundaryV1(
        current_claim=current_claim,
        maximum_scope=scope,
        not_claimed=list(PERSONAL_NOT_CLAIMED),
    )


def _run_git(
    root: Path,
    args: list[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        raise PersonalClearanceError(f"git command failed: {args[0]}")
    return completed


def resolve_repository_root(project: str | Path) -> Path:
    requested = Path(project).expanduser()
    if not requested.exists():
        raise PersonalClearanceError("project path does not exist")
    completed = subprocess.run(
        ["git", "-C", str(requested), "rev-parse", "--show-toplevel"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise PersonalClearanceError("personal clearance requires a local Git repository")
    return Path(completed.stdout.strip()).resolve()


def default_config(project_id: str) -> PersonalClearanceConfigV1:
    return PersonalClearanceConfigV1(
        schema_version=PERSONAL_CONFIG_SCHEMA_VERSION,
        project_id=project_id,
        purpose="TODO: describe the exact local change or candidate being cleared",
        non_goals=["TODO: state at least one thing this clearance does not authorize"],
        critical_failure_path="TODO: describe the most important way this change could fail",
        rollback_trigger="TODO: state the observable condition that triggers rollback",
        rollback_strategy="TODO: describe how to return this local project to a safe state",
        evidence_limitations=[
            "Configured checks run with the current user's permissions and are not independently sandboxed."
        ],
        maximum_scope="personal_local",
        recipient_kind="self",
        validity_hours=24,
        hard_boundaries=PersonalHardBoundariesV1(),
        checks=[
            PersonalCheckConfigV1(
                check_id="git-diff-check",
                argv=["git", "diff", "--check"],
                timeout_seconds=60,
                required=True,
            )
        ],
    )


def initialize_project(project: str | Path, *, force: bool = False) -> Path:
    root = resolve_repository_root(project)
    config_path = root / CONFIG_RELATIVE_PATH
    if config_path.exists() and not force:
        raise PersonalClearanceError(
            "personal clearance config already exists; use --force to replace it"
        )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = default_config(root.name)
    config_path.write_text(pretty_json(config), encoding="utf-8")
    ignore_path = config_path.parent / ".gitignore"
    if not ignore_path.exists():
        ignore_path.write_text("/artifacts/\n", encoding="utf-8")
    return config_path


def load_config(root: Path) -> PersonalClearanceConfigV1:
    config_path = root / CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        raise PersonalClearanceError(
            "personal clearance config is missing; run personal_clearance.py init first"
        )
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        assert_safe_metadata(payload, label="personal clearance config")
        return PersonalClearanceConfigV1.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise PersonalClearanceError(f"invalid personal clearance config: {exc}") from exc


def _untracked_manifest(root: Path) -> tuple[str, int, int]:
    completed = _run_git(
        root,
        [
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            ".",
            ARTIFACT_EXCLUDE_PATHSPEC,
        ],
    )
    raw_paths = sorted(item for item in completed.stdout.split(b"\0") if item)
    aggregate = hashlib.sha256()
    total_bytes = 0
    for raw_path in raw_paths:
        relative = Path(os.fsdecode(raw_path))
        if relative.is_absolute() or ".." in relative.parts:
            raise PersonalClearanceError("git returned an unsafe untracked path")
        candidate = root / relative
        metadata = candidate.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            content = os.fsencode(os.readlink(candidate))
        elif stat.S_ISREG(metadata.st_mode):
            content_hash = hashlib.sha256()
            with candidate.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    content_hash.update(chunk)
            content = bytes.fromhex(content_hash.hexdigest())
        else:
            content = f"special:{stat.S_IFMT(metadata.st_mode)}".encode("ascii")
        total_bytes += metadata.st_size
        aggregate.update(len(raw_path).to_bytes(8, "big"))
        aggregate.update(raw_path)
        aggregate.update(metadata.st_mode.to_bytes(8, "big"))
        aggregate.update(metadata.st_size.to_bytes(8, "big", signed=False))
        aggregate.update(content)
    return aggregate.hexdigest(), len(raw_paths), total_bytes


def capture_project_snapshot(
    root: Path,
    config: PersonalClearanceConfigV1,
    *,
    captured_at: str,
) -> PersonalProjectSnapshotV1:
    head = _run_git(root, ["rev-parse", "--verify", "HEAD"], check=False)
    if head.returncode == 0:
        head_state: Literal["committed", "unborn"] = "committed"
        head_commit = head.stdout.decode("ascii").strip()
    else:
        head_state = "unborn"
        head_commit = None

    branch = _run_git(root, ["symbolic-ref", "--quiet", "--short", "HEAD"], check=False)
    branch_name = branch.stdout.strip() if branch.returncode == 0 else b"detached"
    staged = _run_git(
        root,
        ["diff", "--cached", "--binary", "--no-ext-diff", "--", ".", ARTIFACT_EXCLUDE_PATHSPEC],
    ).stdout
    unstaged = _run_git(
        root,
        ["diff", "--binary", "--no-ext-diff", "--", ".", ARTIFACT_EXCLUDE_PATHSPEC],
    ).stdout
    untracked_digest, untracked_count, untracked_bytes = _untracked_manifest(root)
    submodules = _run_git(root, ["submodule", "status", "--recursive"], check=False)
    submodule_state = submodules.stdout if submodules.returncode == 0 else b"unavailable"
    config_digest = canonical_sha256(config)
    project_digest = _sha256(config.project_id.encode("utf-8"))
    project_ref = f"project:sha256:{project_digest}"
    branch_ref_sha256 = _sha256(branch_name)
    staged_diff_sha256 = _sha256(staged)
    unstaged_diff_sha256 = _sha256(unstaged)
    submodule_state_sha256 = _sha256(submodule_state)
    state = {
        "project_ref": project_ref,
        "config_digest_sha256": config_digest,
        "head_state": head_state,
        "head_commit": head_commit,
        "branch_ref_sha256": branch_ref_sha256,
        "staged_diff_sha256": staged_diff_sha256,
        "staged_diff_bytes": len(staged),
        "unstaged_diff_sha256": unstaged_diff_sha256,
        "unstaged_diff_bytes": len(unstaged),
        "untracked_manifest_sha256": untracked_digest,
        "untracked_file_count": untracked_count,
        "untracked_total_bytes": untracked_bytes,
        "submodule_state_sha256": submodule_state_sha256,
    }
    subject_digest = canonical_sha256(state)
    return PersonalProjectSnapshotV1(
        schema_version=PROJECT_SNAPSHOT_SCHEMA_VERSION,
        project_ref=project_ref,
        subject_ref=f"local-state:{subject_digest}",
        subject_digest_sha256=subject_digest,
        config_digest_sha256=config_digest,
        head_state=head_state,
        head_commit=head_commit,
        branch_ref_sha256=branch_ref_sha256,
        staged_diff_sha256=staged_diff_sha256,
        staged_diff_bytes=len(staged),
        unstaged_diff_sha256=unstaged_diff_sha256,
        unstaged_diff_bytes=len(unstaged),
        untracked_manifest_sha256=untracked_digest,
        untracked_file_count=untracked_count,
        untracked_total_bytes=untracked_bytes,
        submodule_state_sha256=submodule_state_sha256,
        dirty=bool(staged or unstaged or untracked_count),
        captured_at=captured_at,
        artifact_directory_excluded=".delivery-clearance/artifacts",
    )


def _result_bytes(value: bytes | str | None) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8", errors="replace")


def _not_run_result(check: PersonalCheckConfigV1) -> PersonalCheckResultV1:
    executable = check.argv[0].replace("\\", "/").rsplit("/", 1)[-1]
    return PersonalCheckResultV1(
        check_id=check.check_id,
        status="not_run",
        required=True,
        argv_digest_sha256=canonical_sha256({"argv": check.argv}),
        executable_name=executable,
        exit_code=None,
        duration_ms=0,
        stdout_sha256=EMPTY_SHA256,
        stdout_bytes=0,
        stderr_sha256=EMPTY_SHA256,
        stderr_bytes=0,
        executed_at=None,
    )


def _execute_check(
    root: Path,
    check: PersonalCheckConfigV1,
    *,
    executed_at: str,
) -> PersonalCheckResultV1:
    started = time.monotonic()
    stdout = b""
    stderr = b""
    exit_code: int | None = None
    status_value: Literal["passed", "failed", "error", "timeout"] = "error"
    try:
        completed = subprocess.run(
            list(check.argv),
            cwd=root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=check.timeout_seconds,
            shell=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        exit_code = completed.returncode
        status_value = "passed" if completed.returncode == 0 else "failed"
    except subprocess.TimeoutExpired as exc:
        stdout = _result_bytes(exc.stdout)
        stderr = _result_bytes(exc.stderr)
        status_value = "timeout"
    except OSError as exc:
        stderr = type(exc).__name__.encode("ascii", errors="replace")
        status_value = "error"
    duration_ms = max(0, int((time.monotonic() - started) * 1000))
    executable = check.argv[0].replace("\\", "/").rsplit("/", 1)[-1]
    return PersonalCheckResultV1(
        check_id=check.check_id,
        status=status_value,
        required=True,
        argv_digest_sha256=canonical_sha256({"argv": check.argv}),
        executable_name=executable,
        exit_code=exit_code,
        duration_ms=duration_ms,
        stdout_sha256=_sha256(stdout),
        stdout_bytes=len(stdout),
        stderr_sha256=_sha256(stderr),
        stderr_bytes=len(stderr),
        executed_at=executed_at,
    )


def _unresolved_config_fields(config: PersonalClearanceConfigV1) -> list[str]:
    unresolved: list[str] = []

    def pending(value: str) -> bool:
        return value.lstrip().upper().startswith("TODO:")

    if pending(config.purpose):
        unresolved.append("purpose")
    unresolved.extend(
        f"non_goals[{index}]"
        for index, value in enumerate(config.non_goals)
        if pending(value)
    )
    if pending(config.critical_failure_path):
        unresolved.append("critical_failure_path")
    if pending(config.rollback_trigger):
        unresolved.append("rollback_trigger")
    if pending(config.rollback_strategy):
        unresolved.append("rollback_strategy")
    unresolved.extend(
        f"evidence_limitations[{index}]"
        for index, value in enumerate(config.evidence_limitations)
        if pending(value)
    )
    return sorted(unresolved)


def _boundary_artifact(
    config: PersonalClearanceConfigV1,
    snapshot: PersonalProjectSnapshotV1,
    *,
    responsibility_accepted: bool,
    observed_at: str,
    valid_until: str,
) -> PersonalBoundaryReconstructionV1:
    unresolved = _unresolved_config_fields(config)
    complete = responsibility_accepted and not unresolved
    scope = DeliveryScope.PERSONAL_LOCAL if complete else DeliveryScope.BLOCKED
    return PersonalBoundaryReconstructionV1(
        schema_version=BOUNDARY_RECONSTRUCTION_SCHEMA_VERSION,
        project_ref=snapshot.project_ref,
        config_digest_sha256=snapshot.config_digest_sha256,
        reviewer_kind="self",
        risk_owner_kind="self",
        responsibility_accepted_for_this_run=responsibility_accepted,
        active_reconstruction_complete=complete,
        unresolved_config_fields=unresolved,
        purpose=config.purpose,
        non_goals=config.non_goals,
        critical_failure_path=config.critical_failure_path,
        rollback_trigger=config.rollback_trigger,
        rollback_strategy=config.rollback_strategy,
        evidence_limitations=config.evidence_limitations,
        observed_at=observed_at,
        valid_until=valid_until,
        independent_review_performed=False,
        claim_boundary=_claim(
            scope,
            "The operator reconstructed these boundaries only for this personal local project state.",
        ),
        privacy=_privacy(),
    )


def _protocol_artifacts(
    config: PersonalClearanceConfigV1,
    snapshot: PersonalProjectSnapshotV1,
    check_run: PersonalCheckRunV1,
    boundary: PersonalBoundaryReconstructionV1,
    *,
    evaluated_at: str,
    valid_until: str,
) -> tuple[TrustPolicyV1, EvidenceBundleV1, QualifiedReconstructionV1, GateDecisionV1]:
    project_suffix = snapshot.project_ref.rsplit(":", 1)[-1][:32]
    state_suffix = snapshot.subject_digest_sha256[:32]
    scenario_ref = f"scenario:personal-local:{project_suffix}"
    reviewer_ref = f"reviewer:self:{project_suffix}"
    model_ref = "model:local-ai-assisted-development"
    scenario = DeliveryScenarioV1(
        scenario_ref=scenario_ref,
        scenario_class=DeliveryScenarioClass.PERSONAL_LOCAL_PROTOTYPE,
        project_ref=snapshot.project_ref,
        model_ref=model_ref,
        maximum_scope=DeliveryScope.PERSONAL_LOCAL,
        recipient=RecipientContractV1(
            recipient_ref=reviewer_ref,
            recipient_kind="self",
            external=False,
            automatic_execution_authority=False,
        ),
        risk_owner=RiskOwnerContractV1(
            required=True,
            risk_owner_ref=reviewer_ref,
            accepted_scope_ceiling=DeliveryScope.PERSONAL_LOCAL,
            acceptance_evidence_type="risk_owner_acceptance",
        ),
        affected_parties=[],
        disclosure=SafeguardRequirementV1(
            required=False,
            evidence_type=None,
            mechanism_ref=None,
            human_fallback_required=False,
        ),
        appeal=SafeguardRequirementV1(
            required=False,
            evidence_type=None,
            mechanism_ref=None,
            human_fallback_required=False,
        ),
        redress=SafeguardRequirementV1(
            required=False,
            evidence_type=None,
            mechanism_ref=None,
            human_fallback_required=False,
        ),
        impact_classes=["personal_local_development_process"],
        regulated_or_irreversible=False,
    )
    boundaries = (
        ReconstructionBoundaryType.INTENT_AND_NON_GOALS,
        ReconstructionBoundaryType.CRITICAL_FAILURE_PATH,
        ReconstructionBoundaryType.ROLLBACK_TRIGGER,
        ReconstructionBoundaryType.EVIDENCE_WEAKNESS_AND_LIMITATIONS,
    )
    required_mrus = [
        MinimumReconstructableUnitV1(
            mru_ref=f"mru:personal-local:{boundary_type.value}",
            boundary_type=boundary_type,
            required_for_scope=DeliveryScope.PERSONAL_LOCAL,
            evidence_kind="active_reconstruction",
            blocks_promotion=True,
        )
        for boundary_type in boundaries
    ]
    policy = TrustPolicyV1(
        schema_version=TRUST_POLICY_SCHEMA_VERSION,
        policy_id=f"delivery-clearance:personal-policy:{state_suffix}",
        subject_ref=snapshot.subject_ref,
        scenario_ref=scenario_ref,
        scenario=scenario,
        model_capability_profile=ModelCapabilityProfileV1(
            profile_id=f"model-capability:personal-local:{state_suffix}",
            model_ref=model_ref,
            scenario_refs=[scenario_ref],
            task_types=["local_project_development"],
            status="observed",
            maximum_autonomy_scope=DeliveryScope.PERSONAL_LOCAL,
            evidence_refs=[f"project-state:sha256:{snapshot.subject_digest_sha256}"],
            counter_evidence_refs=[],
            known_failure_modes=[
                "configured_checks_may_not_cover_all_failures",
                "self_review_is_not_independent_review",
                "AI_self_review_is_not_final_authority",
            ],
            observed_at=evaluated_at,
            valid_until=valid_until,
            vendor_claims_sufficient=False,
        ),
        maximum_scope=DeliveryScope.PERSONAL_LOCAL,
        hard_denies=[
            "ai_review_only_trust",
            "irreversible_external_effect",
            "production_mutation",
            "external_delivery",
            "audit_check_mutated_project",
        ],
        risk_budget=RiskBudgetV1(
            level="low",
            production_mutation_allowed=False,
            real_user_exposure_allowed=False,
            irreversible_external_effects_allowed=False,
        ),
        required_evidence=[
            EvidenceRequirementV1(
                evidence_type="project_state_snapshot",
                required_for_scope=DeliveryScope.PERSONAL_LOCAL,
                blocking=True,
            ),
            EvidenceRequirementV1(
                evidence_type="configured_checks",
                required_for_scope=DeliveryScope.PERSONAL_LOCAL,
                blocking=True,
            ),
            EvidenceRequirementV1(
                evidence_type="rollback_plan",
                required_for_scope=DeliveryScope.PERSONAL_LOCAL,
                blocking=True,
            ),
            EvidenceRequirementV1(
                evidence_type="risk_owner_acceptance",
                required_for_scope=DeliveryScope.PERSONAL_LOCAL,
                blocking=True,
            ),
            EvidenceRequirementV1(
                evidence_type="qualified_reconstruction",
                required_for_scope=DeliveryScope.PERSONAL_LOCAL,
                blocking=True,
            ),
        ],
        required_roles=["qualified_reviewer", "risk_owner"],
        required_mrus=required_mrus,
        claim_boundary=_claim(
            DeliveryScope.PERSONAL_LOCAL,
            "This policy can authorize only the operator's personal local use of this exact project state.",
        ),
        privacy=_privacy(),
        created_at=evaluated_at,
    )

    if check_run.all_required_checks_passed:
        check_status: Literal["passed", "failed", "missing"] = "passed"
        check_scope = DeliveryScope.PERSONAL_LOCAL
    elif not check_run.checks_requested:
        check_status = "missing"
        check_scope = DeliveryScope.BLOCKED
    else:
        check_status = "failed"
        check_scope = DeliveryScope.BLOCKED
    rollback_unresolved = any(
        field.startswith("rollback_") for field in boundary.unresolved_config_fields
    )
    rollback_status: Literal["passed", "missing"] = (
        "missing" if rollback_unresolved else "passed"
    )
    rollback_scope = (
        DeliveryScope.BLOCKED if rollback_unresolved else DeliveryScope.PERSONAL_LOCAL
    )
    acceptance_status: Literal["passed", "missing"] = (
        "passed" if boundary.responsibility_accepted_for_this_run else "missing"
    )
    acceptance_scope = (
        DeliveryScope.PERSONAL_LOCAL
        if boundary.responsibility_accepted_for_this_run
        else DeliveryScope.BLOCKED
    )
    check_run_digest = canonical_sha256(check_run)
    boundary_digest = canonical_sha256(boundary)
    evidence_items = [
        EvidenceItemV1(
            evidence_id=f"evidence:project-state:{state_suffix}",
            evidence_type="project_state_snapshot",
            status="passed",
            source_schema_version=PROJECT_SNAPSHOT_SCHEMA_VERSION,
            source_ref=ARTIFACT_FILENAMES["snapshot"],
            supported_scope=DeliveryScope.PERSONAL_LOCAL,
            metadata={
                "subject_digest_sha256": snapshot.subject_digest_sha256,
                "dirty": snapshot.dirty,
            },
        ),
        EvidenceItemV1(
            evidence_id=f"evidence:configured-checks:{check_run_digest[:32]}",
            evidence_type="configured_checks",
            status=check_status,
            source_schema_version=CHECK_RUN_SCHEMA_VERSION,
            source_ref=ARTIFACT_FILENAMES["check_run"],
            supported_scope=check_scope,
            metadata={
                "check_run_digest_sha256": check_run_digest,
                "check_count": len(check_run.results),
                "all_required_checks_passed": check_run.all_required_checks_passed,
            },
        ),
        EvidenceItemV1(
            evidence_id=f"evidence:rollback:{boundary_digest[:32]}",
            evidence_type="rollback_plan",
            status=rollback_status,
            source_schema_version=BOUNDARY_RECONSTRUCTION_SCHEMA_VERSION,
            source_ref=ARTIFACT_FILENAMES["boundary"],
            supported_scope=rollback_scope,
            metadata={"boundary_reconstruction_digest_sha256": boundary_digest},
        ),
        EvidenceItemV1(
            evidence_id=f"evidence:risk-owner:{boundary_digest[:32]}",
            evidence_type="risk_owner_acceptance",
            status=acceptance_status,
            source_schema_version=BOUNDARY_RECONSTRUCTION_SCHEMA_VERSION,
            source_ref=ARTIFACT_FILENAMES["boundary"],
            supported_scope=acceptance_scope,
            metadata={
                "reviewer_kind": "self",
                "independent_review_performed": False,
            },
        ),
    ]
    if check_run.project_state_mutated_during_checks:
        evidence_items.append(
            EvidenceItemV1(
                evidence_id=f"evidence:check-mutation:{state_suffix}",
                evidence_type="hard_deny:audit_check_mutated_project",
                status="passed",
                source_schema_version=CHECK_RUN_SCHEMA_VERSION,
                source_ref=ARTIFACT_FILENAMES["check_run"],
                supported_scope=DeliveryScope.BLOCKED,
                metadata={"observed": True},
            )
        )
    evidence = EvidenceBundleV1(
        schema_version=EVIDENCE_BUNDLE_SCHEMA_VERSION,
        bundle_id=f"delivery-clearance:personal-evidence:{state_suffix}",
        subject_ref=snapshot.subject_ref,
        policy_ref=policy.policy_id,
        evidence=evidence_items,
        maximum_supported_scope=DeliveryScope.PERSONAL_LOCAL,
        claim_boundary=_claim(
            DeliveryScope.PERSONAL_LOCAL,
            "Evidence supports at most this exact personal local project state.",
        ),
        privacy=_privacy(),
        created_at=evaluated_at,
    )

    complete = boundary.active_reconstruction_complete
    mru_results = [
        MruResultV1(
            mru_ref=requirement.mru_ref,
            boundary_type=requirement.boundary_type,
            status="passed" if complete else "missing",
            evidence_refs=(
                [f"boundary-reconstruction:sha256:{boundary_digest}"] if complete else []
            ),
        )
        for requirement in required_mrus
    ]
    qualified_scope = DeliveryScope.PERSONAL_LOCAL if complete else DeliveryScope.BLOCKED
    reconstruction = QualifiedReconstructionV1(
        schema_version=QUALIFIED_RECONSTRUCTION_SCHEMA_VERSION,
        reconstruction_id=f"delivery-clearance:personal-reconstruction:{state_suffix}",
        policy_ref=policy.policy_id,
        reviewer_ref=reviewer_ref,
        scenario_ref=scenario_ref,
        project_ref=snapshot.project_ref,
        reviewer_roles=["qualified_reviewer", "risk_owner"],
        status="passed" if complete else "missing",
        qualified_scope=qualified_scope,
        active_reconstruction=complete,
        passive_attention_only=False,
        required_mrus_total=len(mru_results),
        required_mrus_passed=len(mru_results) if complete else 0,
        missing_mru_refs=[] if complete else [item.mru_ref for item in mru_results],
        mru_results=mru_results,
        human_capability_profile=HumanCapabilityProfileV1(
            profile_id=f"human-capability:personal-local:{state_suffix}",
            human_ref=reviewer_ref,
            project_ref=snapshot.project_ref,
            scenario_refs=[scenario_ref],
            qualified_roles=["qualified_reviewer", "risk_owner"],
            boundary_types=list(boundaries),
            status="active" if complete else "insufficient",
            maximum_scope=qualified_scope,
            evidence_refs=(
                [f"boundary-reconstruction:sha256:{boundary_digest}"] if complete else []
            ),
            counter_evidence_refs=[],
            observed_at=evaluated_at,
            valid_until=valid_until,
            permanent_global_label=False,
        ),
        evidence_refs=(
            [f"boundary-reconstruction:sha256:{boundary_digest}"] if complete else []
        ),
        observed_at=evaluated_at,
        valid_until=valid_until,
        claim_boundary=_claim(
            qualified_scope,
            "Self-qualification is limited to this project state, purpose, and validity window.",
        ),
        privacy=_privacy(),
    )
    decision = evaluate_gate(
        policy,
        evidence,
        reconstruction,
        decided_at=evaluated_at,
    )
    return policy, evidence, reconstruction, decision


def _receipt(
    snapshot: PersonalProjectSnapshotV1,
    check_run: PersonalCheckRunV1,
    boundary: PersonalBoundaryReconstructionV1,
    policy: TrustPolicyV1,
    evidence: EvidenceBundleV1,
    reconstruction: QualifiedReconstructionV1,
    decision: GateDecisionV1,
    *,
    issued_at: str,
    expires_at: str,
) -> PersonalClearanceReceiptV1:
    digests = {
        "snapshot_digest_sha256": canonical_sha256(snapshot),
        "check_run_digest_sha256": canonical_sha256(check_run),
        "boundary_reconstruction_digest_sha256": canonical_sha256(boundary),
        "policy_digest_sha256": canonical_sha256(policy),
        "evidence_bundle_digest_sha256": canonical_sha256(evidence),
        "qualified_reconstruction_digest_sha256": canonical_sha256(reconstruction),
        "gate_decision_digest_sha256": canonical_sha256(decision),
    }
    receipt_material = {
        "subject_digest_sha256": snapshot.subject_digest_sha256,
        "config_digest_sha256": snapshot.config_digest_sha256,
        **digests,
        "gate_decision_ref": decision.decision_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    scope = decision.approved_scope
    claim = (
        "This exact project state is cleared only for the operator's personal local use."
        if decision.status == "allow"
        else "This project state is not cleared for delivery or use."
    )
    return PersonalClearanceReceiptV1(
        schema_version=PERSONAL_RECEIPT_SCHEMA_VERSION,
        receipt_id=f"delivery-clearance:personal:{canonical_sha256(receipt_material)[:32]}",
        project_ref=snapshot.project_ref,
        subject_ref=snapshot.subject_ref,
        subject_digest_sha256=snapshot.subject_digest_sha256,
        config_digest_sha256=snapshot.config_digest_sha256,
        gate_decision_ref=decision.decision_id,
        status=decision.status,
        approved_scope=scope,
        reasons=decision.reasons,
        missing_evidence_types=decision.missing_evidence_types,
        responsibility_accepted_for_this_run=boundary.responsibility_accepted_for_this_run,
        independent_review_performed=False,
        configured_check_count=len(check_run.results),
        all_required_checks_passed=check_run.all_required_checks_passed,
        project_state_mutated_during_checks=check_run.project_state_mutated_during_checks,
        issued_at=issued_at,
        expires_at=expires_at,
        claim_boundary=_claim(scope, claim),
        privacy=_privacy(),
        **digests,
    )


def audit_project(
    project: str | Path,
    *,
    execute_checks: bool,
    accept_responsibility: bool,
    evaluated_at: str | None = None,
) -> tuple[Path, PersonalAuditArtifacts]:
    root = resolve_repository_root(project)
    config = load_config(root)
    issued_at = evaluated_at or _timestamp()
    issued_dt = parse_timestamp(issued_at)
    expires_at = _timestamp(issued_dt + timedelta(hours=config.validity_hours))
    before = capture_project_snapshot(root, config, captured_at=issued_at)
    results = [
        _execute_check(root, check, executed_at=issued_at)
        if execute_checks
        else _not_run_result(check)
        for check in config.checks
    ]
    after = capture_project_snapshot(root, config, captured_at=issued_at)
    check_run = PersonalCheckRunV1(
        schema_version=CHECK_RUN_SCHEMA_VERSION,
        project_ref=after.project_ref,
        checks_requested=execute_checks,
        all_required_checks_passed=all(item.status == "passed" for item in results),
        project_state_mutated_during_checks=(
            before.subject_digest_sha256 != after.subject_digest_sha256
        ),
        before_subject_digest_sha256=before.subject_digest_sha256,
        after_subject_digest_sha256=after.subject_digest_sha256,
        results=results,
        claim_boundary=_claim(
            DeliveryScope.PERSONAL_LOCAL,
            "Check receipts contain hashes, counts, and exit states, never raw command output.",
        ),
        privacy=_privacy(),
    )
    boundary = _boundary_artifact(
        config,
        after,
        responsibility_accepted=accept_responsibility,
        observed_at=issued_at,
        valid_until=expires_at,
    )
    policy, evidence, reconstruction, decision = _protocol_artifacts(
        config,
        after,
        check_run,
        boundary,
        evaluated_at=issued_at,
        valid_until=expires_at,
    )
    receipt = _receipt(
        after,
        check_run,
        boundary,
        policy,
        evidence,
        reconstruction,
        decision,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    return root, PersonalAuditArtifacts(
        snapshot=after,
        check_run=check_run,
        boundary=boundary,
        policy=policy,
        evidence=evidence,
        reconstruction=reconstruction,
        decision=decision,
        receipt=receipt,
    )


def _artifact_mapping(artifacts: PersonalAuditArtifacts) -> Mapping[str, Any]:
    return {
        ARTIFACT_FILENAMES["snapshot"]: artifacts.snapshot,
        ARTIFACT_FILENAMES["check_run"]: artifacts.check_run,
        ARTIFACT_FILENAMES["boundary"]: artifacts.boundary,
        ARTIFACT_FILENAMES["policy"]: artifacts.policy,
        ARTIFACT_FILENAMES["evidence"]: artifacts.evidence,
        ARTIFACT_FILENAMES["reconstruction"]: artifacts.reconstruction,
        ARTIFACT_FILENAMES["decision"]: artifacts.decision,
        ARTIFACT_FILENAMES["receipt"]: artifacts.receipt,
    }


def render_report(artifacts: PersonalAuditArtifacts) -> str:
    receipt = artifacts.receipt
    boundary = artifacts.boundary
    status_label = {
        "allow": "CLEARED FOR PERSONAL LOCAL USE",
        "block": "BLOCKED",
        "needs_evidence": "NEEDS EVIDENCE",
    }[receipt.status]
    check_rows = "".join(
        "<tr>"
        f"<td>{escape(item.check_id)}</td>"
        f"<td>{escape(item.status)}</td>"
        f"<td>{item.exit_code if item.exit_code is not None else '-'}</td>"
        f"<td>{item.duration_ms} ms</td>"
        "</tr>"
        for item in artifacts.check_run.results
    )
    missing = ", ".join(receipt.missing_evidence_types) or "None"
    reasons = ", ".join(receipt.reasons) or "None"
    non_goals = "".join(f"<li>{escape(item)}</li>" for item in boundary.non_goals)
    limitations = "".join(
        f"<li>{escape(item)}</li>" for item in boundary.evidence_limitations
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Delivery Clearance - Personal Local Receipt</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; color: #17211b; background: #f5f7f4; }}
    * {{ box-sizing: border-box; }}
    html, body {{ max-width: 100%; overflow-x: hidden; }}
    body {{ margin: 0; }}
    header {{ background: #17211b; color: #ffffff; padding: 28px 24px; }}
    header p {{ max-width: 900px; margin: 8px 0 0; color: #d7dfd9; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 24px; }}
    section {{ padding: 20px 0; border-bottom: 1px solid #cbd4cd; }}
    h1, h2 {{ letter-spacing: 0; }}
    h1 {{ margin: 0; font-size: 30px; }}
    h2 {{ font-size: 19px; margin: 0 0 12px; }}
    .status {{ display: inline-block; max-width: 100%; margin-top: 18px; padding: 8px 10px; border: 1px solid #8ca393; border-radius: 4px; background: #eef4ef; color: #173b25; font-weight: 700; overflow-wrap: anywhere; }}
    .scope {{ font-family: ui-monospace, monospace; }}
    dl {{ display: grid; grid-template-columns: minmax(160px, 220px) 1fr; gap: 8px 16px; }}
    dt {{ font-weight: 700; }}
    dd {{ min-width: 0; margin: 0; overflow-wrap: anywhere; }}
    table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
    th, td {{ padding: 9px; text-align: left; border-bottom: 1px solid #d6ddd8; overflow-wrap: anywhere; }}
    th {{ background: #e9eeea; }}
    code {{ overflow-wrap: anywhere; }}
    .warning {{ color: #7a2e20; }}
    @media (max-width: 640px) {{
      header, main {{ padding-left: 16px; padding-right: 16px; }}
      dl {{ grid-template-columns: minmax(0, 1fr); gap: 4px 0; }}
      dd + dt {{ margin-top: 6px; }}
      th, td {{ padding: 7px 5px; font-size: 12px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Delivery Clearance</h1>
    <p>AI Delivery Clearance Protocol / AI 交付放行协议</p>
    <div class="status">{escape(status_label)}</div>
  </header>
  <main>
    <section>
      <h2>Clearance decision</h2>
      <dl>
        <dt>Approved scope</dt><dd class="scope">{escape(receipt.approved_scope.value)}</dd>
        <dt>Responsibility accepted</dt><dd>{str(receipt.responsibility_accepted_for_this_run).lower()}</dd>
        <dt>Independent review</dt><dd>false</dd>
        <dt>Issued</dt><dd>{escape(receipt.issued_at)}</dd>
        <dt>Expires</dt><dd>{escape(receipt.expires_at)}</dd>
        <dt>Reasons</dt><dd>{escape(reasons)}</dd>
        <dt>Missing evidence</dt><dd>{escape(missing)}</dd>
      </dl>
    </section>
    <section>
      <h2>Human boundary reconstruction</h2>
      <dl>
        <dt>Purpose</dt><dd>{escape(boundary.purpose)}</dd>
        <dt>Critical failure path</dt><dd>{escape(boundary.critical_failure_path)}</dd>
        <dt>Rollback trigger</dt><dd>{escape(boundary.rollback_trigger)}</dd>
        <dt>Rollback strategy</dt><dd>{escape(boundary.rollback_strategy)}</dd>
      </dl>
      <h2>Non-goals</h2><ul>{non_goals}</ul>
      <h2>Evidence limitations</h2><ul>{limitations}</ul>
    </section>
    <section>
      <h2>Configured checks</h2>
      <table><thead><tr><th>Check</th><th>Status</th><th>Exit</th><th>Duration</th></tr></thead><tbody>{check_rows}</tbody></table>
      <p>Raw command text and raw stdout/stderr are not included. Only digests, byte counts, and exit states are retained.</p>
    </section>
    <section>
      <h2>Claim boundary</h2>
      <p>{escape(receipt.claim_boundary.current_claim)}</p>
      <p class="warning"><strong>未经放行，不得交付。</strong> This self-attestation is not external delivery authority, production approval, independent audit, or proof that AI is always correct.</p>
      <code>{escape(receipt.receipt_id)}</code>
    </section>
  </main>
</body>
</html>
"""


def write_audit_artifacts(root: Path, artifacts: PersonalAuditArtifacts) -> Path:
    output_dir = root / ARTIFACT_RELATIVE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, payload in _artifact_mapping(artifacts).items():
        (output_dir / filename).write_text(pretty_json(payload), encoding="utf-8")
    (output_dir / ARTIFACT_FILENAMES["html"]).write_text(
        render_report(artifacts),
        encoding="utf-8",
    )
    return output_dir


def _load_model(path: Path, model_type: type[Any]) -> Any:
    if not path.is_file():
        raise PersonalClearanceError(f"required artifact is missing: {path.name}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert_safe_metadata(payload, label=path.name)
        return model_type.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise PersonalClearanceError(f"invalid artifact {path.name}: {exc}") from exc


def verify_project_clearance(
    project: str | Path,
    *,
    verified_at: str | None = None,
) -> dict[str, Any]:
    root = resolve_repository_root(project)
    config = load_config(root)
    output_dir = root / ARTIFACT_RELATIVE_DIR
    snapshot = _load_model(
        output_dir / ARTIFACT_FILENAMES["snapshot"], PersonalProjectSnapshotV1
    )
    check_run = _load_model(
        output_dir / ARTIFACT_FILENAMES["check_run"], PersonalCheckRunV1
    )
    boundary = _load_model(
        output_dir / ARTIFACT_FILENAMES["boundary"], PersonalBoundaryReconstructionV1
    )
    policy = _load_model(output_dir / ARTIFACT_FILENAMES["policy"], TrustPolicyV1)
    evidence = _load_model(
        output_dir / ARTIFACT_FILENAMES["evidence"], EvidenceBundleV1
    )
    reconstruction = _load_model(
        output_dir / ARTIFACT_FILENAMES["reconstruction"], QualifiedReconstructionV1
    )
    decision = _load_model(
        output_dir / ARTIFACT_FILENAMES["decision"], GateDecisionV1
    )
    receipt = _load_model(
        output_dir / ARTIFACT_FILENAMES["receipt"], PersonalClearanceReceiptV1
    )
    report_path = output_dir / ARTIFACT_FILENAMES["html"]
    if not report_path.is_file():
        raise PersonalClearanceError(f"required artifact is missing: {report_path.name}")
    loaded_artifacts = PersonalAuditArtifacts(
        snapshot=snapshot,
        check_run=check_run,
        boundary=boundary,
        policy=policy,
        evidence=evidence,
        reconstruction=reconstruction,
        decision=decision,
        receipt=receipt,
    )
    now = verified_at or _timestamp()
    current = capture_project_snapshot(root, config, captured_at=now)
    checks = {
        "project_state_current": current.subject_digest_sha256
        == snapshot.subject_digest_sha256,
        "config_current": current.config_digest_sha256 == snapshot.config_digest_sha256,
        "check_run_bound_to_snapshot": check_run.after_subject_digest_sha256
        == snapshot.subject_digest_sha256,
        "boundary_bound_to_config": boundary.config_digest_sha256
        == snapshot.config_digest_sha256,
        "receipt_bound_to_subject": receipt.subject_digest_sha256
        == snapshot.subject_digest_sha256,
        "snapshot_digest_matches": receipt.snapshot_digest_sha256
        == canonical_sha256(snapshot),
        "check_run_digest_matches": receipt.check_run_digest_sha256
        == canonical_sha256(check_run),
        "boundary_digest_matches": receipt.boundary_reconstruction_digest_sha256
        == canonical_sha256(boundary),
        "policy_digest_matches": receipt.policy_digest_sha256 == canonical_sha256(policy),
        "evidence_digest_matches": receipt.evidence_bundle_digest_sha256
        == canonical_sha256(evidence),
        "qualified_reconstruction_digest_matches": (
            receipt.qualified_reconstruction_digest_sha256
            == canonical_sha256(reconstruction)
        ),
        "gate_decision_digest_matches": receipt.gate_decision_digest_sha256
        == canonical_sha256(decision),
        "receipt_not_expired": parse_timestamp(now) < parse_timestamp(receipt.expires_at),
        "personal_scope_only": receipt.approved_scope == DeliveryScope.PERSONAL_LOCAL,
        "receipt_allowed": receipt.status == "allow",
        "human_report_matches_artifacts": report_path.read_text(encoding="utf-8")
        == render_report(loaded_artifacts),
    }
    replayed = evaluate_gate(
        policy,
        evidence,
        reconstruction,
        decided_at=decision.decided_at,
    )
    checks["deterministic_gate_replay_matches"] = replayed == decision
    checks["receipt_matches_gate"] = (
        receipt.gate_decision_ref == decision.decision_id
        and receipt.status == decision.status
        and receipt.approved_scope == decision.approved_scope
        and receipt.reasons == decision.reasons
        and receipt.missing_evidence_types == decision.missing_evidence_types
    )
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise PersonalClearanceError(
            "personal clearance verification failed: " + ", ".join(failed)
        )
    result = {
        "schema_version": "delivery-clearance.personal-verification.v1",
        "status": "pass",
        "approved_scope": receipt.approved_scope.value,
        "receipt_id": receipt.receipt_id,
        "checks": checks,
        "claim_boundary": (
            "This verifies a fresh, untampered self-audit for the exact current Git state and "
            "personal_local scope only. It is not independent review or external delivery authority."
        ),
    }
    assert_safe_metadata(result, label="personal clearance verification")
    return result
