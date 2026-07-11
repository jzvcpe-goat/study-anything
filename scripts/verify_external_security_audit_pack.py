#!/usr/bin/env python3
"""Verify the independent security audit preparation pack and claim boundary."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import sys
from typing import Any, Mapping
import zipfile

import generate_external_security_audit_pack as generator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "external-security-audit-pack-verification-v1"
EXPECTED_SCOPE_AREAS = {
    "oidc_and_tenant_authorization",
    "api_container_and_filesystem",
    "agent_egress_and_credentials",
    "dependency_and_supply_chain",
    "plugin_backup_sync_and_local_data",
    "dual_loop_and_delivery_trust",
    "ci_release_and_reliability",
}
EXPECTED_CBB_V1_PACK_ASSETS = {
    "docs/protocol.md",
    "docs/cbb-protocol-v1-contracts.md",
    "docs/cbb-protocol-v1-kernel.md",
    "docs/cbb-protocol-v1-provenance.md",
    "docs/cbb-protocol-v1-scenarios-and-qualification.md",
    "docs/cbb-protocol-v1-outcomes.md",
    "docs/cbb-protocol-v1-agentic-evolution.md",
    "platform/generated/study-anything-cbb-v1-contracts.json",
    "platform/generated/study-anything-cbb-v0-compatibility.json",
    "platform/generated/study-anything-cbb-v1-kernel.json",
    "platform/generated/study-anything-cbb-runtime-isolation.json",
    "platform/generated/study-anything-cbb-v1-provenance.json",
    "platform/generated/study-anything-cbb-v1-tamper-cases.json",
    "platform/generated/study-anything-cbb-v1-scenarios.json",
    "platform/generated/study-anything-cbb-v1-qualification.json",
    "platform/generated/study-anything-cbb-v1-outcomes.json",
    "platform/generated/study-anything-cbb-agentic-tool-boundary.json",
    "platform/generated/study-anything-cbb-memory-quarantine.json",
    "platform/generated/study-anything-cbb-evolution-gate.json",
    "platform/schemas/cbb/cbb.trust-policy.v1.schema.json",
    "platform/schemas/cbb/cbb.evidence-bundle.v1.schema.json",
    "platform/schemas/cbb/cbb.qualified-reconstruction.v1.schema.json",
    "platform/schemas/cbb/cbb.gate-decision.v1.schema.json",
    "platform/schemas/cbb/cbb.delivery-trust-receipt.v1.schema.json",
    "platform/schemas/cbb/cbb.receipt-provenance.v1.schema.json",
    "platform/schemas/cbb/cbb.delivery-outcome-receipt.v1.schema.json",
    "platform/schemas/cbb/cbb.evolution-gate-receipt.v1.schema.json",
    "fixtures/cbb-v1-contracts/pass.json",
    "fixtures/cbb-v1-contracts/missing-evidence.json",
    "fixtures/cbb-v1-contracts/hard-deny.json",
    "fixtures/cbb-v1-contracts/stale.json",
    "fixtures/cbb-v1-contracts/secret-like.json",
    "fixtures/cbb-v1-contracts/malformed.json",
    "fixtures/cbb-v1-contracts/naive-timestamp.json",
    "fixtures/cbb-v1-contracts/invalid-state.json",
    "fixtures/cbb-v1-contracts/scope-expansion.json",
    "fixtures/cbb-v1-kernel/pass.json",
    "fixtures/cbb-v1-kernel/missing-evidence.json",
    "fixtures/cbb-v1-kernel/failed-evidence.json",
    "fixtures/cbb-v1-kernel/stale-reconstruction.json",
    "fixtures/cbb-v1-kernel/hard-deny.json",
    "fixtures/cbb-v1-kernel/reference-mismatch.json",
    "fixtures/cbb-v1-kernel/claim-boundary-narrowing.json",
    "fixtures/cbb-v1-provenance/pass-signed.json",
    "fixtures/cbb-v1-provenance/unsigned-development.json",
    "fixtures/cbb-v1-provenance/expired.json",
    "fixtures/cbb-v1-provenance/revoked.json",
    "fixtures/cbb-v1-provenance/replay.json",
    "fixtures/cbb-v1-provenance/tampered-policy.json",
    "fixtures/cbb-v1-provenance/tampered-evidence.json",
    "fixtures/cbb-v1-provenance/tampered-reconstruction.json",
    "fixtures/cbb-v1-provenance/tampered-decision.json",
    "fixtures/cbb-v1-provenance/tampered-receipt.json",
    "fixtures/cbb-v1-provenance/tampered-signature.json",
    "fixtures/cbb-v1-provenance/wrong-public-key.json",
    "fixtures/cbb-v1-scenarios/personal-local-prototype.json",
    "fixtures/cbb-v1-scenarios/public-fake-data-demo.json",
    "fixtures/cbb-v1-scenarios/limited-beta.json",
    "fixtures/cbb-v1-scenarios/paid-customer-candidate.json",
    "fixtures/cbb-v1-scenarios/production-candidate-blocked.json",
    "fixtures/cbb-v1-scenarios/regulated-or-irreversible-blocked.json",
    "fixtures/cbb-v1-outcomes/monitored-no-adverse-signal.json",
    "fixtures/cbb-v1-outcomes/near-miss-narrows-scope.json",
    "fixtures/cbb-v1-outcomes/affected-party-challenge-freezes.json",
    "fixtures/cbb-v1-outcomes/claim-violation-revokes.json",
    "fixtures/cbb-v1-outcomes/failed-rollback-revokes.json",
    "fixtures/cbb-v1-agentic-evolution/approved-local-candidate.json",
    "fixtures/cbb-v1-agentic-evolution/missing-human-reconstruction.json",
    "fixtures/cbb-v1-agentic-evolution/hard-deny-change-blocked.json",
    "fixtures/cbb-v1-agentic-evolution/poisoned-memory-needs-evidence.json",
    "fixtures/cbb-v1-agentic-evolution/self-authorization-blocked.json",
    "fixtures/cbb-v1-agentic-evolution/tool-authority-expansion-blocked.json",
}
EXPECTED_CBB_V1_PLAN_ASSETS = EXPECTED_CBB_V1_PACK_ASSETS | {
    "docs/quality-audits/phase-31-cbb-protocol-v1-contracts.md",
    "docs/quality-audits/phase-33-cbb-protocol-v1-kernel.md",
    "docs/quality-audits/phase-34-cbb-protocol-v1-provenance.md",
    "docs/quality-audits/phase-35-delivery-clearance-scenarios-and-positioning.md",
    "docs/quality-audits/phase-36-delivery-clearance-outcomes.md",
    "docs/quality-audits/phase-37-agentic-evolution-isolation.md",
}
LOCAL_PATH_PATTERN = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\Users\\\\)")
SECRET_PATTERN = re.compile(
    r"(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"Bearer [A-Za-z0-9._-]{24,}|sk-[A-Za-z0-9]{16,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})",
    re.IGNORECASE,
)


class ExternalAuditPackVerificationError(RuntimeError):
    """Readable external audit pack verification failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ExternalAuditPackVerificationError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    values = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(values, dict), f"{path.name} must contain an object")
    return dict(values)


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    require(manifest.get("schema_version") == generator.SCHEMA_VERSION, "pack schema mismatch")
    require(manifest.get("status") == "ready_for_independent_audit", "pack must remain audit-ready only")
    require(manifest.get("package_type") == "independent_security_audit_preparation", "package type mismatch")
    require(set(manifest.get("scope_area_ids") or []) == EXPECTED_SCOPE_AREAS, "audit scope areas are incomplete")
    independence = manifest.get("independence") or {}
    require(independence.get("external_auditor_required") is True, "external auditor is not required")
    require(independence.get("human_security_reviewer_required") is True, "human reviewer is not required")
    require(independence.get("ai_only_review_sufficient") is False, "AI-only review cannot be sufficient")
    require(independence.get("self_certification_allowed") is False, "self-certification must be forbidden")
    require(independence.get("signed_report_required") is True, "signed report must be required")
    require(independence.get("audit_completed") is False, "preparation pack cannot claim audit completion")
    privacy = manifest.get("privacy") or {}
    require(privacy.get("metadata_only_pack") is True, "pack must be metadata-only")
    for key in (
        "raw_source_text_included",
        "raw_learner_data_included",
        "production_payloads_included",
        "screenshots_included",
        "real_secrets_included",
        "cookies_included",
        "bearer_tokens_included",
        "signed_urls_included",
        "user_owned_agent_credentials_included",
        "private_exploit_details_included",
        "local_absolute_paths_included",
        "environment_values_included",
        "raw_logs_included",
        "audit_finding_bodies_included",
    ):
        require(privacy.get(key) is False, f"privacy boundary must keep {key}=false")
    packaged_paths = {
        str(record.get("path"))
        for record in manifest.get("files") or []
        if isinstance(record, Mapping)
    }
    require(
        EXPECTED_CBB_V1_PACK_ASSETS <= packaged_paths,
        "canonical CBB v1 audit assets are incomplete",
    )


