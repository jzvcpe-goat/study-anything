#!/usr/bin/env python3
"""Verify the marketplace-quality external Agent eval harness."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "external-eval-marketplace-harness-v1"
RELEASE_VERSION = "v0.3.31-alpha"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-external-eval-harness.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"

PLATFORM_IDS = ("codex", "kimi", "workbuddy")
EXPECTED_ADAPTERS = ("promptfoo", "deepeval", "langchain-agentevals", "ragas")
EXPECTED_TRAJECTORY = (
    "teach.overview",
    "teach.glossary",
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
)
REQUIRED_OPERATOR_ASSETS = [
    "docs/agent-eval.md",
    "docs/eval-frameworks.md",
    "docs/platform-agent-integrations.md",
    "docs/adoption.md",
    "evals/README.md",
    "evals/promptfoo/agent-eval-artifact.yaml",
    "evals/deepeval/study_anything_quality_eval.py",
    "evals/baselines/study-anything-agent-eval-baseline.json",
    "evals/fixtures/fake-agent-learning-loop.json",
    "evals/fixtures/mock-http-agent-learning-loop.json",
    "scripts/run_external_agent_evals.py",
    "scripts/verify_agent_eval_assets.py",
    "scripts/verify_agent_eval_baseline.py",
    "scripts/verify_external_agent_adapter_hardening.py",
    "scripts/verify_platform_ecosystem_eval_flow.py",
    "scripts/verify_external_eval_marketplace_harness.py",
    "platform/ecosystem-submission.json",
    "platform/study-anything-platform-tools.json",
    "platform/generated/study-anything-platform-openapi.json",
    "platform/generated/study-anything-openai-tools.json",
]
REQUIRED_PACK_COMMAND = "verify_external_eval_marketplace_harness.py --check"
REQUIRED_EVIDENCE = (
    "external_eval_marketplace_harness.schema_version == external-eval-marketplace-harness-v1"
)
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


class ExternalEvalHarnessError(RuntimeError):
    """Readable external-eval harness failure."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ExternalEvalHarnessError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExternalEvalHarnessError(f"JSON object expected: {path}")
    return value


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise ExternalEvalHarnessError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise ExternalEvalHarnessError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise ExternalEvalHarnessError(
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
        raise ExternalEvalHarnessError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise ExternalEvalHarnessError(f"Required external-eval asset is missing: {relative_path}")
    return target


def assert_contains(root: Path, relative_path: str, *needles: str) -> str:
    target = require_file(root, relative_path)
    text = target.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise ExternalEvalHarnessError(f"{relative_path} is missing required text: {missing}")
    return text


def sanitize_command(command: str) -> str:
    command = command.replace("http://127.0.0.1:8787/invoke", "${USER_OWNED_AGENT_ENDPOINT}")
    command = command.replace("http://127.0.0.1:8787", "${USER_OWNED_AGENT_ENDPOINT}")
    return re.sub(r"AGENT_ENDPOINT=\S+", "AGENT_ENDPOINT=${USER_OWNED_AGENT_ENDPOINT}", command)


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(safe_relative(root, "platform/ecosystem-submission.json"))
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise ExternalEvalHarnessError("Ecosystem submission schema drifted.")
    if submission.get("version") != RELEASE_VERSION:
        raise ExternalEvalHarnessError(f"Ecosystem submission version must be {RELEASE_VERSION}.")
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    required_assets = {
        "docs/eval-frameworks.md",
        "scripts/verify_external_eval_marketplace_harness.py",
        "platform/generated/study-anything-external-eval-harness.json",
    }
    missing_assets = required_assets - shared_assets
    if missing_assets:
        raise ExternalEvalHarnessError(f"Ecosystem submission missing eval assets: {sorted(missing_assets)}")
    command_text = "\n".join(str(item) for item in (submission.get("acceptance") or {}).get("minimum_commands", []))
    if REQUIRED_PACK_COMMAND not in command_text:
        raise ExternalEvalHarnessError("Ecosystem submission missing external eval harness check.")
    prove_text = "\n".join(str(item) for item in (submission.get("acceptance") or {}).get("must_prove", []))
    if SCHEMA_VERSION not in prove_text:
        raise ExternalEvalHarnessError("Ecosystem submission must prove external eval harness schema.")
    return {
        "schema_version": submission.get("schema_version"),
        "version": submission.get("version"),
        "platform_count": len(submission.get("submissions", [])),
        "no_frontend_required": (submission.get("project") or {}).get("standalone_frontend_required") is False,
    }


def validate_platform_pack(root: Path, platform_id: str) -> dict[str, Any]:
    pack = read_json(safe_relative(root, f"platform/packs/{platform_id}/pack.json"))
    if pack.get("schema_version") != "study-anything-platform-pack-v1":
        raise ExternalEvalHarnessError(f"{platform_id} pack schema drifted.")
    commands = [str(command) for command in pack.get("local_verification_commands", [])]
    if REQUIRED_PACK_COMMAND not in "\n".join(commands):
        raise ExternalEvalHarnessError(f"{platform_id} pack must include {REQUIRED_PACK_COMMAND}.")
    evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
    if REQUIRED_EVIDENCE not in evidence:
        raise ExternalEvalHarnessError(f"{platform_id} pack missing external eval harness evidence.")
    return {
        "platform_id": platform_id,
        "integration_mode": pack.get("integration_mode"),
        "commands": [sanitize_command(command) for command in commands if "eval" in command],
        "acceptance_evidence_count": len(evidence),
    }


def validate_eval_assets(root: Path) -> dict[str, Any]:
    assert_contains(
        root,
        "scripts/run_external_agent_evals.py",
        'choices=["promptfoo", "deepeval", "retrieval", "report"]',
        "promptfoo@",
        "ragas-compatible-native",
        "study-anything-native-maturity-report",
    )
    assert_contains(
        root,
        "scripts/verify_agent_eval_baseline.py",
        "study-anything-agent-eval-baseline-v1",
        "study-anything-agent-eval-regression-report-v1",
        "promptfoo",
        "deepeval",
        "langchain-agentevals",
        "ragas",
    )
    assert_contains(
        root,
        "evals/promptfoo/agent-eval-artifact.yaml",
        "/v1/sessions/{{sessionId}}/agent-eval/artifact",
        "agent_invocation_coverage",
        "quiz.generate",
        "answer.grade",
        "insight.synthesize",
    )
    assert_contains(
        root,
        "docs/eval-frameworks.md",
        "Promptfoo",
        "DeepEval",
        "LangChain AgentEvals",
        "Ragas",
        "optional",
        "Study Anything must not store judge or model keys",
    )

    baseline = read_json(safe_relative(root, "evals/baselines/study-anything-agent-eval-baseline.json"))
    if baseline.get("schema_version") != "study-anything-agent-eval-baseline-v1":
        raise ExternalEvalHarnessError("Agent eval baseline schema drifted.")
    if baseline.get("version") != RELEASE_VERSION:
        raise ExternalEvalHarnessError(f"Agent eval baseline version must be {RELEASE_VERSION}.")
    adapter_ids = baseline.get("scorecard", {}).get("adapter_ids", [])
    if set(adapter_ids) != set(EXPECTED_ADAPTERS):
        raise ExternalEvalHarnessError(f"Agent eval baseline adapter ids drifted: {adapter_ids}")

    fixtures = {}
    for name in ("fake-agent-learning-loop.json", "mock-http-agent-learning-loop.json"):
        path = f"evals/fixtures/{name}"
        fixture = read_json(safe_relative(root, path))
        if fixture.get("schema_version") != "study-anything-agent-eval-fixture-v1":
            raise ExternalEvalHarnessError(f"Fixture schema drifted: {path}")
        tasks = [
            str(item.get("task_type"))
            for item in fixture.get("agent_tasks", [])
            if isinstance(item, dict)
        ]
        if tuple(tasks) != EXPECTED_TRAJECTORY:
            raise ExternalEvalHarnessError(f"Fixture task trajectory drifted: {path}: {tasks}")
        if any(bool(value) for value in (fixture.get("privacy") or {}).values()):
            raise ExternalEvalHarnessError(f"Fixture privacy flags are unsafe: {path}")
        fixtures[name] = {
            "schema_version": fixture.get("schema_version"),
            "task_count": len(tasks),
            "privacy_flags_clear": True,
        }

    return {
        "adapter_ids": list(EXPECTED_ADAPTERS),
        "trajectory": list(EXPECTED_TRAJECTORY),
        "baseline_schema": baseline.get("schema_version"),
        "baseline_version": baseline.get("version"),
        "fixtures": fixtures,
    }


def native_gates() -> list[dict[str, Any]]:
    return [
        {
            "gate_id": "native_maturity_report",
            "required": True,
            "command": (
                "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
                "--tool report --create-session --required"
            ),
            "evidence_schema": "agent-eval-report-v1",
            "passes_without_judge_model": True,
        },
        {
            "gate_id": "asset_contract",
            "required": True,
            "command": "python3 scripts/verify_agent_eval_assets.py",
            "evidence_schema": "agent-eval-artifact-v1",
            "passes_without_judge_model": True,
        },
        {
            "gate_id": "baseline_regression",
            "required": True,
            "command": "python3 scripts/verify_agent_eval_baseline.py --check",
            "evidence_schema": "study-anything-agent-eval-regression-report-v1",
            "passes_without_judge_model": True,
        },
        {
            "gate_id": "external_agent_adapter_hardening",
            "required": True,
            "command": "python3 scripts/verify_external_agent_adapter_hardening.py",
            "evidence_schema": "external-agent-adapter-hardening-v1",
            "passes_without_judge_model": True,
        },
    ]


def external_adapters() -> list[dict[str, Any]]:
    return [
        {
            "adapter_id": "promptfoo",
            "mode": "optional_external_contract_gate",
            "command": (
                "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
                "--tool promptfoo --create-session"
            ),
            "required_command": (
                "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
                "--tool promptfoo --create-session --required"
            ),
            "timeout_seconds": 180,
            "missing_runtime_behavior": "skipped_when_optional",
            "credentials_stored_by_study_anything": False,
            "artifact": "evals/promptfoo/agent-eval-artifact.yaml",
        },
        {
            "adapter_id": "deepeval",
            "mode": "optional_external_or_native_quality_fallback",
            "command": (
                "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
                "--tool deepeval --create-session --allow-native-quality-fallback"
            ),
            "timeout_seconds": 180,
            "missing_runtime_behavior": "native_quality_fallback_when_allowed",
            "credentials_stored_by_study_anything": False,
            "artifact": "evals/deepeval/study_anything_quality_eval.py",
        },
        {
            "adapter_id": "langchain-agentevals",
            "mode": "trajectory_contract_export",
            "command": "Use agent_eval_artifact.trajectory with create_trajectory_match_evaluator.",
            "timeout_seconds": 180,
            "missing_runtime_behavior": "adapter_descriptor_only_until_operator_installs_runtime",
            "credentials_stored_by_study_anything": False,
            "artifact": "agent-eval-artifact-v1 trajectory field",
        },
        {
            "adapter_id": "ragas",
            "mode": "ragas_compatible_native_retrieval_gate",
            "command": (
                "STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 "
                "python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required"
            ),
            "timeout_seconds": 180,
            "missing_runtime_behavior": "native_retrieval_gate_first_full_ragas_later",
            "credentials_stored_by_study_anything": False,
            "artifact": "retrieval-quality-eval-v1",
        },
    ]


def sample_eval_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "fake_agent_baseline_loop",
            "fixture": "evals/fixtures/fake-agent-learning-loop.json",
            "purpose": "Fast deterministic invocation and privacy contract.",
            "expected": ["agent-eval-artifact-v1", "agent-eval-report-v1"],
        },
        {
            "case_id": "mock_http_agent_loop",
            "fixture": "evals/fixtures/mock-http-agent-learning-loop.json",
            "purpose": "User-owned HTTP Agent evidence separated from fake-agent evidence.",
            "expected": ["agent-audit-v1", "external-agent-adapter-hardening-v1"],
        },
        {
            "case_id": "retrieval_grounding_gate",
            "fixture": "scripts/verify_platform_ecosystem_eval_flow.py",
            "purpose": "Ragas-compatible retrieval/context quality without raw snippets in eval evidence.",
            "expected": ["retrieval-quality-eval-v1"],
        },
        {
            "case_id": "marketplace_submission_pack",
            "fixture": "platform/ecosystem-submission.json",
            "purpose": "Kimi/Codex/WorkBuddy submission assets include eval evidence and commands.",
            "expected": ["external-eval-marketplace-harness-v1"],
        },
    ]


