#!/usr/bin/env python3
"""Verify that the platform adoption pack can be consumed as an external tool directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
DEFAULT_TRANSCRIPT = ROOT / "platform" / "generated" / "study-anything-operator-drill-transcript.json"
SCHEMA_VERSION = "study-anything-operator-drill-v1"
ARCHIVE_SCHEMA = "study-anything-platform-adoption-pack-v1"
PACK_SCHEMA = "study-anything-platform-pack-v1"

PLATFORM_REQUIREMENTS = {
    "kimi": {
        "display": "Kimi Work / Kimi-compatible Agent",
        "terms": ["Kimi", "localhost", "gateway", "adoption-proof-v1"],
        "required_entrypoints": ["openai_tools", "openapi", "gateway", "gateway_verifier"],
        "must_import": [
            "platform/generated/study-anything-openai-tools.json",
            "platform/generated/study-anything-platform-openapi.json",
        ],
    },
    "codex": {
        "display": "Codex Skill / terminal Agent",
        "terms": ["Skill", "study_anything_cli.py", "adoption-proof-v1"],
        "required_entrypoints": ["skill", "cli", "demo"],
        "must_import": [
            "skills/study-anything/SKILL.md",
            "platform/generated/study-anything-tool-catalog.md",
        ],
    },
    "workbuddy": {
        "display": "WorkBuddy-style HTTP workspace",
        "terms": ["OpenAPI", "HTTP", "adoption-proof-v1"],
        "required_entrypoints": ["openapi", "tool_catalog"],
        "must_import": [
            "platform/generated/study-anything-platform-openapi.json",
            "platform/generated/study-anything-tool-catalog.md",
        ],
    },
}

REQUIRED_EXPORT_EVIDENCE = [
    "commercial_readiness.schema_version == commercial-readiness-v1",
    "adoption_telemetry.schema_version == adoption-telemetry-v1",
    "pmf_readiness.schema_version == pmf-readiness-v1",
    "agent_audit.status == verified",
    "agent_eval_policy.schema_version == agent-eval-policy-v1",
    "agent_eval_report.schema_version == agent-eval-report-v1",
    "agent_eval_report.native_fast_gate.status == pass",
    "agent_quality_eval.schema_version == agent-quality-eval-v1",
    "enrichment_artifact.schema_version == learning-enrichment-artifact-v1",
    "obsidian_export.schema_version == obsidian-markdown-export-v1",
    "learning_package.schema_version == learning-package-v1",
    "second_brain.schema_version == second-brain-handoff-v1",
    "plugin_sdk.schema_version == plugin-sdk-v1",
    "plugin_capability_index.schema_version == plugin-capability-index-v1",
    "plugin_package_validation.schema_version == plugin-package-validation-v1",
    "plugin_quarantine.schema_version == plugin-quarantine-verification-v1",
    "deployment_guide.schema_version == deployment-guide-v1",
    "ecosystem_submission.schema_version == ecosystem-submission-v1",
    "ecosystem_submission_verification.schema_version == ecosystem-submission-verification-v1",
    "adoption_telemetry_verification.schema_version == adoption-telemetry-verification-v1",
    "agent_gateway_hardening.schema_version == agent-gateway-hardening-verification-v1",
    "external_agent_adapter_hardening.schema_version == external-agent-adapter-hardening-v1",
    "notebooklm_obsidian_bridge_hardening.schema_version == notebooklm-obsidian-bridge-hardening-v1",
    "learning_enrichment_bridge.schema_version == learning-enrichment-bridge-verification-v1",
    "security_recovery_hardening.schema_version == security-recovery-hardening-verification-v1",
    "platform_submission_dry_run.schema_version == platform-submission-dry-run-v1",
    "platform_manual_submission_rehearsal.schema_version == platform-manual-submission-rehearsal-v1",
    "first_lesson_authoring_kit.schema_version == first-run-lesson-authoring-kit-v1",
    "external_eval_marketplace_harness.schema_version == external-eval-marketplace-harness-v1",
    "agent_eval_marketplace_enforcement.schema_version == agent-eval-marketplace-enforcement-v1",
    "platform_adoption_feedback_diagnostics.schema_version == platform-adoption-feedback-diagnostics-v1",
    "platform_feedback_package.schema_version == platform-feedback-package-v1",
    "platform_field_rehearsal.schema_version == platform-field-adoption-rehearsal-v1",
    "platform_import_failure_fixture.schema_version == platform-import-failure-fixture-v1",
    "platform_support_triage.schema_version == platform-support-triage-v1",
    "platform_support_ticket_fixture.schema_version == platform-support-ticket-fixture-v1",
    "platform_onboarding_readiness.schema_version == platform-onboarding-readiness-v1",
    "platform_triage_dashboard.schema_version == platform-triage-dashboard-v1",
    "platform_release_blocker_fixture.schema_version == platform-release-blocker-fixture-v1",
    "public_support_status.schema_version == public-support-status-v1",
    "public_maintainer_dashboard.schema_version == public-maintainer-dashboard-v1",
    "public_status_linkage_fixture.schema_version == public-status-linkage-fixture-v1",
    "published_image_evidence.schema_version == published-image-evidence-v1",
    "published_image_evidence_fixture.schema_version == published-image-evidence-fixture-v1",
    "adopter_evidence_archive.schema_version == adopter-evidence-archive-v1",
    "adopter_evidence_fixture.schema_version == adopter-evidence-fixture-v1",
    "release_asset_adoption.schema_version == release-asset-adoption-v1",
    "release_asset_adoption_fixture.schema_version == release-asset-adoption-fixture-v1",
    "release_asset_adoption_proof.schema_version == release-asset-adoption-proof-v1",
    "plugin_ecosystem_adoption_kit.schema_version == plugin-ecosystem-adoption-kit-v1",
    "deployment_hardening.schema_version == deployment-hardening-verification-v1",
]

FORBIDDEN_PROOF_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{12,}"),
]


class OperatorDrillError(RuntimeError):
    """Readable operator-drill failure."""


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise OperatorDrillError(f"Cannot read JSON {path}: {exc}") from exc


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not (root / "manifest.json").exists():
            raise OperatorDrillError(f"Pack root does not contain manifest.json: {root}")
        return root

    pack_path = Path(args.pack).resolve()
    if not pack_path.exists():
        raise OperatorDrillError(f"Adoption pack archive is missing: {pack_path}")
    with zipfile.ZipFile(pack_path) as archive:
        names = archive.namelist()
        roots = {name.split("/", 1)[0] for name in names if "/" in name}
        if len(roots) != 1:
            raise OperatorDrillError(f"Adoption pack archive should have one root, got {sorted(roots)}")
        archive.extractall(tmp_root)
    return tmp_root / next(iter(roots))


def relative_exists(pack_root: Path, relative_path: str) -> bool:
    return (pack_root / relative_path).is_file()


def validate_archive_manifest(pack_root: Path) -> dict[str, Any]:
    manifest = read_json(pack_root / "manifest.json")
    if manifest.get("schema_version") != ARCHIVE_SCHEMA:
        raise OperatorDrillError(f"Unexpected adoption pack schema: {manifest.get('schema_version')}")
    if manifest.get("no_frontend_required") is not True:
        raise OperatorDrillError("Adoption pack must declare no_frontend_required=true.")
    if manifest.get("real_model_keys_stored_by_study_anything") is not False:
        raise OperatorDrillError("Adoption pack must declare that Study Anything stores no real model keys.")

    missing_files: list[str] = []
    sha_mismatches: list[str] = []
    for record in manifest.get("files", []):
        path = str(record.get("path"))
        target = pack_root / path
        if not target.exists():
            missing_files.append(path)
            continue
        if sha256_file(target) != record.get("sha256"):
            sha_mismatches.append(path)
    if missing_files or sha_mismatches:
        raise OperatorDrillError(
            f"Adoption pack file validation failed: missing={missing_files} sha_mismatches={sha_mismatches}"
        )
    return manifest


def operation_ids(openapi: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for methods in openapi.get("paths", {}).values():
        if not isinstance(methods, dict):
            continue
        for operation in methods.values():
            if isinstance(operation, dict) and operation.get("operationId"):
                found.add(str(operation["operationId"]))
    return found


def validate_tool_import_assets(pack_root: Path, required_tools: list[str]) -> dict[str, Any]:
    openai_tools = read_json(pack_root / "platform/generated/study-anything-openai-tools.json")
    openapi = read_json(pack_root / "platform/generated/study-anything-platform-openapi.json")
    if not isinstance(openai_tools, list):
        raise OperatorDrillError("OpenAI tool import asset must be a list.")
    if openapi.get("openapi") != "3.1.0":
        raise OperatorDrillError(f"Unexpected OpenAPI version: {openapi.get('openapi')}")

    function_names: set[str] = set()
    malformed_tools: list[str] = []
    for item in openai_tools:
        function = item.get("function") if isinstance(item, dict) else None
        if not isinstance(function, dict):
            malformed_tools.append("<missing function>")
            continue
        name = str(function.get("name", ""))
        function_names.add(name)
        parameters = function.get("parameters")
        description = str(function.get("description", ""))
        if (
            item.get("type") != "function"
            or not name.startswith("study_anything_")
            or not isinstance(parameters, dict)
            or parameters.get("type") != "object"
            or "Method:" not in description
        ):
            malformed_tools.append(name or "<unnamed>")
    if malformed_tools:
        raise OperatorDrillError(f"Malformed OpenAI tool definitions: {malformed_tools}")

    openapi_operation_ids = operation_ids(openapi)
    missing_openai = sorted(set(required_tools) - function_names)
    missing_openapi = sorted(set(required_tools) - openapi_operation_ids)
    if missing_openai or missing_openapi:
        raise OperatorDrillError(
            f"Generated tool import assets are missing required tools: "
            f"openai={missing_openai} openapi={missing_openapi}"
        )

    servers = openapi.get("servers", [])
    server_urls = [str(server.get("url", "")) for server in servers if isinstance(server, dict)]
    if "http://127.0.0.1:8000" not in server_urls:
        raise OperatorDrillError("OpenAPI asset must keep the default local API server.")
    if openapi.get("components", {}).get("securitySchemes"):
        raise OperatorDrillError("OpenAPI import asset must not define API key security schemes.")

    return {
        "openai_tool_count": len(openai_tools),
        "openapi_path_count": len(openapi.get("paths", {})),
        "required_tools_present": sorted(set(required_tools) & function_names & openapi_operation_ids),
    }


def validate_platform(pack_root: Path, platform_id: str) -> dict[str, Any]:
    requirements = PLATFORM_REQUIREMENTS[platform_id]
    pack_path = pack_root / "platform" / "packs" / platform_id / "pack.json"
    readme_path = pack_root / "platform" / "packs" / platform_id / "README.md"
    pack = read_json(pack_path)
    readme = readme_path.read_text(encoding="utf-8")
    if pack.get("schema_version") != PACK_SCHEMA:
        raise OperatorDrillError(f"{platform_id} pack schema drifted: {pack.get('schema_version')}")
    if pack.get("platform_id") != platform_id:
        raise OperatorDrillError(f"{platform_id} pack has wrong platform_id: {pack.get('platform_id')}")

    entrypoints = pack.get("entrypoints", {})
    missing_entrypoints = [
        key for key in requirements["required_entrypoints"] if key not in entrypoints
    ]
    if missing_entrypoints:
        raise OperatorDrillError(f"{platform_id} pack missing entrypoints: {missing_entrypoints}")

    missing_paths: list[str] = []
    for value in list(entrypoints.values()) + list(pack.get("import_assets", [])):
        path = str(value)
        if not relative_exists(pack_root, path):
            missing_paths.append(path)
    for path in requirements["must_import"]:
        if path not in pack.get("import_assets", []) and path not in entrypoints.values():
            missing_paths.append(path)
    if missing_paths:
        raise OperatorDrillError(f"{platform_id} pack references missing files: {sorted(set(missing_paths))}")

    readme_lower = readme.lower()
    missing_terms = [term for term in requirements["terms"] if term.lower() not in readme_lower]
    if missing_terms:
        raise OperatorDrillError(f"{platform_id} README missing operator terms: {missing_terms}")

    evidence = pack.get("acceptance_evidence", [])
    missing_evidence = [item for item in REQUIRED_EXPORT_EVIDENCE if item not in evidence]
    if missing_evidence:
        raise OperatorDrillError(f"{platform_id} pack missing acceptance evidence: {missing_evidence}")

    forbidden = " ".join(pack.get("must_not_log_or_share", []))
    if "API keys or model secrets" not in forbidden:
        raise OperatorDrillError(f"{platform_id} pack must explicitly forbid sharing model secrets.")

    return {
        "platform_id": platform_id,
        "display": requirements["display"],
        "integration_mode": pack.get("integration_mode"),
        "entrypoints": entrypoints,
        "import_assets": pack.get("import_assets", []),
        "local_verification_commands": pack.get("local_verification_commands", []),
        "acceptance_evidence_count": len(evidence),
        "privacy_forbids_model_secrets": True,
    }


def operator_steps(platform_id: str, platform: dict[str, Any]) -> list[dict[str, str]]:
    import_assets = ", ".join(platform.get("import_assets", []))
    commands = platform.get("local_verification_commands", [])
    first_command = commands[0] if commands else "python3 scripts/diagnose_adoption.py"
    final_command = commands[-1] if commands else "python3 scripts/diagnose_adoption.py"
    return [
        {
            "step": "unpack",
            "operator_action": f"Open platform/packs/{platform_id}/README.md and pack.json from the adoption pack.",
            "acceptance": f"{platform['display']} sees its own entrypoints and privacy boundary.",
        },
        {
            "step": "import_tools",
            "operator_action": f"Import or expose: {import_assets}.",
            "acceptance": "Tool names start with study_anything_ and map to local HTTP endpoints only.",
        },
        {
            "step": "start_runtime",
            "operator_action": "Start Skill Mode or the published Docker image with local secrets outside Study Anything.",
            "acceptance": "GET /v1/health returns ok and no standalone frontend is required.",
        },
        {
            "step": "review_deployment_path",
            "operator_action": "Run python3 scripts/verify_deployment_hardening.py --check and use diagnose_adoption.py if Docker, GHCR, ports, paths, or Agent endpoints fail.",
            "acceptance": "deployment-hardening-verification-v1 confirms Skill Mode, published image, source build, and fallback guidance are aligned.",
        },
        {
            "step": "verify_learning_enrichment_bridge",
            "operator_action": "Run python3 scripts/verify_learning_enrichment_bridge.py --check before claiming NotebookLM, Obsidian, or HTML micro-lesson handoff works.",
            "acceptance": "learning-enrichment-bridge-verification-v1 confirms all enrichment source types, HTML artifact structure, strict second-brain privacy, and platform pack evidence.",
        },
        {
            "step": "verify_agent_eval_marketplace_enforcement",
            "operator_action": "Run python3 scripts/verify_agent_eval_marketplace_enforcement.py --check before claiming external judge or marketplace eval readiness.",
            "acceptance": "agent-eval-marketplace-enforcement-v1 confirms native gates, optional external judges, required-mode failures, timeout diagnostics, baseline regression, and redacted platform evidence.",
        },
        {
            "step": "verify_platform_feedback_diagnostics",
            "operator_action": "Run python3 scripts/verify_platform_adoption_feedback_diagnostics.py --check and python3 scripts/generate_platform_feedback_package.py --check before sharing adoption failures.",
            "acceptance": "platform-adoption-feedback-diagnostics-v1 and platform-feedback-package-v1 confirm import errors, version drift, missing commands, endpoint health, and redacted local feedback are aligned.",
        },
        {
            "step": "publish_public_support_status",
            "operator_action": "Run python3 scripts/generate_platform_public_support_status.py --check and python3 scripts/verify_platform_public_support_status.py --check before publishing maintainer status.",
            "acceptance": "public-support-status-v1, public-maintainer-dashboard-v1, and public-status-linkage-fixture-v1 confirm only labels, commands, schema names, fixture hashes, and release readiness are publishable.",
        },
        {
            "step": "package_published_image_evidence",
            "operator_action": "Run python3 scripts/generate_published_image_evidence.py --check and python3 scripts/verify_published_image_evidence.py --check before public handoff.",
            "acceptance": "published-image-evidence-v1 and published-image-evidence-fixture-v1 confirm manifest platforms, docker-images workflow, local pull-timeout fallback, optional remote smoke replay, and release-blocking classifications are metadata-only.",
        },
        {
            "step": "package_adopter_evidence_archive",
            "operator_action": "Run python3 scripts/generate_adopter_evidence_archive.py --check and python3 scripts/verify_adopter_evidence_archive.py --check before public handoff.",
            "acceptance": "adopter-evidence-archive-v1 and adopter-evidence-fixture-v1 confirm release proof, checksums, Docker manifest evidence, known limitations, and maintainer handoff are metadata-only.",
        },
        {
            "step": "verify_release_asset_adoption",
            "operator_action": "Run python3 scripts/generate_release_asset_adoption.py --check and python3 scripts/verify_release_asset_adoption.py --fixture fixtures/release-asset-adoption/asset-only-pass.json --asset-dir platform/generated --runtime metadata-only before telling platform operators to use GitHub Release assets.",
            "acceptance": "release-asset-adoption-v1, release-asset-adoption-fixture-v1, and release-asset-adoption-proof-v1 confirm required release zip assets, digest checks, adoption-pack manifest hashes, and replay classifications are metadata-only.",
        },
        {
            "step": "verify_platform_field_rehearsal",
            "operator_action": "Run python3 scripts/generate_platform_field_rehearsal.py --check and python3 scripts/verify_platform_field_rehearsal.py --check before asking external users to try a platform import.",
            "acceptance": "platform-field-adoption-rehearsal-v1 and platform-import-failure-fixture-v1 confirm Kimi, Codex, WorkBuddy, generic OpenAPI rehearsals, import quirks, and mock failure fixtures are actionable and redacted.",
        },
        {
            "step": "run_learning_loop",
            "operator_action": first_command,
            "acceptance": "The platform can create/import context, run learning, answer, and fetch mastery.",
        },
        {
            "step": "collect_redacted_evidence",
            "operator_action": final_command,
            "acceptance": "The shared transcript contains audit/eval/export schemas, not raw source, answers, endpoints, or keys.",
        },
    ]


def assert_redacted(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    forbidden_literals = [
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
        "Private answer:",
        "Private platform browser/video context",
    ]
    leaks = [literal for literal in forbidden_literals if literal in serialized]
    for pattern in FORBIDDEN_PROOF_PATTERNS:
        if pattern.search(serialized):
            leaks.append(pattern.pattern)
    if leaks:
        raise OperatorDrillError(f"Operator drill transcript leaked private data: {leaks}")


def build_transcript(pack_root: Path, pack_path: Path | None) -> dict[str, Any]:
    manifest = validate_archive_manifest(pack_root)
    required_tools = [str(name) for name in manifest.get("required_tool_names", [])]
    generated_assets = validate_tool_import_assets(pack_root, required_tools)
    platforms = {
        platform_id: validate_platform(pack_root, platform_id)
        for platform_id in sorted(PLATFORM_REQUIREMENTS)
    }
    transcript = {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "pack": {
            "schema_version": manifest.get("schema_version"),
            "version": manifest.get("version"),
            "archive_name": Path(pack_path).name if pack_path else None,
            "file_count": len(manifest.get("files", [])),
            "no_frontend_required": manifest.get("no_frontend_required"),
            "real_model_keys_stored_by_study_anything": manifest.get(
                "real_model_keys_stored_by_study_anything"
            ),
        },
        "generated_tool_assets": generated_assets,
        "platforms": platforms,
        "operator_drills": {
            platform_id: operator_steps(platform_id, platform)
            for platform_id, platform in platforms.items()
        },
        "handoff_contract": {
            "notebooklm_fixture": "fixtures/notebooklm/notebooklm-style-context-package.json",
            "enrichment_artifact_schema": "learning-enrichment-artifact-v1",
            "obsidian_export_schema": "obsidian-markdown-export-v1",
            "learning_package_schema": "learning-package-v1",
            "second_brain_schema": "second-brain-handoff-v1",
            "plugin_sdk_schema": "plugin-sdk-v1",
            "plugin_capability_index_schema": "plugin-capability-index-v1",
            "plugin_package_validation_schema": "plugin-package-validation-v1",
            "plugin_quarantine_schema": "plugin-quarantine-verification-v1",
            "deployment_guide_schema": "deployment-guide-v1",
            "commercial_readiness_schema": "commercial-readiness-v1",
            "ecosystem_submission_schema": "ecosystem-submission-v1",
            "ecosystem_submission_verification_schema": "ecosystem-submission-verification-v1",
            "notebooklm_obsidian_bridge_hardening_schema": "notebooklm-obsidian-bridge-hardening-v1",
            "learning_enrichment_bridge_schema": "learning-enrichment-bridge-verification-v1",
            "security_recovery_hardening_schema": "security-recovery-hardening-verification-v1",
            "platform_submission_dry_run_schema": "platform-submission-dry-run-v1",
            "platform_manual_submission_rehearsal_schema": "platform-manual-submission-rehearsal-v1",
            "first_lesson_authoring_kit_schema": "first-run-lesson-authoring-kit-v1",
            "agent_eval_marketplace_enforcement_schema": "agent-eval-marketplace-enforcement-v1",
            "platform_adoption_feedback_diagnostics_schema": "platform-adoption-feedback-diagnostics-v1",
            "platform_feedback_package_schema": "platform-feedback-package-v1",
            "platform_field_rehearsal_schema": "platform-field-adoption-rehearsal-v1",
            "platform_import_failure_fixture_schema": "platform-import-failure-fixture-v1",
            "public_support_status_schema": "public-support-status-v1",
            "public_maintainer_dashboard_schema": "public-maintainer-dashboard-v1",
            "public_status_linkage_fixture_schema": "public-status-linkage-fixture-v1",
            "published_image_evidence_schema": "published-image-evidence-v1",
            "published_image_evidence_fixture_schema": "published-image-evidence-fixture-v1",
            "adopter_evidence_archive_schema": "adopter-evidence-archive-v1",
            "adopter_evidence_fixture_schema": "adopter-evidence-fixture-v1",
            "release_asset_adoption_schema": "release-asset-adoption-v1",
            "release_asset_adoption_fixture_schema": "release-asset-adoption-fixture-v1",
            "release_asset_adoption_proof_schema": "release-asset-adoption-proof-v1",
            "plugin_ecosystem_adoption_kit_schema": "plugin-ecosystem-adoption-kit-v1",
            "deployment_hardening_schema": "deployment-hardening-verification-v1",
            "external_agent_adapter_hardening_schema": "external-agent-adapter-hardening-v1",
            "shared_logs_are_redacted": True,
        },
        "privacy": {
            "no_real_model_keys_in_study_anything": True,
            "external_platform_owns_browsing_files_video_and_model_credentials": True,
            "study_anything_owns_learning_state_audit_eval_and_exports": True,
        },
    }
    assert_redacted(transcript)
    return transcript


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=str(DEFAULT_PACK))
    parser.add_argument("--pack-root")
    parser.add_argument("--output", default=str(DEFAULT_TRANSCRIPT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    tmp_root = Path(tempfile.mkdtemp(prefix="study-anything-operator-drill-"))
    try:
        pack_root = resolve_pack_root(args, tmp_root)
        pack_path = None if args.pack_root else Path(args.pack).resolve()
        payload = build_transcript(pack_root, pack_path)
        text = dump_json(payload)
        output = Path(args.output)
        if args.check:
            if not output.exists():
                raise OperatorDrillError(f"Operator drill transcript missing: {output}")
            if output.read_text(encoding="utf-8") != text:
                raise OperatorDrillError(
                    "Operator drill transcript is stale. Run "
                    "`python3 scripts/verify_platform_operator_drill.py --write`."
                )
            print("ok    platform operator drill transcript is up to date")
            return
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
            print(f"wrote {output.relative_to(ROOT)}")
            return
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_operator_drill failed: {exc}", file=sys.stderr)
        sys.exit(1)