def validate_plan(plan: Mapping[str, Any]) -> None:
    require(plan.get("status") == "ready_for_independent_audit", "audit plan status mismatch")
    scope_areas = plan.get("scope_areas") or []
    require(isinstance(scope_areas, list), "scope_areas must be a list")
    require({item.get("id") for item in scope_areas if isinstance(item, dict)} == EXPECTED_SCOPE_AREAS, "audit plan scope mismatch")
    for item in scope_areas:
        require(isinstance(item, dict), "scope area must be an object")
        for command in item.get("evidence_commands") or []:
            tokens = shlex.split(command)
            script_tokens = [token for token in tokens if token.endswith(".py")]
            require(len(script_tokens) == 1, f"evidence command must name one script: {command}")
            require((ROOT / script_tokens[0]).is_file(), f"evidence command script missing: {script_tokens[0]}")
        for asset in item.get("evidence_assets") or []:
            require((ROOT / asset).is_file(), f"audit evidence asset missing: {asset}")
    trust_scope = next(
        item for item in scope_areas if item.get("id") == "dual_loop_and_delivery_trust"
    )
    require(
        {
            "python3 scripts/verify_cbb_v1_contracts.py --check",
            "python3 scripts/verify_cbb_v0_compatibility.py --check",
            "python3 scripts/verify_cbb_v1_kernel.py --check",
            "python3 scripts/verify_cbb_runtime_isolation.py --check",
            "python3 scripts/verify_cbb_v1_provenance.py --check",
            "python3 scripts/verify_cbb_v1_tamper_cases.py --check",
            "python3 scripts/generate_cbb_v1_scenario_assets.py --check",
            "python3 scripts/verify_cbb_v1_scenarios.py --check",
            "python3 scripts/verify_cbb_v1_qualification.py --check",
            "python3 scripts/generate_cbb_v1_outcome_assets.py --check",
            "python3 scripts/verify_cbb_v1_outcomes.py --check",
            "python3 scripts/generate_cbb_v1_agentic_assets.py --check",
            "python3 scripts/verify_cbb_agentic_tool_boundary.py --check",
            "python3 scripts/verify_cbb_memory_quarantine.py --check",
            "python3 scripts/verify_cbb_evolution_gate.py --check",
        }
        <= set(trust_scope.get("evidence_commands") or []),
        "canonical CBB v1 verifier commands are missing from the audit plan",
    )
    require(
        EXPECTED_CBB_V1_PLAN_ASSETS
        <= set(trust_scope.get("evidence_assets") or []),
        "canonical CBB v1 evidence assets are missing from the audit plan",
    )


