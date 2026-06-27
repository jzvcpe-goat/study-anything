#!/usr/bin/env python3
"""Verify Agent eval marketplace enforcement and external judge boundaries."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "agent-eval-marketplace-enforcement-v1"
RELEASE_VERSION = "v0.3.31-alpha"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-agent-eval-marketplace-enforcement.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
PLATFORM_IDS = ("codex", "kimi", "workbuddy")
EXPECTED_ADAPTERS = ("promptfoo", "deepeval", "langchain-agentevals", "ragas")
REQUIRED_PACK_COMMAND = "verify_agent_eval_marketplace_enforcement.py --check"
REQUIRED_EVIDENCE = (
    "agent_eval_marketplace_enforcement.schema_version == agent-eval-marketplace-enforcement-v1"
)
REQUIRED_ASSETS = [
    "docs/agent-eval.md",
    "docs/eval-frameworks.md",
    "docs/platform-agent-integrations.md",
    "docs/adoption.md",
    "evals/README.md",
    "evals/promptfoo/agent-eval-artifact.yaml",
    "evals/deepeval/study_anything_quality_eval.py",
    "evals/baselines/study-anything-agent-eval-baseline.json",
    "scripts/run_external_agent_evals.py",
    "scripts/verify_agent_eval_assets.py",
    "scripts/verify_agent_eval_baseline.py",
    "scripts/verify_external_eval_marketplace_harness.py",
    "platform/ecosystem-submission.json",
    "platform/generated/study-anything-external-eval-harness.json",
]
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
]
FORBIDDEN_LITERALS = [
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "Private answer:",
    "Private platform browser/video context",
    "Baseline source text",
    "Baseline answer text",
    "raw source text returned",
    "learner@example.com",
]


class AgentEvalMarketplaceEnforcementError(RuntimeError):
    """Readable Agent eval marketplace enforcement failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AgentEvalMarketplaceEnforcementError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AgentEvalMarketplaceEnforcementError(f"JSON object expected: {path}")
    return value


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise AgentEvalMarketplaceEnforcementError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise AgentEvalMarketplaceEnforcementError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise AgentEvalMarketplaceEnforcementError(
                    f"Adoption pack archive should have one root, got {sorted(roots)}"
                )
            archive.extractall(tmp_root)
        return tmp_root / next(iter(roots))
    return ROOT


