#!/usr/bin/env python3
"""Verify the Cognitive Loop Mastra adapter contract pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-mastra-adapter.json"
MANIFEST = ROOT / "platform" / "mastra" / "manifest.json"
README = ROOT / "platform" / "mastra" / "README.md"
TEMPLATE = ROOT / "platform" / "mastra" / "cognitive-loop-mastra-adapter.ts"
SCHEMA_VERSION = "cognitive-loop-mastra-adapter-verification-v1"

FORBIDDEN_TEXT = (
    "sk-proj-",
    "bearer ",
    "api_key",
    "secret_access_key",
    "raw private source text",
    "learner answer:",
    "http://127.0.0.1:8787/",
    "agent_endpoint_secret",
    "model_api_key",
)

REQUIRED_TYPESCRIPT_MARKERS = (
    '@mastra/core/workflows',
    "createStep",
    "createWorkflow",
    "suspendSchema",
    "resumeSchema",
    "suspend(",
    "bail(",
    "Human Mastery Gate",
    "CognitiveLoopRunInputSchema",
    "CognitiveLoopRunOutputSchema",
    "metadataOnly: z.literal(true)",
    "rawSourceTextIncluded: z.literal(false)",
    "modelKeysIncluded: z.literal(false)",
    '"watcher_ingest"',
)

REQUIRED_DOC_MARKERS = (
    "contract pack",
    "not the shipped Study Anything runtime",
    "does not store model keys",
    "HITL Mapping",
    "Current Boundary",
)


class MastraAdapterVerificationError(RuntimeError):
    """Readable Mastra adapter verifier failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def assert_no_forbidden_text(value: str, *, label: str) -> None:
    lowered = value.lower()
    leaked = [needle for needle in FORBIDDEN_TEXT if needle in lowered]
    if leaked:
        raise MastraAdapterVerificationError(f"{label} contains private or secret-like text: {leaked}")


def assert_file(path: Path) -> None:
    if not path.is_file():
        raise MastraAdapterVerificationError(f"Required Mastra adapter file is missing: {path}")


def load_manifest() -> dict[str, Any]:
    assert_file(MANIFEST)
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MastraAdapterVerificationError(f"Mastra adapter manifest is invalid JSON: {exc}") from exc
    if manifest.get("schema_version") != "cognitive-loop-mastra-adapter-manifest-v1":
        raise MastraAdapterVerificationError("Mastra adapter manifest schema_version drifted.")
    if manifest.get("status") != "contract_pack":
        raise MastraAdapterVerificationError("Mastra adapter manifest must remain a contract_pack.")
    runtime = manifest.get("runtime") or {}
    if runtime.get("framework") != "Mastra":
        raise MastraAdapterVerificationError("Mastra adapter manifest runtime.framework drifted.")
    if runtime.get("runtime_started_by_study_anything") is not False:
        raise MastraAdapterVerificationError("Study Anything must not start Mastra in this contract pack.")
    if runtime.get("compiled_in_this_repo") is not False:
        raise MastraAdapterVerificationError("The Mastra template must not be claimed as compiled here.")
    privacy = manifest.get("privacy") or {}
    for key in (
        "raw_source_text_allowed",
        "diff_bodies_allowed",
        "learner_answers_allowed",
        "agent_endpoint_secrets_allowed",
        "model_api_keys_allowed",
        "prompt_text_allowed",
    ):
        if privacy.get(key) is not False:
            raise MastraAdapterVerificationError(f"Manifest privacy.{key} must be false.")
    claims = manifest.get("claim_boundaries") or {}
    for key in (
        "mastra_runtime_integrated",
        "watcher_daemon_shipped",
        "realtime_html_console_shipped",
        "study_anything_stores_real_model_keys",
    ):
        if claims.get(key) is not False:
            raise MastraAdapterVerificationError(f"Manifest claim_boundaries.{key} must be false.")
    return manifest