def validate_schemas() -> None:
    finding = load_json(ROOT / "platform/schemas/security/external-security-audit-finding-v1.schema.json")
    report = load_json(ROOT / "platform/schemas/security/external-security-audit-report-v1.schema.json")
    require(
        finding.get("properties", {}).get("schema_version", {}).get("const")
        == "external-security-audit-finding-v1",
        "finding schema version is not fixed",
    )
    report_properties = report.get("properties", {})
    require(
        report_properties.get("audit_status", {}).get("const")
        == "completed_by_independent_auditor",
        "report schema does not require independent completion",
    )
    auditor = report_properties.get("auditor", {}).get("properties", {})
    require(
        auditor.get("independence_attested", {}).get("const") is True,
        "report schema does not require independence attestation",
    )


def validate_text_boundary(name: str, data: bytes) -> None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    require(LOCAL_PATH_PATTERN.search(text) is None, f"local absolute path leaked in {name}")
    require(SECRET_PATTERN.search(text) is None, f"secret-like value leaked in {name}")


def validate_archive(manifest: Mapping[str, Any]) -> dict[str, Any]:
    archive_data = generator.ARCHIVE_PATH.read_bytes()
    archive_meta = manifest.get("archive") or {}
    require(sha256_bytes(archive_data) == archive_meta.get("sha256"), "archive checksum mismatch")
    checksum = generator.SHA256_PATH.read_text(encoding="utf-8")
    require(checksum == f"{archive_meta['sha256']}  {generator.PACKAGE_NAME}.zip\n", "checksum sidecar mismatch")

    with zipfile.ZipFile(generator.ARCHIVE_PATH) as archive:
        names = archive.namelist()
        require(bool(names), "audit archive is empty")
        require(len(names) == len(set(names)), "audit archive contains duplicate entries")
        root_prefix = f"{generator.ARCHIVE_ROOT}/"
        for name in names:
            path = PurePosixPath(name)
            require(name.startswith(root_prefix), f"archive entry is outside package root: {name}")
            require(not path.is_absolute() and ".." not in path.parts, f"unsafe archive entry: {name}")
            validate_text_boundary(name, archive.read(name))

        archived_manifest = json.loads(archive.read(f"{root_prefix}manifest.json"))
        validate_manifest(archived_manifest)
        require(
            f"{root_prefix}AUDITOR_START_HERE.md" in names,
            "auditor start guide missing from archive",
        )
        for record in manifest.get("files") or []:
            relative = str(record["path"])
            archive_path = str(record["archive_path"])
            require(archive_path in names, f"manifest file missing from archive: {relative}")
            archive_bytes = archive.read(archive_path)
            source_bytes = (ROOT / relative).read_bytes()
            require(archive_bytes == source_bytes, f"archive source mismatch: {relative}")
            require(sha256_bytes(archive_bytes) == record["sha256"], f"file digest mismatch: {relative}")

    return {
        "archive_sha256": archive_meta["sha256"],
        "archive_bytes": len(archive_data),
        "archive_entry_count": len(names),
        "single_root": True,
        "offline_hash_validation": True,
    }


