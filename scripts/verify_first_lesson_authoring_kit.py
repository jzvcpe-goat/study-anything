#!/usr/bin/env python3
"""Verify the copyable first-run lesson authoring kit for platform Agents."""

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
SCHEMA_VERSION = "first-run-lesson-authoring-kit-v1"
RELEASE_VERSION = "v0.3.17-alpha"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-first-lesson-authoring-kit.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"

PLATFORM_IDS = ("codex", "kimi", "workbuddy")
REQUIRED_TOOLS = [
    "study_anything_health",
    "study_anything_validate_context_package",
    "study_anything_create_session_from_context_package",
    "study_anything_add_enrichment",
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
    "study_anything_enrichment_artifact_export",
    "study_anything_learning_package_export",
    "study_anything_second_brain_handoff_export",
]
REQUIRED_OPERATOR_ASSETS = [
    "platform/ecosystem-submission.json",
    "platform/study-anything-platform-tools.json",
    "platform/generated/study-anything-platform-openapi.json",
    "platform/generated/study-anything-openai-tools.json",
    "platform/generated/study-anything-tool-catalog.md",
    "docs/use-with-kimi.md",
    "docs/platform-agent-integrations.md",
    "docs/adoption.md",
    "docs/ecosystem-submission.md",
    "docs/second-brain-handoff.md",
    "docs/notebooklm-bridge.md",
    "scripts/study_anything_cli.py",
    "scripts/verify_platform_lesson_flow.py",
    "scripts/verify_importer_lesson_flow.py",
    "scripts/verify_first_lesson_authoring_kit.py",
]
REQUIRED_PACK_COMMAND = "verify_first_lesson_authoring_kit.py --check"
REQUIRED_EVIDENCE = (
    "first_lesson_authoring_kit.schema_version == first-run-lesson-authoring-kit-v1"
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
    "raw source text returned",
    "learner@example.com",
]