def inspect_template(template_text: str) -> dict[str, Any]:
    missing = [marker for marker in REQUIRED_TYPESCRIPT_MARKERS if marker not in template_text]
    if missing:
        raise MastraAdapterVerificationError(f"Mastra TypeScript scaffold is missing markers: {missing}")
    assert_no_forbidden_text(template_text, label="Mastra TypeScript scaffold")
    return {
        "uses_mastra_workflows_import": True,
        "declares_input_schema": True,
        "declares_output_schema": True,
        "declares_suspend_schema": True,
        "declares_resume_schema": True,
        "maps_human_gate_to_suspend": True,
        "maps_rejection_to_bail": True,
        "metadata_only_constraints": True,
    }


def inspect_readme(readme_text: str) -> dict[str, Any]:
    normalized = " ".join(readme_text.split())
    missing = [marker for marker in REQUIRED_DOC_MARKERS if marker not in normalized]
    if missing:
        raise MastraAdapterVerificationError(f"Mastra adapter README is missing markers: {missing}")
    assert_no_forbidden_text(readme_text, label="Mastra adapter README")
    return {
        "install_instructions_present": "npm create mastra@latest" in readme_text,
        "hitl_mapping_documented": "HITL Mapping" in readme_text,
        "boundary_documented": "Current Boundary" in readme_text,
        "model_key_storage_denied": "does not store model keys" in readme_text,
    }


def build_dry_run() -> dict[str, Any]:
    return {
        "low_risk": {
            "input": {
                "risk": {"level": "low", "requiresHumanGate": False},
                "artifact_kinds": ["project_snapshot", "decision_card", "event_store", "watcher_ingest"],
            },
            "expected_status": "not_required",
            "suspended": False,
        },
        "high_risk": {
            "input": {
                "risk": {"level": "high", "requiresHumanGate": True},
                "artifact_kinds": ["project_snapshot", "decision_card", "event_store", "watcher_ingest"],
            },
            "expected_status": "suspended_until_human_resume",
            "suspended": True,
            "suspend_payload_redacted": True,
        },
        "rejected": {
            "resume": {"approved": False, "reason": "Insufficient operator understanding."},
            "expected_status": "rejected",
            "uses_bail": True,
        },
        "missing_evidence": {
            "input": {
                "artifact_kinds": ["project_snapshot"],
            },
            "expected_status": "rejected",
            "uses_bail": True,
        },
    }


def build_report() -> dict[str, Any]:
    for path in (MANIFEST, README, TEMPLATE):
        assert_file(path)
    manifest = load_manifest()
    readme_text = README.read_text(encoding="utf-8")
    template_text = TEMPLATE.read_text(encoding="utf-8")
    readme_checks = inspect_readme(readme_text)
    template_checks = inspect_template(template_text)
    file_records = []
    for path in (README, TEMPLATE, MANIFEST):
        file_records.append(
            {
                "path": relative_path(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Verify the copy-ready Cognitive Loop Mastra adapter contract pack for external "
            "Mastra projects without claiming this repository ships the full Mastra runtime."
        ),
        "manifest": {
            "schema_version": manifest["schema_version"],
            "adapter_id": manifest["adapter_id"],
            "adapter_version": manifest["adapter_version"],
            "status": manifest["status"],
        },
        "files": file_records,
        "typescript_scaffold": template_checks,
        "operator_docs": readme_checks,
        "dry_run_contract": build_dry_run(),
        "mastra_alignment": {
            "official_framework": "Mastra",
            "workflow_pattern": "createWorkflow/createStep",
            "hitl_pattern": "suspend/resume/bail",
            "source_links": [
                "https://mastra.ai/docs",
                "https://mastra.ai/docs/workflows/human-in-the-loop",
                "https://github.com/mastra-ai/mastra",
            ],
        },
        "distribution": {
            "report_path": relative_path(REPORT),
            "verification_command": "python3 scripts/verify_cognitive_loop_mastra_adapter.py --check",
            "safe_for_platform_agent_static_import": True,
        },
        "runtime_boundaries": {
            "mastra_runtime_started": False,
            "typescript_compiled_in_this_repo": False,
            "watcher_daemon_started": False,
            "realtime_html_console_started": False,
            "external_agent_called": False,
        },
        "privacy": {
            "raw_source_text_included": False,
            "diff_bodies_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
        },
    }
    assert_no_forbidden_text(dump_json(report), label="Mastra adapter verification report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    serialized = dump_json(build_report())
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop Mastra adapter report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Mastra adapter report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_mastra_adapter.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_cognitive_loop_mastra_adapter failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