def assert_no_leaks(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise ExternalEvalHarnessError(f"External eval harness leaked private data: {leaks}")


def build_report(root: Path) -> dict[str, Any]:
    running_from_adoption_pack = safe_relative(root, "manifest.json").is_file()
    for path in REQUIRED_OPERATOR_ASSETS:
        require_file(root, path)
    if not running_from_adoption_pack:
        require_file(root, "platform/generated/study-anything-platform-adoption-pack.json")
    eval_assets = validate_eval_assets(root)
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "marketplace_quality_goal": (
            "Give external platform Agents a copyable, redacted eval contract before any "
            "marketplace or ecosystem submission claims production readiness."
        ),
        "submission": validate_submission(root),
        "platforms": {
            platform_id: validate_platform_pack(root, platform_id)
            for platform_id in PLATFORM_IDS
        },
        "eval_assets": eval_assets,
        "native_fast_gates": native_gates(),
        "external_adapters": external_adapters(),
        "sample_eval_cases": sample_eval_cases(),
        "expected_evidence_schema": {
            "schema_version": "external-eval-marketplace-harness-evidence-v1",
            "required_fields": [
                "status",
                "native_fast_gate",
                "baseline_regression",
                "adapter_results",
                "privacy",
                "artifact_paths",
            ],
            "required_statuses": ["pass", "skipped_optional"],
        },
        "artifact_import_export": {
            "source_report": "platform/generated/study-anything-external-eval-harness.json",
            "adoption_pack": "platform/generated/study-anything-platform-adoption-pack.zip",
            "operator_docs": ["docs/agent-eval.md", "docs/eval-frameworks.md"],
            "copyable_commands": [
                "python3 scripts/verify_external_eval_marketplace_harness.py --check",
                "python3 scripts/verify_agent_eval_assets.py",
                "python3 scripts/verify_agent_eval_baseline.py --check",
                (
                    "API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py "
                    "--tool report --create-session --required"
                ),
            ],
        },
        "timeout_policy": {
            "default_external_eval_timeout_seconds": 180,
            "platform_ecosystem_eval_timeout_seconds": 60,
            "optional_adapter_timeout_result": "skipped_when_optional_not_failed",
            "required_adapter_timeout_result": "failed",
        },
        "privacy_assertions": {
            "real_model_or_judge_keys_stored_by_study_anything": False,
            "raw_source_text_in_eval_harness": False,
            "learner_answers_in_eval_harness": False,
            "agent_endpoint_secrets_in_eval_harness": False,
            "raw_agent_metadata_in_eval_harness": False,
            "browser_video_private_context_in_eval_harness": False,
            "report_is_redacted": True,
        },
        "failure_remediation": {
            "native_gate_failed": [
                "Run verify_agent_eval_assets.py and verify_agent_eval_baseline.py --check first.",
                "Use fake deterministic Agent to isolate Study Anything runtime regressions.",
            ],
            "optional_adapter_missing": [
                "Install the external runtime in the operator eval environment.",
                "Keep the native fast gate as the release blocker until the optional adapter is required.",
            ],
            "promptfoo_timeout": [
                "Increase --timeout-seconds or prewarm npx promptfoo package installation.",
                "Treat timeout as skipped only when the adapter is optional.",
            ],
            "privacy_leak": [
                "Stop release, inspect the offending artifact, and remove raw source, answer, endpoint, or key material.",
                "Share only schema/status/hash/reference evidence in ecosystem submissions.",
            ],
        },
    }
    assert_no_leaks(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", help="Optional adoption-pack zip to validate.")
    parser.add_argument("--pack-root", help="Optional unpacked adoption-pack or repo root.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    tmp_root = Path(tempfile.mkdtemp(prefix="study-anything-external-eval-harness-"))
    try:
        root = resolve_pack_root(args, tmp_root)
        payload = build_report(root)
        text = dump_json(payload)
        output = Path(args.output)
        if args.check:
            if not output.exists():
                raise ExternalEvalHarnessError(f"External eval harness report missing: {output}")
            if output.read_text(encoding="utf-8") != text:
                raise ExternalEvalHarnessError(
                    "External eval marketplace harness is stale. Run "
                    "`python3 scripts/verify_external_eval_marketplace_harness.py --write`."
                )
            print("ok    external eval marketplace harness is up to date")
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
        print(f"verify_external_eval_marketplace_harness failed: {exc}", file=sys.stderr)
        sys.exit(1)