def safe_relative(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise AgentEvalMarketplaceEnforcementError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise AgentEvalMarketplaceEnforcementError(f"Required Agent eval enforcement asset is missing: {relative_path}")
    return target


def assert_contains(root: Path, relative_path: str, *needles: str) -> str:
    text = require_file(root, relative_path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise AgentEvalMarketplaceEnforcementError(f"{relative_path} is missing required text: {missing}")
    return text


def assert_no_leaks(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise AgentEvalMarketplaceEnforcementError(f"Agent eval marketplace enforcement leaked private data: {leaks}")


def validate_runner_contract(root: Path) -> dict[str, Any]:
    runner = assert_contains(
        root,
        "scripts/run_external_agent_evals.py",
        'choices=["promptfoo", "deepeval", "retrieval", "report"]',
        "--required",
        "--timeout-seconds",
        "args.required and result[\"status\"] != \"ok\"",
        "Promptfoo did not finish within",
        "npx is not available",
        "Could not parse DeepEval adapter output",
        "Could not parse retrieval eval output",
        "Could not parse Agent eval report output",
    )
    return {
        "required_flag_blocks_non_ok": "args.required and result[\"status\"] != \"ok\"" in runner,
        "timeout_flag_present": "--timeout-seconds" in runner,
        "missing_runtime_diagnostic_present": "npx is not available" in runner,
        "malformed_output_diagnostics": [
            "deepeval_parse_error",
            "retrieval_parse_error",
            "agent_eval_report_parse_error",
        ],
    }


def validate_baseline_and_harness(root: Path) -> dict[str, Any]:
    baseline = read_json(safe_relative(root, "evals/baselines/study-anything-agent-eval-baseline.json"))
    harness = read_json(safe_relative(root, "platform/generated/study-anything-external-eval-harness.json"))
    if baseline.get("version") != RELEASE_VERSION:
        raise AgentEvalMarketplaceEnforcementError(f"Agent eval baseline version must be {RELEASE_VERSION}.")
    if harness.get("version") != RELEASE_VERSION:
        raise AgentEvalMarketplaceEnforcementError(f"External eval harness version must be {RELEASE_VERSION}.")
    adapters = set((baseline.get("scorecard") or {}).get("adapter_ids") or [])
    if adapters != set(EXPECTED_ADAPTERS):
        raise AgentEvalMarketplaceEnforcementError(f"Baseline adapter inventory drifted: {sorted(adapters)}")
    if harness.get("schema_version") != "external-eval-marketplace-harness-v1":
        raise AgentEvalMarketplaceEnforcementError("External eval harness schema drifted.")
    return {
        "baseline_schema": baseline.get("schema_version"),
        "baseline_version": baseline.get("version"),
        "baseline_status": baseline.get("status"),
        "harness_schema": harness.get("schema_version"),
        "harness_status": harness.get("status"),
        "adapter_ids": sorted(adapters),
    }


def promptfoo_missing_runtime_probe(root: Path) -> dict[str, Any]:
    script = safe_relative(root, "scripts/run_external_agent_evals.py")
    if root.resolve() != ROOT.resolve():
        return {
            "optional_status": "not_run_against_pack",
            "required_exit_nonzero": True,
            "reason": "Runtime probe runs only from the source tree; pack mode validates the committed report.",
        }
    with tempfile.TemporaryDirectory(prefix="study-anything-no-npx-") as tmp:
        env = os.environ.copy()
        env["PATH"] = tmp
        base_command = [
            sys.executable,
            str(script),
            "--tool",
            "promptfoo",
            "--api-base",
            "http://127.0.0.1:9",
            "--session-id",
            "session-diagnostic-only",
            "--timeout-seconds",
            "1",
        ]
        optional = subprocess.run(
            base_command,
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        required = subprocess.run(
            [*base_command, "--required"],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
    try:
        optional_payload = json.loads(optional.stdout)
        required_payload = json.loads(required.stdout)
    except json.JSONDecodeError as exc:
        raise AgentEvalMarketplaceEnforcementError(
            f"Could not parse promptfoo missing-runtime probe: {optional.stdout} {required.stdout}"
        ) from exc
    if optional.returncode != 0 or optional_payload.get("status") != "skipped":
        raise AgentEvalMarketplaceEnforcementError(f"Optional missing Promptfoo runtime should be skipped: {optional_payload}")
    if required.returncode == 0 or required_payload.get("status") != "skipped":
        raise AgentEvalMarketplaceEnforcementError(f"Required missing Promptfoo runtime should fail: {required_payload}")
    return {
        "adapter_id": "promptfoo",
        "missing_runtime_reason": optional_payload.get("reason"),
        "optional_status": optional_payload.get("status"),
        "optional_exit_code": optional.returncode,
        "required_status": required_payload.get("status"),
        "required_exit_nonzero": required.returncode != 0,
        "redacted": True,
    }


def external_judge_contracts() -> list[dict[str, Any]]:
    return [
        {
            "adapter_id": "promptfoo",
            "external_project": "promptfoo",
            "required_command": (
                "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
                "--tool promptfoo --create-session --required"
            ),
            "optional_command": (
                "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
                "--tool promptfoo --create-session"
            ),
            "missing_runtime_optional_result": "skipped",
            "missing_runtime_required_result": "failed_exit",
            "credentials_stored_by_study_anything": False,
        },
        {
            "adapter_id": "deepeval",
            "external_project": "deepeval",
            "required_command": (
                "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
                "--tool deepeval --create-session --required"
            ),
            "optional_command": (
                "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
                "--tool deepeval --create-session --allow-native-quality-fallback"
            ),
            "missing_runtime_optional_result": "native_quality_fallback_when_allowed",
            "missing_runtime_required_result": "failed_exit_unless_deepeval_installed",
            "credentials_stored_by_study_anything": False,
        },
        {
            "adapter_id": "langchain-agentevals",
            "external_project": "langchain-ai/agentevals",
            "required_command": "Operator runs trajectory match outside Study Anything using agent-eval-artifact-v1.",
            "optional_command": "Export agent-eval-artifact-v1 trajectory and expected task sequence.",
            "missing_runtime_optional_result": "descriptor_only",
            "missing_runtime_required_result": "operator_environment_failure",
            "credentials_stored_by_study_anything": False,
        },
        {
            "adapter_id": "ragas",
            "external_project": "ragas",
            "required_command": (
                "STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 "
                "python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required"
            ),
            "optional_command": "Use retrieval-quality-eval-v1 as the redacted Ragas-compatible input.",
            "missing_runtime_optional_result": "native_retrieval_gate_available",
            "missing_runtime_required_result": "failed_exit_if_retrieval_gate_fails",
            "credentials_stored_by_study_anything": False,
        },
    ]


def validate_docs(root: Path) -> dict[str, Any]:
    checked = {
        "docs/agent-eval.md": [
            "Agent Eval Marketplace Enforcement",
            "agent-eval-marketplace-enforcement-v1",
            "optional",
            "required",
        ],
        "docs/platform-agent-integrations.md": [
            "agent-eval-marketplace-enforcement-v1",
            "external judge",
        ],
        "docs/adoption.md": [
            "verify_agent_eval_marketplace_enforcement.py --check",
            "agent-eval-marketplace-enforcement-v1",
        ],
    }
    for path, needles in checked.items():
        assert_contains(root, path, *needles)
    return {"checked_docs": sorted(checked), "external_judge_keys_stay_outside": True}


def validate_platform_packs(root: Path) -> dict[str, Any]:
    platforms: dict[str, Any] = {}
    for platform_id in PLATFORM_IDS:
        pack = read_json(safe_relative(root, f"platform/packs/{platform_id}/pack.json"))
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        if REQUIRED_PACK_COMMAND not in commands:
            raise AgentEvalMarketplaceEnforcementError(f"{platform_id} pack missing enforcement command.")
        if REQUIRED_EVIDENCE not in evidence:
            raise AgentEvalMarketplaceEnforcementError(f"{platform_id} pack missing enforcement evidence.")
        platforms[platform_id] = {
            "integration_mode": pack.get("integration_mode"),
            "command_declared": True,
            "acceptance_evidence_declared": True,
        }
    return platforms


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(safe_relative(root, "platform/ecosystem-submission.json"))
    if submission.get("version") != RELEASE_VERSION:
        raise AgentEvalMarketplaceEnforcementError(f"Ecosystem submission version must be {RELEASE_VERSION}.")
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    required_assets = {
        "scripts/verify_agent_eval_marketplace_enforcement.py",
        "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
        "docs/agent-eval.md",
        "docs/eval-frameworks.md",
    }
    missing = required_assets - shared_assets
    if missing:
        raise AgentEvalMarketplaceEnforcementError(f"Ecosystem submission missing enforcement assets: {sorted(missing)}")
    acceptance = submission.get("acceptance") or {}
    commands = "\n".join(str(item) for item in acceptance.get("minimum_commands", []))
    must_prove = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    if REQUIRED_PACK_COMMAND not in commands:
        raise AgentEvalMarketplaceEnforcementError("Ecosystem submission missing enforcement command.")
    if SCHEMA_VERSION not in must_prove:
        raise AgentEvalMarketplaceEnforcementError("Ecosystem submission must prove enforcement schema.")
    return {
        "schema_version": submission.get("schema_version"),
        "version": submission.get("version"),
        "shared_assets_included": len(required_assets),
        "submission_count": len(submission.get("submissions", [])),
    }


def validate_adoption_pack(root: Path) -> dict[str, Any]:
    manifest_path = safe_relative(root, "platform/generated/study-anything-platform-adoption-pack.json")
    if not manifest_path.is_file() and safe_relative(root, "manifest.json").is_file():
        manifest_path = safe_relative(root, "manifest.json")
    if not manifest_path.is_file():
        return {"included": False, "reason": "manifest_not_generated_yet"}
    manifest = read_json(manifest_path)
    if manifest.get("version") != RELEASE_VERSION:
        return {
            "included": False,
            "reason": "manifest_version_mismatch",
            "found_version": manifest.get("version"),
            "expected_version": RELEASE_VERSION,
        }
    paths = {str(item.get("path")) for item in manifest.get("files", []) if isinstance(item, dict)}
    required = {
        "scripts/verify_agent_eval_marketplace_enforcement.py",
        "platform/generated/study-anything-agent-eval-marketplace-enforcement.json",
        "docs/release-notes/v0.3.31-alpha.md",
    }
    missing = required - paths
    if missing:
        return {"included": False, "missing": sorted(missing)}
    must_verify = set(str(item) for item in (manifest.get("acceptance") or {}).get("must_verify", []))
    if SCHEMA_VERSION not in must_verify:
        return {"included": False, "missing": [SCHEMA_VERSION]}
    return {
        "included": True,
        "schema_version": manifest.get("schema_version"),
        "version": manifest.get("version"),
        "enforcement_assets_included": len(required),
    }


def build_report(root: Path) -> dict[str, Any]:
    for path in REQUIRED_ASSETS:
        require_file(root, path)
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "purpose": (
            "Make external judge usage enforceable for ecosystem submissions while keeping native "
            "Study Anything gates local-first and keeping model or judge keys outside Study Anything."
        ),
        "runner_contract": validate_runner_contract(root),
        "baseline_and_harness": validate_baseline_and_harness(root),
        "runtime_diagnostics": {
            "promptfoo_missing_runtime": promptfoo_missing_runtime_probe(root),
            "malformed_judge_output": [
                "deepeval_parse_error",
                "retrieval_parse_error",
                "agent_eval_report_parse_error",
            ],
            "timeout_policy": {
                "optional_external_timeout_result": "skipped",
                "required_external_timeout_result": "failed_exit",
                "default_timeout_seconds": 180,
            },
        },
        "external_judge_contracts": external_judge_contracts(),
        "docs": validate_docs(root),
        "platform_packs": validate_platform_packs(root),
        "ecosystem_submission": validate_submission(root),
        "adoption_pack": validate_adoption_pack(root),
        "privacy_assertions": {
            "real_model_or_judge_keys_stored_by_study_anything": False,
            "judge_api_keys_in_report": False,
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "browser_video_private_context_in_report": False,
            "report_is_redacted": True,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_agent_eval_marketplace_enforcement.py --check",
            "pack_command": (
                "python3 scripts/verify_agent_eval_marketplace_enforcement.py "
                "--pack platform/generated/study-anything-platform-adoption-pack.zip"
            ),
            "release_gate": "scripts/release_check.sh",
        },
    }
    assert_no_leaks(report)
    return report


def check_report(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        raise AgentEvalMarketplaceEnforcementError(f"Agent eval enforcement report missing: {path}")
    expected = dump_json(payload)
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        raise AgentEvalMarketplaceEnforcementError(
            "Agent eval marketplace enforcement report is stale. Run "
            "`python3 scripts/verify_agent_eval_marketplace_enforcement.py --write`."
        )
    adoption = payload.get("adoption_pack") or {}
    if adoption.get("included") is not True:
        raise AgentEvalMarketplaceEnforcementError(f"Adoption pack missing enforcement evidence: {adoption}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=None, help="Validate a platform adoption pack zip.")
    parser.add_argument("--pack-root", default=None, help="Validate an extracted adoption pack root.")
    parser.add_argument("--write", action="store_true", help="Write the generated report.")
    parser.add_argument("--check", action="store_true", help="Require the generated report to be current.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report output path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-anything-agent-eval-enforcement-") as tmp:
        root = resolve_pack_root(args, Path(tmp))
        if root.resolve() != ROOT.resolve():
            require_file(root, "scripts/verify_agent_eval_marketplace_enforcement.py")
            require_file(root, "platform/generated/study-anything-agent-eval-marketplace-enforcement.json")
        report = build_report(root)

    output = Path(args.output)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(dump_json(report), encoding="utf-8")
    if args.check:
        check_report(output, report)
    print(dump_json(report), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_agent_eval_marketplace_enforcement failed: {exc}", file=sys.stderr)
        sys.exit(1)
