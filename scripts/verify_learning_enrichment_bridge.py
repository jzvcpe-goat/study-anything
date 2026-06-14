#!/usr/bin/env python3
"""Verify the Learning Enrichment operator bridge for platform agents."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core.learning_context import (  # noqa: E402
    ALLOWED_CONTEXT_SOURCE_TYPES,
    LEARNING_CONTEXT_SCHEMA_VERSION,
    validate_learning_context_package,
)
from study_anything.core.learning_enrichment import (  # noqa: E402
    LEARNING_ENRICHMENT_ARTIFACT_SCHEMA_VERSION,
    build_learning_enrichment_artifact,
)
from study_anything.core.learning_package import build_learning_package_export  # noqa: E402
from study_anything.core.obsidian_export import build_obsidian_markdown_export  # noqa: E402
from study_anything.core.second_brain_handoff import build_second_brain_handoff  # noqa: E402
from study_anything.core.security import hash_user_id, sha256_text  # noqa: E402
from study_anything.core.workflow import (  # noqa: E402
    Answer,
    EnrichmentItem,
    GradingResult,
    LearningState,
    Mastery,
    QuizItem,
    ReadingSource,
)


SCHEMA_VERSION = "learning-enrichment-bridge-verification-v1"
RELEASE_VERSION = "v0.3.21-alpha"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-learning-enrichment-bridge.json"
DEFAULT_PACK = ROOT / "platform" / "generated" / "study-anything-platform-adoption-pack.zip"
PLATFORM_IDS = ("codex", "kimi", "workbuddy")
REQUIRED_PACK_COMMAND = "verify_learning_enrichment_bridge.py --check"
REQUIRED_EVIDENCE = (
    "learning_enrichment_bridge.schema_version == learning-enrichment-bridge-verification-v1"
)
REQUIRED_TOOLS = {
    "study_anything_validate_context_package",
    "study_anything_create_session_from_context_package",
    "study_anything_append_context_package",
    "study_anything_add_enrichment",
    "study_anything_teaching_layers",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
    "study_anything_obsidian_export",
    "study_anything_enrichment_artifact_export",
    "study_anything_learning_package_export",
    "study_anything_second_brain_handoff_export",
}
REQUIRED_DOCS = {
    "docs/learning-enrichment.md": [
        "learning-enrichment-artifact-v1",
        "video_slice",
        "app_context",
        "HTML",
    ],
    "docs/notebooklm-bridge.md": [
        "manual",
        "official_notebooklm_api_required: false",
        "second-brain-handoff-v1",
    ],
    "docs/obsidian-export.md": [
        "obsidian-markdown-export-v1",
        "raw source text",
        "second-brain",
    ],
    "docs/second-brain-handoff.md": [
        "second-brain-handoff-v1",
        "NotebookLM",
        "local archive",
    ],
    "docs/platform-agent-integrations.md": [
        "Learning Enrichment",
        "NotebookLM",
        "Obsidian",
    ],
    "docs/use-with-kimi.md": [
        "study_anything_add_enrichment",
        "study_anything_second_brain_handoff_export",
        "NotebookLM",
    ],
}
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
]
FORBIDDEN_LITERALS = [
    "Private platform browser/video context",
    "raw source text returned",
    "http://127.0.0.1:8787/private-agent",
    "bridge-secret",
]


class LearningEnrichmentBridgeError(RuntimeError):
    """Readable operator-bridge verification failure."""


class EnrichmentHTMLParser(HTMLParser):
    """Tiny structural parser for the generated micro-lesson HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.article_schema: str | None = None
        self.tags: list[str] = []
        self.headings: list[str] = []
        self._capture_heading = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        attributes = dict(attrs)
        if tag == "article":
            self.article_schema = attributes.get("data-schema")
        if tag == "h2":
            self._capture_heading = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self._capture_heading = False

    def handle_data(self, data: str) -> None:
        if self._capture_heading:
            text = data.strip()
            if text:
                self.headings.append(text)


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise LearningEnrichmentBridgeError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LearningEnrichmentBridgeError(f"JSON object expected: {path}")
    return value