def verify() -> dict[str, Any]:
    generator.check_outputs()
    manifest = load_json(generator.SIDECAR_PATH)
    validate_manifest(manifest)
    plan = load_json(ROOT / "security/audit/audit-plan.json")
    validate_plan(plan)
    validate_schemas()
    archive = validate_archive(manifest)

    invalid = deepcopy(manifest)
    invalid["status"] = "audit_passed"
    invalid["independence"]["audit_completed"] = True
    try:
        validate_manifest(invalid)
    except ExternalAuditPackVerificationError as exc:
        negative_result = str(exc)
    else:  # pragma: no cover - defensive guard
        raise ExternalAuditPackVerificationError("self-certified audit status was accepted")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "package": {
            "schema_version": manifest["schema_version"],
            "status": manifest["status"],
            "scope_area_count": len(manifest["scope_area_ids"]),
            "file_count": len(manifest["files"]),
            **archive,
        },
        "independence": {
            "external_auditor_required": True,
            "human_security_reviewer_required": True,
            "ai_only_review_sufficient": False,
            "self_certification_allowed": False,
            "signed_report_required": True,
            "audit_completed": False,
        },
        "negative_checks": {
            "self_certified_audit_pass_rejected": negative_result,
            "unsafe_archive_paths_rejected": True,
            "local_absolute_paths_rejected": True,
            "secret_like_values_rejected": True,
        },
        "privacy": {
            "metadata_only": True,
            "raw_source_text_included": False,
            "raw_learner_data_included": False,
            "production_payloads_included": False,
            "screenshots_included": False,
            "real_secrets_included": False,
            "cookies_or_bearer_tokens_included": False,
            "signed_urls_included": False,
            "user_owned_agent_credentials_included": False,
            "private_exploit_details_included": False,
            "local_absolute_paths_included": False,
            "model_calls_performed": False,
            "external_network_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": (
            "This verifies that a deterministic metadata-only package is ready for an "
            "independent human-led security audit. It does not prove that an audit or "
            "penetration test ran, that findings were remediated, that hosted production "
            "is secure, or that the repository is vulnerability-free."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    try:
        report = verify()
    except (ExternalAuditPackVerificationError, generator.ExternalAuditPackError, OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"verify_external_security_audit_pack failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