class FirstLessonAuthoringKitError(RuntimeError):
    """Readable first-lesson authoring-kit failure."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FirstLessonAuthoringKitError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FirstLessonAuthoringKitError(f"JSON object expected: {path}")
    return value


def read_json_any(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FirstLessonAuthoringKitError(f"Cannot read JSON {path}: {exc}") from exc


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise FirstLessonAuthoringKitError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise FirstLessonAuthoringKitError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise FirstLessonAuthoringKitError(
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
        raise FirstLessonAuthoringKitError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> None:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise FirstLessonAuthoringKitError(f"Required first-lesson asset is missing: {relative_path}")


def operation_ids(openapi: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for methods in openapi.get("paths", {}).values():
        if not isinstance(methods, dict):
            continue
        for operation in methods.values():
            if isinstance(operation, dict) and operation.get("operationId"):
                found.add(str(operation["operationId"]))
    return found


def validate_tool_assets(root: Path) -> dict[str, Any]:
    manifest = read_json(safe_relative(root, "platform/study-anything-platform-tools.json"))
    manifest_names = {
        str(tool.get("name"))
        for tool in manifest.get("tools", [])
        if isinstance(tool, dict) and tool.get("name")
    }
    openai_tools = read_json_any(safe_relative(root, "platform/generated/study-anything-openai-tools.json"))
    openapi = read_json(safe_relative(root, "platform/generated/study-anything-platform-openapi.json"))
    if not isinstance(openai_tools, list):
        raise FirstLessonAuthoringKitError("OpenAI-compatible tool asset must be a list.")
    openai_names = {
        str(item.get("function", {}).get("name"))
        for item in openai_tools
        if isinstance(item, dict)
    }
    openapi_names = operation_ids(openapi)
    missing = sorted(set(REQUIRED_TOOLS) - manifest_names - openai_names - openapi_names)
    if missing:
        raise FirstLessonAuthoringKitError(f"First lesson required tools are missing: {missing}")
    return {
        "required_tool_count": len(REQUIRED_TOOLS),
        "openai_tool_count": len(openai_tools),
        "openapi_path_count": len(openapi.get("paths", {})),
        "required_tools_present": REQUIRED_TOOLS,
    }


def sanitize_command(command: str) -> str:
    sanitized = command.replace("http://127.0.0.1:8787/invoke", "${USER_OWNED_AGENT_ENDPOINT}")
    sanitized = sanitized.replace("http://127.0.0.1:8787", "${USER_OWNED_AGENT_ENDPOINT}")
    sanitized = re.sub(r"AGENT_ENDPOINT=\S+", "AGENT_ENDPOINT=${USER_OWNED_AGENT_ENDPOINT}", sanitized)
    return sanitized


def validate_platform_pack(root: Path, platform_id: str) -> dict[str, Any]:
    pack = read_json(safe_relative(root, f"platform/packs/{platform_id}/pack.json"))
    if pack.get("schema_version") != "study-anything-platform-pack-v1":
        raise FirstLessonAuthoringKitError(f"{platform_id} pack schema drifted.")
    commands = [str(command) for command in pack.get("local_verification_commands", [])]
    if REQUIRED_PACK_COMMAND not in "\n".join(commands):
        raise FirstLessonAuthoringKitError(f"{platform_id} pack must include {REQUIRED_PACK_COMMAND}.")
    evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
    if REQUIRED_EVIDENCE not in evidence:
        raise FirstLessonAuthoringKitError(f"{platform_id} pack is missing first-lesson kit evidence.")
    return {
        "platform_id": platform_id,
        "integration_mode": pack.get("integration_mode"),
        "entrypoints": pack.get("entrypoints", {}),
        "commands": [sanitize_command(command) for command in commands],
        "acceptance_evidence_count": len(evidence),
    }


def validate_submission(root: Path) -> dict[str, Any]:
    submission = read_json(safe_relative(root, "platform/ecosystem-submission.json"))
    if submission.get("schema_version") != "ecosystem-submission-v1":
        raise FirstLessonAuthoringKitError("Ecosystem submission schema drifted.")
    if submission.get("version") != RELEASE_VERSION:
        raise FirstLessonAuthoringKitError(
            f"Ecosystem submission version must be {RELEASE_VERSION}."
        )
    shared_assets = set(str(item) for item in submission.get("shared_assets", []))
    for asset in (
        "scripts/verify_first_lesson_authoring_kit.py",
        "platform/generated/study-anything-first-lesson-authoring-kit.json",
    ):
        if asset not in shared_assets:
            raise FirstLessonAuthoringKitError(f"Ecosystem submission missing shared asset {asset}.")
    acceptance = submission.get("acceptance") or {}
    command_text = "\n".join(str(item) for item in acceptance.get("minimum_commands", []))
    if REQUIRED_PACK_COMMAND not in command_text:
        raise FirstLessonAuthoringKitError("Ecosystem submission missing first-lesson kit check.")
    prove_text = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    if SCHEMA_VERSION not in prove_text:
        raise FirstLessonAuthoringKitError("Ecosystem submission must prove first-lesson kit schema.")
    return {
        "schema_version": submission.get("schema_version"),
        "version": submission.get("version"),
        "platform_count": len(submission.get("submissions", [])),
        "no_frontend_required": (submission.get("project") or {}).get(
            "standalone_frontend_required"
        )
        is False,
    }


def context_package_template() -> dict[str, Any]:
    return {
        "schema_version": "learning-context-package-v1",
        "title": "${LEARNING_TOPIC}",
        "learner_goal": "${WHAT_THE_USER_WANTS_TO_UNDERSTAND_OR_DO}",
        "source_items": [
            {
                "source_type": "document",
                "reference": "${USER_OWNED_SOURCE_REFERENCE}",
                "excerpt": "${BOUNDED_EXCERPT_OR_SUMMARY_200_TO_800_WORDS}",
                "why_it_matters": "${WHY_THIS_SOURCE_IS_RELEVANT}",
            },
            {
                "source_type": "app_context",
                "reference": "${OPTIONAL_BROWSER_APP_OR_VIDEO_SLICE_REFERENCE}",
                "excerpt": "${OPTIONAL_REDACTED_CONTEXT_SUMMARY}",
                "why_it_matters": "${OPTIONAL_CONTEXT_ROLE}",
            },
        ],
        "constraints": {
            "language": "${zh_or_en}",
            "avoid": ["raw credentials", "private browser traces", "unbounded source dumps"],
            "preferred_outputs": [
                "source-bound quiz",
                "professional term explanation",
                "Obsidian note",
                "NotebookLM-style learning package",
            ],
        },
    }


def copyable_prompts() -> dict[str, dict[str, str]]:
    return {
        "zh": {
            "title": "Study Anything 第一课启动提示词",
            "prompt": (
                "你是我的平台 Agent。请不要把真实模型密钥、浏览器私有上下文或完整原文写入 Study Anything。"
                "先根据我给出的材料生成 learning-context-package-v1，然后调用 Study Anything 工具完成第一课："
                "1. 检查 /v1/health；2. validate context package；3. create session from context package；"
                "4. add enrichment（如有网页、视频切片、Obsidian 笔记或应用上下文）；5. run 学习流；"
                "6. 让我回答 quiz；7. submit answers；8. 获取 mastery、agent audit、eval artifact；"
                "9. 导出 enrichment artifact、learning package、Obsidian note 和 second-brain handoff。"
                "最后只汇报 schema、session_id、掌握度、引用来源和本地证据路径。"
            ),
        },
        "en": {
            "title": "Study Anything first lesson kickoff prompt",
            "prompt": (
                "You are my platform Agent. Do not send real model secrets, private browser context, "
                "or full raw source dumps into Study Anything. Build a learning-context-package-v1 from "
                "the bounded material I provide, then call Study Anything tools to complete the first lesson: "
                "health check, validate context package, create session, add enrichment if available, run the "
                "learning workflow, ask me for quiz answers, submit answers, fetch mastery/audit/eval evidence, "
                "and export the enrichment artifact, learning package, Obsidian note, and second-brain handoff. "
                "Report only schemas, session_id, mastery, cited references, and local evidence paths."
            ),
        },
    }


def operator_checklist() -> list[dict[str, Any]]:
    return [
        {
            "step_id": "collect_bounded_material",
            "operator_action": "Collect a bounded excerpt, file summary, video slice summary, or app-context summary outside Study Anything.",
            "expected_output": "learning-context-package-v1 draft with references and bounded excerpts",
        },
        {
            "step_id": "start_local_runtime",
            "operator_action": "Start Skill Mode or Docker Compose and verify health.",
            "expected_output": "GET /v1/health returns ok and version matches the pack",
        },
        {
            "step_id": "configure_optional_http_agent",
            "operator_action": "If using a real model, configure the user's own local/private HTTP Agent endpoint.",
            "expected_output": "Agent capabilities include quiz.generate, answer.grade, insight.synthesize",
        },
        {
            "step_id": "run_source_bound_lesson",
            "operator_action": "Create a session from the context package, run the learning flow, and submit answers.",
            "expected_output": "mastery, audit, eval, and source-bound citations are available",
        },
        {
            "step_id": "export_memory_evidence",
            "operator_action": "Export Obsidian, NotebookLM-style learning package, and second-brain handoff evidence.",
            "expected_output": "redacted schemas are present; raw source and learner answers stay local/user-owned",
        },
    ]


def tool_call_sequence() -> list[dict[str, str]]:
    return [
        {"order": "01", "tool": "study_anything_health", "expected_schema": "health response"},
        {
            "order": "02",
            "tool": "study_anything_validate_context_package",
            "expected_schema": "learning-context-package-v1",
        },
        {
            "order": "03",
            "tool": "study_anything_create_session_from_context_package",
            "expected_schema": "learning-context-package-v1",
        },
        {
            "order": "04",
            "tool": "study_anything_add_enrichment",
            "expected_schema": "learning-enrichment-item-v1",
        },
        {"order": "05", "tool": "study_anything_run", "expected_schema": "session event stream"},
        {"order": "06", "tool": "study_anything_answer", "expected_schema": "graded answer result"},
        {"order": "07", "tool": "study_anything_mastery", "expected_schema": "mastery response"},
        {"order": "08", "tool": "study_anything_agent_audit", "expected_schema": "agent-audit-v1"},
        {
            "order": "09",
            "tool": "study_anything_agent_eval_artifact",
            "expected_schema": "agent-eval-artifact-v1",
        },
        {
            "order": "10",
            "tool": "study_anything_enrichment_artifact_export",
            "expected_schema": "learning-enrichment-artifact-v1",
        },
        {
            "order": "11",
            "tool": "study_anything_learning_package_export",
            "expected_schema": "learning-package-v1",
        },
        {
            "order": "12",
            "tool": "study_anything_second_brain_handoff_export",
            "expected_schema": "second-brain-handoff-v1",
        },
    ]


def assert_no_leaks(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise FirstLessonAuthoringKitError(f"First lesson authoring kit leaked private data: {leaks}")


def build_report(root: Path) -> dict[str, Any]:
    running_from_adoption_pack = safe_relative(root, "manifest.json").is_file()
    for path in REQUIRED_OPERATOR_ASSETS:
        require_file(root, path)
    if not running_from_adoption_pack:
        require_file(root, "platform/generated/study-anything-platform-adoption-pack.json")
    tool_assets = validate_tool_assets(root)
    sequence = tool_call_sequence()
    sequence_tools = [step["tool"] for step in sequence]
    if sequence_tools != REQUIRED_TOOLS:
        raise FirstLessonAuthoringKitError("First lesson tool sequence drifted from required tools.")
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "submission": validate_submission(root),
        "platforms": {
            platform_id: validate_platform_pack(root, platform_id)
            for platform_id in PLATFORM_IDS
        },
        "tool_assets": tool_assets,
        "copyable_prompts": copyable_prompts(),
        "operator_checklist": operator_checklist(),
        "tool_call_sequence": sequence,
        "context_package_template": context_package_template(),
        "http_agent_setup": {
            "recommended_mode": "user_owned_http_agent",
            "gateway_command": "python3 scripts/openai_compatible_agent_gateway.py --dry-run --port ${AGENT_PORT}",
            "register_command": (
                "python3 scripts/study_anything_cli.py agent-add-http "
                "--endpoint ${USER_OWNED_AGENT_ENDPOINT} --set-default"
            ),
            "credentials_boundary": "Credentials stay in the user's Agent or host platform environment.",
        },
        "expected_outputs": [
            "learning-context-package-v1",
            "learning-enrichment-artifact-v1",
            "agent-audit-v1",
            "agent-eval-artifact-v1",
            "mastery response",
            "obsidian-markdown-export-v1",
            "learning-package-v1",
            "second-brain-handoff-v1",
        ],
        "evidence_export_paths": [
            "platform/generated/study-anything-first-lesson-authoring-kit.json",
            "platform/generated/study-anything-platform-manual-submission-rehearsal.json",
            "platform/generated/study-anything-operator-drill-transcript.json",
            "platform/generated/study-anything-platform-adoption-pack.json",
        ],
        "failure_remediation": {
            "platform_cannot_call_localhost": [
                "Use a terminal-capable Agent, local gateway, or private HTTP tool host.",
                "Browser-only chat can follow the copy-only prompt but cannot run the local tools directly.",
            ],
            "agent_output_invalid": [
                "Run verify_external_agent_adapter_hardening.py.",
                "Fallback to fake deterministic Agent to isolate Study Anything runtime issues.",
            ],
            "context_package_invalid": [
                "Keep excerpts bounded and references explicit.",
                "Do not include secrets, cookies, signed URLs, or private browser traces.",
            ],
            "exports_too_sensitive": [
                "Share only schema/version/status evidence.",
                "Keep Obsidian and learning-package contents in the user's local vault/archive.",
            ],
        },
        "privacy_assertions": {
            "copyable_prompts_include_real_model_keys": False,
            "context_template_contains_raw_source": False,
            "agent_endpoint_secrets_returned": False,
            "learner_answers_returned": False,
            "browser_video_private_context_returned": False,
            "report_is_redacted": True,
        },
        "time_budget": {
            "target_minutes": 20,
            "estimated_operator_minutes": 12,
            "stop_on_first_blocker": True,
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

    tmp_root = Path(tempfile.mkdtemp(prefix="study-anything-first-lesson-kit-"))
    try:
        root = resolve_pack_root(args, tmp_root)
        payload = build_report(root)
        text = dump_json(payload)
        output = Path(args.output)
        if args.check:
            if not output.exists():
                raise FirstLessonAuthoringKitError(f"First lesson authoring kit missing: {output}")
            if output.read_text(encoding="utf-8") != text:
                raise FirstLessonAuthoringKitError(
                    "First lesson authoring kit is stale. Run "
                    "`python3 scripts/verify_first_lesson_authoring_kit.py --write`."
                )
            print("ok    first lesson authoring kit is up to date")
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
        print(f"verify_first_lesson_authoring_kit failed: {exc}", file=sys.stderr)
        sys.exit(1)