def read_json_any(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise LearningEnrichmentBridgeError(f"Cannot read JSON {path}: {exc}") from exc


def resolve_pack_root(args: argparse.Namespace, tmp_root: Path) -> Path:
    if args.pack_root:
        root = Path(args.pack_root).resolve()
        if not root.exists():
            raise LearningEnrichmentBridgeError(f"Pack root does not exist: {root}")
        return root
    if args.pack:
        pack = Path(args.pack).resolve()
        if not pack.exists():
            raise LearningEnrichmentBridgeError(f"Adoption pack archive is missing: {pack}")
        with zipfile.ZipFile(pack) as archive:
            roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
            if len(roots) != 1:
                raise LearningEnrichmentBridgeError(
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
        raise LearningEnrichmentBridgeError(f"Unsafe path escapes pack root: {relative_path}") from exc
    return target


def require_file(root: Path, relative_path: str) -> Path:
    target = safe_relative(root, relative_path)
    if not target.is_file():
        raise LearningEnrichmentBridgeError(f"Required bridge asset is missing: {relative_path}")
    return target


def assert_contains(root: Path, relative_path: str, *needles: str) -> str:
    text = require_file(root, relative_path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise LearningEnrichmentBridgeError(f"{relative_path} is missing required text: {missing}")
    return text


def assert_no_sensitive_text(label: str, payload: Any, forbidden: list[str]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in forbidden + FORBIDDEN_LITERALS if literal and literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise LearningEnrichmentBridgeError(f"{label} leaked private data: {leaks}")


def fixture_package() -> dict[str, Any]:
    capture_by_type = {
        "app_context": "app_selection",
        "document": "document_excerpt",
        "markdown_note": "markdown_excerpt",
        "obsidian_note": "obsidian_excerpt",
        "video_slice": "video_transcript_slice",
        "web": "browser_excerpt",
    }
    return {
        "schema_version": LEARNING_CONTEXT_SCHEMA_VERSION,
        "package_id": "operator-bridge-v0-3-14",
        "title": "Learning Enrichment Operator Bridge",
        "reference": "learning-context://operator-bridge/v0.3.14",
        "producer": "platform-agent",
        "language": "zh",
        "track": "PRODUCT",
        "metadata": {
            "bridge": "learning-enrichment-operator",
            "platforms": ["kimi", "codex", "workbuddy"],
        },
        "items": [
            {
                "item_id": f"operator-{source_type}",
                "source_type": source_type,
                "reference": f"{source_type}://study-anything/operator-bridge",
                "title": f"{source_type} enrichment reference",
                "text": (
                    f"Private platform browser/video context for {source_type}; "
                    "bounded excerpt used only to create hashes and references."
                ),
                "locator": "section=operator-bridge",
                "provenance": {
                    "collector": "platform-agent",
                    "capture_method": capture_by_type[source_type],
                    "source_owner": "user",
                    "platform": "operator-bridge-fixture",
                },
                "redaction_policy": "reference_only",
                "metadata": {
                    "bridge_role": "teaching_context",
                    "obsidian_backlinks": ["[[Study Anything Bridge]]"]
                    if source_type == "obsidian_note"
                    else [],
                },
            }
            for source_type in sorted(ALLOWED_CONTEXT_SOURCE_TYPES)
        ],
    }


def build_state() -> tuple[LearningState, dict[str, Any], list[str]]:
    package_values = fixture_package()
    package = validate_learning_context_package(package_values)
    primary_text = "Private primary source text for Learning Enrichment bridge verification."
    private_answer = "Private learner enrichment answer that must stay out of strict handoff."
    private_feedback = "Private bridge grading feedback."
    private_agent_endpoint = "http://127.0.0.1:8787/private-agent?token=bridge-secret"
    enrichment_items = [
        EnrichmentItem(
            source_type=item.source_type,
            reference=item.reference,
            title=item.title,
            text=item.text,
            excerpt_hash=item.excerpt_hash,
            locator=item.locator,
            metadata={
                **item.metadata,
                "provenance": dict(item.provenance),
                "redaction_policy": item.redaction_policy,
            },
        )
        for item in package.items
    ]
    state = LearningState(
        session_id="session-learning-enrichment-bridge-12345678",
        user_id="learning-enrichment-bridge-user",
        user_hash=hash_user_id("learning-enrichment-bridge-user"),
        track=package.track or "PRODUCT",
        stage="completed",
        source=ReadingSource(
            source_type="learning_context_package",
            reference=package.reference,
            title=package.title,
            text=primary_text,
            excerpt_hash=sha256_text(primary_text),
            verified=True,
        ),
        enrichment_items=enrichment_items,
        teaching_layers=[
            {
                "layer": "overview",
                "task_type": "teach.overview",
                "content": "A platform Agent gathers context; Study Anything turns it into source-bound practice.",
                "citations": [package.items[0].excerpt_hash],
                "confidence": 0.9,
                "agent": {
                    "provider_id": "operator-bridge-agent",
                    "task_type": "teach.overview",
                    "status": "ok",
                    "latency_ms": 5,
                    "endpoint": private_agent_endpoint,
                    "metadata": {
                        "endpoint": private_agent_endpoint,
                        "api_key": "sk-proj-OperatorBridgeSecret000000",
                        "tokens": {"input": 18, "output": 41},
                    },
                },
            },
            {
                "layer": "glossary",
                "task_type": "teach.glossary",
                "content": {
                    "Learning Enrichment Layer": "Turns external platform context into bounded learning references.",
                    "NotebookLM bridge": "A manual import/export contract, not a hosted API dependency.",
                    "Second-brain handoff": "A strict local-memory export for Obsidian and archives.",
                },
                "citations": [package.items[-1].excerpt_hash],
                "confidence": 0.86,
                "agent": {"provider_id": "operator-bridge-agent", "status": "ok"},
            },
        ],
        quiz_items=[
            QuizItem(
                item_id="bridge-quiz-1",
                prompt="What stays outside Study Anything when a platform Agent enriches a lesson?",
                source_ref=package.reference,
                excerpt_hash=package.items[0].excerpt_hash,
                rubric="Name credentials, raw browser/app/video context, and unbounded source dumps.",
            )
        ],
        answers=[Answer(item_id="bridge-quiz-1", text=private_answer)],
        grading_results=[
            GradingResult(
                item_id="bridge-quiz-1",
                score=0.93,
                feedback=private_feedback,
                reward=1.0,
            )
        ],
        mastery=Mastery(level=0.84, bloom="analyze"),
        insights=["Use enrichment references to decide what the learner should review next."],
    )
    forbidden = [
        primary_text,
        private_answer,
        private_feedback,
        private_agent_endpoint,
        "sk-proj-OperatorBridgeSecret000000",
        "bridge-secret",
        *[item.text for item in package.items],
    ]
    return state, package.public_dict(), forbidden


def verify_html_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    html = str(artifact.get("html") or "")
    parser = EnrichmentHTMLParser()
    parser.feed(html)
    required_headings = {"Teaching Brief", "Professional Terms", "Source Map", "Practice"}
    if parser.article_schema != LEARNING_ENRICHMENT_ARTIFACT_SCHEMA_VERSION:
        raise LearningEnrichmentBridgeError("Enrichment HTML article data-schema drifted.")
    if "script" in parser.tags:
        raise LearningEnrichmentBridgeError("Enrichment HTML must not include scripts.")
    if required_headings - set(parser.headings):
        raise LearningEnrichmentBridgeError(
            f"Enrichment HTML missing headings: {sorted(required_headings - set(parser.headings))}"
        )
    if "<article" not in html or "<section>" not in html:
        raise LearningEnrichmentBridgeError("Enrichment HTML must be embeddable structured HTML.")
    return {
        "article_schema": parser.article_schema,
        "headings": parser.headings,
        "contains_script_tag": False,
        "embeddable_article": True,
    }


def verify_exports(state: LearningState, public_package: dict[str, Any], forbidden: list[str]) -> dict[str, Any]:
    obsidian = build_obsidian_markdown_export(state)
    package = build_learning_package_export(state)
    artifact = build_learning_enrichment_artifact(state)
    second_brain = build_second_brain_handoff(state)

    schemas = {
        "context_package": public_package.get("schema_version"),
        "obsidian": obsidian.get("schema_version"),
        "learning_package": package.get("schema_version"),
        "enrichment_artifact": artifact.get("schema_version"),
        "second_brain": second_brain.get("schema_version"),
        "archive_manifest": second_brain["local_archive"]["manifest"]["schema_version"],
    }
    expected_schemas = {
        "context_package": LEARNING_CONTEXT_SCHEMA_VERSION,
        "obsidian": "obsidian-markdown-export-v1",
        "learning_package": "learning-package-v1",
        "enrichment_artifact": LEARNING_ENRICHMENT_ARTIFACT_SCHEMA_VERSION,
        "second_brain": "second-brain-handoff-v1",
        "archive_manifest": "second-brain-archive-manifest-v1",
    }
    if schemas != expected_schemas:
        raise LearningEnrichmentBridgeError(f"Bridge schema drifted: {schemas}")

    source_types = sorted(
        str(item.get("source_type"))
        for item in package.get("source_references", [])
        if isinstance(item, dict) and item.get("kind") == "enrichment"
    )
    if source_types != sorted(ALLOWED_CONTEXT_SOURCE_TYPES):
        raise LearningEnrichmentBridgeError(f"Source type coverage drifted: {source_types}")

    source_hashes = {
        str(item.get("excerpt_hash"))
        for item in package.get("source_references", [])
        if isinstance(item, dict) and item.get("kind") == "enrichment"
    }
    user_owned_export_forbidden = [
        fragment
        for fragment in forbidden
        if fragment
        not in {
            "Private learner enrichment answer that must stay out of strict handoff.",
            "Private bridge grading feedback.",
        }
    ]
    assert_no_sensitive_text("obsidian", obsidian, user_owned_export_forbidden)
    assert_no_sensitive_text("learning_package", package, user_owned_export_forbidden)
    assert_no_sensitive_text("enrichment_artifact", artifact, user_owned_export_forbidden)
    assert_no_sensitive_text("second_brain", second_brain, forbidden)
    artifact_refs = {
        str(item.get("excerpt_hash"))
        for item in artifact.get("source_references", [])
        if isinstance(item, dict) and item.get("kind") == "enrichment"
    }
    if source_hashes - artifact_refs:
        raise LearningEnrichmentBridgeError("Enrichment artifact lost source-bound excerpt hashes.")

    second_privacy = second_brain.get("privacy") or {}
    if second_privacy.get("learner_answers_included") is not False:
        raise LearningEnrichmentBridgeError("Strict second-brain handoff includes learner answers.")
    if second_brain["notebooklm_bridge"].get("official_notebooklm_api_required") is not False:
        raise LearningEnrichmentBridgeError("NotebookLM bridge must remain manual/API-independent.")

    archive = second_brain["local_archive"]
    roles = {str(item.get("role")) for item in archive.get("files", []) if isinstance(item, dict)}
    required_roles = {"obsidian_note", "learning_package", "enrichment_markdown", "enrichment_html"}
    if required_roles - roles:
        raise LearningEnrichmentBridgeError(f"Second-brain archive missing roles: {sorted(required_roles - roles)}")
    manifest_files = {item["path"]: item for item in archive["manifest"]["files"]}
    for file in archive["files"]:
        digest = hashlib.sha256(str(file["content"]).encode("utf-8")).hexdigest()
        if file["sha256"] != digest or manifest_files[file["path"]]["sha256"] != digest:
            raise LearningEnrichmentBridgeError(f"Archive digest mismatch: {file['path']}")

    return {
        "schemas": schemas,
        "source_types": source_types,
        "source_hash_count": len(source_hashes),
        "html_artifact": verify_html_artifact(artifact),
        "notebooklm_bridge": {
            "status": second_brain["notebooklm_bridge"]["status"],
            "mode": second_brain["handoff_contract"]["notebooklm_mode"],
            "official_notebooklm_api_required": False,
            "manual_steps": len(second_brain["notebooklm_bridge"].get("manual_steps", [])),
        },
        "obsidian": {
            "direct_export_filename": obsidian["filename"],
            "strict_handoff_filename": second_brain["obsidian"]["filename"],
            "backlink_count": len(second_brain["obsidian"].get("backlinks", [])),
        },
        "local_archive": {
            "schema_version": archive["manifest"]["schema_version"],
            "file_roles": sorted(roles),
            "file_count": len(archive["files"]),
        },
        "privacy": {
            "raw_source_text_included": False,
            "raw_enrichment_text_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "strict_handoff_learner_answers_included": False,
            "secrets_included": False,
        },
    }


def verify_tool_assets(root: Path) -> dict[str, Any]:
    manifest = read_json(safe_relative(root, "platform/study-anything-platform-tools.json"))
    tools = {str(tool.get("name")) for tool in manifest.get("tools", []) if isinstance(tool, dict)}
    openai_tools = read_json_any(safe_relative(root, "platform/generated/study-anything-openai-tools.json"))
    openapi = read_json(safe_relative(root, "platform/generated/study-anything-platform-openapi.json"))
    openai_names = {
        str(item.get("function", {}).get("name"))
        for item in openai_tools
        if isinstance(item, dict)
    }
    openapi_operation_ids = {
        str(operation.get("operationId"))
        for methods in openapi.get("paths", {}).values()
        if isinstance(methods, dict)
        for operation in methods.values()
        if isinstance(operation, dict) and operation.get("operationId")
    }
    missing = sorted(REQUIRED_TOOLS - tools - openai_names - openapi_operation_ids)
    if missing:
        raise LearningEnrichmentBridgeError(f"Bridge platform tools missing: {missing}")
    return {
        "required_tools_present": sorted(REQUIRED_TOOLS),
        "tool_count": len(tools),
        "openai_tool_count": len(openai_tools) if isinstance(openai_tools, list) else 0,
        "openapi_path_count": len(openapi.get("paths", {})),
    }


def verify_docs(root: Path) -> dict[str, Any]:
    for path, needles in REQUIRED_DOCS.items():
        assert_contains(root, path, *needles)
    return {
        "checked_docs": sorted(REQUIRED_DOCS),
        "skill_first_positioning": True,
        "standalone_frontend_required": False,
    }


def verify_platform_packs(root: Path) -> dict[str, Any]:
    platforms: dict[str, Any] = {}
    for platform_id in PLATFORM_IDS:
        pack = read_json(safe_relative(root, f"platform/packs/{platform_id}/pack.json"))
        commands = "\n".join(str(command) for command in pack.get("local_verification_commands", []))
        evidence = set(str(item) for item in pack.get("acceptance_evidence", []))
        if REQUIRED_PACK_COMMAND not in commands:
            raise LearningEnrichmentBridgeError(f"{platform_id} pack missing bridge verifier command.")
        if REQUIRED_EVIDENCE not in evidence:
            raise LearningEnrichmentBridgeError(f"{platform_id} pack missing bridge evidence.")
        platforms[platform_id] = {
            "command_declared": True,
            "acceptance_evidence_declared": True,
            "integration_mode": pack.get("integration_mode"),
        }
    return platforms


def verify_submission(root: Path) -> dict[str, Any]:
    submission = read_json(safe_relative(root, "platform/ecosystem-submission.json"))
    if submission.get("version") != RELEASE_VERSION:
        raise LearningEnrichmentBridgeError("Ecosystem submission version drifted.")
    shared_assets = set(str(asset) for asset in submission.get("shared_assets", []))
    required_assets = {
        "scripts/verify_learning_enrichment_bridge.py",
        "platform/generated/study-anything-learning-enrichment-bridge.json",
        "docs/learning-enrichment.md",
        "docs/notebooklm-bridge.md",
        "docs/second-brain-handoff.md",
    }
    missing = required_assets - shared_assets
    if missing:
        raise LearningEnrichmentBridgeError(f"Ecosystem submission missing bridge assets: {sorted(missing)}")
    acceptance = submission.get("acceptance") or {}
    command_text = "\n".join(str(command) for command in acceptance.get("minimum_commands", []))
    prove_text = "\n".join(str(item) for item in acceptance.get("must_prove", []))
    if REQUIRED_PACK_COMMAND not in command_text:
        raise LearningEnrichmentBridgeError("Ecosystem submission missing bridge command.")
    if SCHEMA_VERSION not in prove_text:
        raise LearningEnrichmentBridgeError("Ecosystem submission must prove bridge schema.")
    return {
        "schema_version": submission.get("schema_version"),
        "version": submission.get("version"),
        "shared_assets_included": len(required_assets),
    }


def verify_adoption_pack_manifest(root: Path) -> dict[str, Any]:
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
        "scripts/verify_learning_enrichment_bridge.py",
        "platform/generated/study-anything-learning-enrichment-bridge.json",
        "docs/release-notes/v0.3.21-alpha.md",
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
        "bridge_assets_included": len(required),
    }


def operator_flow() -> list[dict[str, str]]:
    return [
        {
            "step_id": "collect_context_outside_study_anything",
            "operator": "Platform Agent collects browser, document, video, app, Markdown, or Obsidian context.",
            "study_anything_boundary": "Accept only bounded excerpts with references, locators, provenance, and hashes.",
        },
        {
            "step_id": "validate_or_import_context_package",
            "operator": "Call validate/create/append context package tools.",
            "study_anything_boundary": "Reject secrets, hidden instructions, unbounded dumps, and invalid provenance.",
        },
        {
            "step_id": "run_source_bound_learning",
            "operator": "Run teaching layers, quiz, answers, mastery, audit, and eval artifact.",
            "study_anything_boundary": "Persist learning state and citations; do not own external browsing/tools.",
        },
        {
            "step_id": "export_enrichment_micro_lesson",
            "operator": "Use Markdown/HTML artifact inside Kimi, Codex, WorkBuddy, or another host.",
            "study_anything_boundary": "Return source map, references, and generated teaching content without raw excerpts.",
        },
        {
            "step_id": "handoff_to_second_brain",
            "operator": "Export Obsidian note, NotebookLM manual bridge, and local archive manifest.",
            "study_anything_boundary": "Strict handoff excludes learner answers, grading feedback, Agent endpoints, and secrets.",
        },
    ]


def build_report(root: Path) -> dict[str, Any]:
    state, public_package, forbidden = build_state()
    report = {
        "schema_version": SCHEMA_VERSION,
        "version": RELEASE_VERSION,
        "status": "pass",
        "operator_flow": operator_flow(),
        "context_contract": {
            "schema_version": public_package["schema_version"],
            "item_count": public_package["item_count"],
            "source_types": public_package["source_types"],
            "public_dict_includes_text": public_package["privacy"]["bounded_excerpts_included"],
            "allowed_source_types": sorted(ALLOWED_CONTEXT_SOURCE_TYPES),
        },
        "exports": verify_exports(state, public_package, forbidden),
        "tool_assets": verify_tool_assets(root),
        "docs": verify_docs(root),
        "platform_packs": verify_platform_packs(root),
        "ecosystem_submission": verify_submission(root),
        "adoption_pack": verify_adoption_pack_manifest(root),
        "acceptance": {
            "minimum_command": f"python3 scripts/{Path(__file__).name} --check",
            "pack_command": f"python3 scripts/{Path(__file__).name} --pack {DEFAULT_PACK.relative_to(ROOT)}",
            "release_gate": "scripts/release_check.sh",
        },
        "privacy_assertions": {
            "real_model_keys_stored_by_study_anything": False,
            "raw_source_text_in_report": False,
            "raw_enrichment_text_in_report": False,
            "learner_answers_in_strict_handoff": False,
            "agent_endpoint_secrets_in_report": False,
            "browser_video_private_context_in_report": False,
            "report_is_redacted": True,
        },
    }
    assert_no_sensitive_text("learning enrichment bridge report", report, forbidden)
    return report


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(payload), encoding="utf-8")


def check_report(path: Path, payload: dict[str, Any]) -> None:
    expected = dump_json(payload)
    if not path.exists():
        raise LearningEnrichmentBridgeError(f"Learning enrichment bridge report is missing: {path}")
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        raise LearningEnrichmentBridgeError(
            f"Learning enrichment bridge report is stale. Run {Path(__file__).name} --write."
        )
    adoption = payload.get("adoption_pack") or {}
    if adoption.get("included") is not True:
        raise LearningEnrichmentBridgeError(f"Adoption pack missing bridge evidence: {adoption}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", default=None, help="Validate a platform adoption pack zip.")
    parser.add_argument("--pack-root", default=None, help="Validate an extracted adoption pack root.")
    parser.add_argument("--write", action="store_true", help="Write the generated report.")
    parser.add_argument("--check", action="store_true", help="Require the generated report to be current.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Report output path.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="study-anything-enrichment-bridge-") as tmp:
        root = resolve_pack_root(args, Path(tmp))
        if root.resolve() != ROOT.resolve():
            require_file(root, "scripts/verify_learning_enrichment_bridge.py")
            require_file(root, "platform/generated/study-anything-learning-enrichment-bridge.json")
        report = build_report(root)

    output = Path(args.output)
    if args.write:
        write_report(output, report)
    if args.check:
        check_report(output, report)
    print(dump_json(report), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_learning_enrichment_bridge failed: {exc}", file=sys.stderr)
        sys.exit(1)
