#!/usr/bin/env python3
"""Verify the platform-agent tool manifest against a running Study Anything API."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "platform" / "study-anything-platform-tools.json"
PACKS_DIR = ROOT / "platform" / "packs"
API_BASE = os.getenv("API_BASE", os.getenv("STUDY_ANYTHING_API_BASE", "http://127.0.0.1:8000")).rstrip("/")
REQUIRED_TOOLS = {
    "study_anything_health",
    "study_anything_create_session",
    "study_anything_add_reading",
    "study_anything_validate_context_package",
    "study_anything_create_session_from_context_package",
    "study_anything_append_context_package",
    "study_anything_run_importer",
    "study_anything_retrieval_status",
    "study_anything_retrieval_rebuild",
    "study_anything_retrieval_search",
    "study_anything_retrieval_quality_eval",
    "study_anything_create_session_from_retrieval",
    "study_anything_append_retrieval_context",
    "study_anything_add_enrichment",
    "study_anything_teaching_layers",
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
    "study_anything_agent_quality_eval",
    "study_anything_obsidian_export",
    "study_anything_enrichment_artifact_export",
    "study_anything_learning_package_export",
}
REQUIRED_ADAPTERS = {"promptfoo", "deepeval", "langchain-agentevals", "ragas"}
REQUIRED_TRAJECTORY = ["quiz.generate", "answer.grade", "insight.synthesize"]
REQUIRED_PLATFORM_PACKS = {"codex", "kimi", "workbuddy"}
NOTEBOOKLM_FIXTURE = ROOT / "fixtures" / "notebooklm" / "notebooklm-style-context-package.json"
BANNED_TOOL_PATH_FRAGMENTS = (
    "/v1/agents/providers",
    "/v1/agents/defaults",
    "/v1/models/",
    "/v1/plugins/install",
    "/v1/sync/export",
    "/v1/sync/inspect",
    "/v1/sync/restore-preview",
    "/v1/pmf/export",
)


class VerificationError(RuntimeError):
    """Readable verification failure."""


def load_manifest(path: Path = DEFAULT_MANIFEST) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise VerificationError(f"Cannot read platform manifest at {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise VerificationError(f"Platform manifest is not valid JSON: {exc}") from exc


def validate_manifest(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if manifest.get("schema_version") != "study-anything-platform-tools-v1":
        raise VerificationError(f"Unexpected manifest schema_version: {manifest.get('schema_version')}")
    tools = manifest.get("tools")
    if not isinstance(tools, list) or not tools:
        raise VerificationError("Platform manifest must include a non-empty tools list.")

    by_name: Dict[str, Dict[str, Any]] = {}
    for tool in tools:
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            raise VerificationError(f"Tool has invalid name: {tool}")
        if name in by_name:
            raise VerificationError(f"Duplicate tool name in platform manifest: {name}")
        method = tool.get("method")
        if method not in {"GET", "POST"}:
            raise VerificationError(f"{name} has unsupported method: {method}")
        path_template = tool.get("path_template")
        if not isinstance(path_template, str) or not path_template.startswith("/v1/"):
            raise VerificationError(f"{name} has invalid path_template: {path_template}")
        banned = [fragment for fragment in BANNED_TOOL_PATH_FRAGMENTS if fragment in path_template]
        if banned:
            raise VerificationError(f"{name} exposes high-risk management endpoint(s): {banned}")
        input_schema = tool.get("input_schema")
        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            raise VerificationError(f"{name} must declare an object input_schema.")
        by_name[name] = tool

    missing = REQUIRED_TOOLS - set(by_name)
    if missing:
        raise VerificationError(f"Platform manifest is missing required tools: {sorted(missing)}")

    evidence = manifest.get("acceptance_evidence") or {}
    command = evidence.get("local_verification_command", "")
    if "verify_platform_agent_tools.py" not in command:
        raise VerificationError("Manifest acceptance evidence must point to verify_platform_agent_tools.py.")
    missing_packs = [
        pack_id
        for pack_id in sorted(REQUIRED_PLATFORM_PACKS)
        if not (PACKS_DIR / pack_id / "pack.json").exists()
    ]
    if missing_packs:
        raise VerificationError(f"Missing platform ecosystem packs: {missing_packs}")
    return by_name


def request(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{API_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise VerificationError(f"API returned {exc.code} for {path}: {detail}") from exc
    except URLError as exc:
        raise VerificationError(f"Cannot reach Study Anything at {API_BASE}: {exc}") from exc


def path_for(tool: Dict[str, Any], **params: str) -> str:
    path = str(tool["path_template"])
    for key, value in params.items():
        path = path.replace("{" + key + "}", quote(value, safe=""))
    if "{" in path or "}" in path:
        raise VerificationError(f"Unresolved path parameter in {tool['name']}: {path}")
    return path


def call_tool(
    tools: Dict[str, Dict[str, Any]],
    name: str,
    payload: Optional[Dict[str, Any]] = None,
    **path_params: str,
) -> Any:
    tool = tools[name]
    path = path_for(tool, **path_params)
    if tool["method"] == "GET":
        return request(path)
    return request(path, payload or {})


def assert_contains_all(actual: Iterable[str], expected: Iterable[str], label: str) -> None:
    missing = set(expected) - set(actual)
    if missing:
        raise VerificationError(f"{label} missing required values: {sorted(missing)}")


def main() -> None:
    manifest = load_manifest()
    tools = validate_manifest(manifest)

    health = call_tool(tools, "study_anything_health")
    if health.get("status") != "ok":
        raise VerificationError(f"Health tool did not return ok: {health}")

    context_fixture = json.loads(NOTEBOOKLM_FIXTURE.read_text(encoding="utf-8"))
    context_private_fragments = [
        str(item.get("text") or "")
        for item in context_fixture.get("items", [])
        if isinstance(item, dict)
    ]
    context_validation = call_tool(
        tools,
        "study_anything_validate_context_package",
        {"package": context_fixture},
    )
    if context_validation.get("schema_version") != "learning-context-package-v1":
        raise VerificationError(f"Context package validation returned invalid schema: {context_validation}")
    if context_validation.get("status") != "valid":
        raise VerificationError(f"Context package validation failed: {context_validation}")
    if any(fragment in json.dumps(context_validation, ensure_ascii=False) for fragment in context_private_fragments):
        raise VerificationError("Context package validation leaked raw fixture text.")
    context_created = call_tool(
        tools,
        "study_anything_create_session_from_context_package",
        {
            "user_id": "platform-context-tools-smoke-user",
            "use_demo_agent": True,
            "package": context_fixture,
        },
    )
    if context_created.get("status") != "session_created":
        raise VerificationError(f"Context package session creation failed: {context_created}")
    context_session = context_created.get("session") or {}
    context_session_id = context_session.get("session_id")
    if not isinstance(context_session_id, str) or not context_session_id:
        raise VerificationError(f"Context package creation did not return a session id: {context_created}")
    context_source_types = {
        item.get("source_type")
        for item in context_session.get("enrichment_items", [])
        if isinstance(item, dict)
    }
    assert_contains_all(
        context_source_types,
        ["web", "document", "video_slice", "app_context", "markdown_note", "obsidian_note"],
        "context package imported source types",
    )
    context_appended = call_tool(
        tools,
        "study_anything_append_context_package",
        {"package": context_fixture},
        session_id=context_session_id,
    )
    if context_appended.get("status") != "session_expanded":
        raise VerificationError(f"Context package append failed: {context_appended}")

    importer = call_tool(
        tools,
        "study_anything_run_importer",
        {
            "inputs": {
                "note_reference": "obsidian://Platform Tools/Importer Smoke",
                "title": "Importer Smoke",
                "markdown_excerpt": "Importer runtime should produce a validated learning context package.",
            },
            "confirmed_permissions": ["write:context"],
            "include_text": True,
        },
        plugin_id="example-note-importer",
    )
    if importer.get("schema_version") != "importer-run-v1":
        raise VerificationError(f"Importer tool returned invalid schema: {importer}")
    if (importer.get("package") or {}).get("schema_version") != "learning-context-package-v1":
        raise VerificationError(f"Importer tool did not return a Learning Context Package: {importer}")
    if "Importer runtime should produce" in json.dumps(importer.get("redacted_package"), ensure_ascii=False):
        raise VerificationError("Importer redacted_package leaked raw importer text.")

    retrieval_status = call_tool(tools, "study_anything_retrieval_status")
    if retrieval_status.get("status") not in {"disabled", "healthy", "unavailable"}:
        raise VerificationError(f"Retrieval status returned invalid state: {retrieval_status}")
    if retrieval_status.get("status") == "healthy":
        rebuilt = call_tool(
            tools,
            "study_anything_retrieval_rebuild",
            {},
            session_id=context_session_id,
        )
        if rebuilt.get("status") != "rebuilt":
            raise VerificationError(f"Retrieval rebuild failed: {rebuilt}")
        searched = call_tool(
            tools,
            "study_anything_retrieval_search",
            {"query": "learning context package", "limit": 2},
            session_id=context_session_id,
        )
        if searched.get("schema_version") != "retrieval-search-v1":
            raise VerificationError(f"Retrieval search returned invalid schema: {searched}")
        retrieval_quality = call_tool(
            tools,
            "study_anything_retrieval_quality_eval",
            {"query": "learning context package", "limit": 2},
            session_id=context_session_id,
        )
        if retrieval_quality.get("schema_version") != "retrieval-quality-eval-v1":
            raise VerificationError(
                f"Retrieval quality eval returned invalid schema: {retrieval_quality}"
            )
        if retrieval_quality.get("status") != "pass":
            raise VerificationError(
                f"Retrieval quality eval did not pass: {retrieval_quality}"
            )
        if (retrieval_quality.get("privacy") or {}).get("result_snippets_included"):
            raise VerificationError(
                f"Retrieval quality eval returned snippet-bearing evidence: {retrieval_quality}"
            )

    private_source_text = "Private platform tool smoke source text must stay out of audit artifacts."
    private_enrichment_text = "Private enrichment web and video context must stay out of redacted evidence."
    private_answer = "Private platform tool smoke answer."
    session = call_tool(
        tools,
        "study_anything_create_session",
        {
            "user_id": "platform-tools-smoke-user",
            "track": "ACADEMIC",
            "use_demo_agent": True,
        },
    )
    session_id = session.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise VerificationError(f"Create session tool did not return a session_id: {session}")

    reading = call_tool(
        tools,
        "study_anything_add_reading",
        {
            "source_type": "local_text",
            "reference": "demo://platform-tools-smoke",
            "title": "Private Platform Tool Smoke",
            "text": private_source_text,
        },
        session_id=session_id,
    )
    source = reading.get("source") or {}
    if not source.get("excerpt_hash"):
        raise VerificationError(f"Reading tool did not persist an excerpt hash: {reading}")

    enrichment = call_tool(
        tools,
        "study_anything_add_enrichment",
        {
            "title": "Platform Tool Enrichment Bundle",
            "items": [
                {
                    "source_type": "web",
                    "reference": "https://example.test/platform-enrichment",
                    "title": "Private Enrichment Web",
                    "locator": "section=platform-smoke",
                    "text": private_enrichment_text,
                    "provenance": {
                        "collector": "platform-agent-tool-smoke",
                        "capture_method": "browser_excerpt",
                        "source_owner": "user",
                    },
                    "redaction_policy": "reference_only",
                },
                {
                    "source_type": "video_slice",
                    "reference": "video://platform-smoke/clip",
                    "title": "Private Enrichment Clip",
                    "locator": "00:00:08-00:00:21",
                    "text": private_enrichment_text,
                    "provenance": {
                        "collector": "platform-agent-tool-smoke",
                        "capture_method": "video_transcript_slice",
                        "source_owner": "user",
                    },
                    "redaction_policy": "reference_only",
                },
            ],
        },
        session_id=session_id,
    )
    if enrichment.get("schema_version") != "learning-enrichment-v1":
        raise VerificationError(f"Enrichment tool returned invalid schema: {enrichment}")
    if private_enrichment_text in json.dumps(enrichment, ensure_ascii=False):
        raise VerificationError("Enrichment tool response leaked raw enrichment text.")
    if not (enrichment.get("source") or {}).get("excerpt_hash"):
        raise VerificationError(f"Enrichment tool did not return a source excerpt hash: {enrichment}")

    teaching = call_tool(
        tools,
        "study_anything_teaching_layers",
        {
            "layers": ["overview", "glossary"],
            "language": "zh",
            "level": "beginner",
        },
        session_id=session_id,
    )
    if teaching.get("schema_version") != "teaching-layers-v1":
        raise VerificationError(f"Teaching layers tool returned invalid schema: {teaching}")
    teaching_layers = teaching.get("layers") or []
    layer_names = {item.get("layer") for item in teaching_layers if isinstance(item, dict)}
    if not {"overview", "glossary"}.issubset(layer_names):
        raise VerificationError(f"Teaching layers tool did not return requested layers: {teaching}")
    teaching_tasks = [
        item.get("agent", {}).get("task_type")
        for item in teaching_layers
        if isinstance(item, dict) and isinstance(item.get("agent"), dict)
    ]
    assert_contains_all(teaching_tasks, ["teach.overview", "teach.glossary"], "teaching layers")

    running = call_tool(tools, "study_anything_run", {}, session_id=session_id)
    quiz_items = running.get("quiz_items") or []
    if not quiz_items:
        raise VerificationError(f"Run tool did not produce a quiz item: {running}")
    quiz_id = quiz_items[0].get("item_id")
    if not quiz_id:
        raise VerificationError(f"Quiz item did not include item_id: {quiz_items[0]}")

    completed = call_tool(
        tools,
        "study_anything_answer",
        {"answers": {quiz_id: private_answer}},
        session_id=session_id,
    )
    if completed.get("stage") != "completed":
        raise VerificationError(f"Answer tool did not complete the learning loop: {completed}")

    mastery = call_tool(tools, "study_anything_mastery", session_id=session_id)
    if not isinstance(mastery.get("level"), (int, float)) or not mastery.get("bloom"):
        raise VerificationError(f"Mastery tool returned invalid mastery state: {mastery}")

    audit = call_tool(tools, "study_anything_agent_audit", session_id=session_id)
    if audit.get("schema_version") != "agent-audit-v1" or audit.get("status") != "verified":
        raise VerificationError(f"Agent audit tool did not return verified audit evidence: {audit}")
    assert_contains_all(audit.get("observed_tasks", []), REQUIRED_TRAJECTORY, "agent audit")

    artifact = call_tool(tools, "study_anything_agent_eval_artifact", session_id=session_id)
    if artifact.get("schema_version") != "agent-eval-artifact-v1":
        raise VerificationError(f"Unexpected eval artifact schema: {artifact}")
    if artifact.get("status") != "ready_for_external_eval":
        raise VerificationError(f"Eval artifact is not ready for external eval: {artifact}")
    failed_required_gates = [
        gate
        for gate in artifact.get("native_gates", [])
        if gate.get("required") and gate.get("status") != "pass"
    ]
    if failed_required_gates:
        raise VerificationError(f"Required native eval gates failed: {failed_required_gates}")
    adapter_ids = {adapter.get("adapter_id") for adapter in artifact.get("adapter_strategy", [])}
    if adapter_ids != REQUIRED_ADAPTERS:
        raise VerificationError(f"Eval adapter strategy mismatch: {sorted(adapter_ids)}")
    trajectory = [step.get("task_type") for step in artifact.get("trajectory", [])]
    assert_contains_all(trajectory, REQUIRED_TRAJECTORY, "eval artifact trajectory")

    quality = call_tool(tools, "study_anything_agent_quality_eval", session_id=session_id)
    if quality.get("schema_version") != "agent-quality-eval-v1":
        raise VerificationError(f"Unexpected quality eval schema: {quality}")
    if quality.get("status") != "pass":
        raise VerificationError(f"Quality eval did not pass minimum teaching gates: {quality}")
    quality_gate_ids = {gate.get("gate_id") for gate in quality.get("gates", [])}
    expected_quality_gates = {
        "overview_quality",
        "glossary_quality",
        "quiz_quality",
        "grading_quality",
        "synthesis_quality",
    }
    assert_contains_all(quality_gate_ids, expected_quality_gates, "quality eval gates")

    obsidian = call_tool(tools, "study_anything_obsidian_export", session_id=session_id)
    if obsidian.get("schema_version") != "obsidian-markdown-export-v1":
        raise VerificationError(f"Unexpected Obsidian export schema: {obsidian}")
    markdown = str(obsidian.get("markdown") or "")
    for heading in ["## Source", "## Quiz Review", "## Mastery", "## Enrichment Context"]:
        if heading not in markdown:
            raise VerificationError(f"Obsidian export missing heading {heading}: {markdown}")
    if private_source_text in markdown or private_enrichment_text in markdown:
        raise VerificationError("Obsidian export leaked raw source/enrichment text.")

    enrichment_artifact = call_tool(
        tools,
        "study_anything_enrichment_artifact_export",
        session_id=session_id,
    )
    if enrichment_artifact.get("schema_version") != "learning-enrichment-artifact-v1":
        raise VerificationError(f"Unexpected enrichment artifact schema: {enrichment_artifact}")
    if enrichment_artifact.get("format") != "markdown+html":
        raise VerificationError(f"Unexpected enrichment artifact format: {enrichment_artifact}")
    if "learning-enrichment-artifact-v1" not in str(enrichment_artifact.get("html") or ""):
        raise VerificationError(f"Enrichment artifact HTML missing schema marker: {enrichment_artifact}")
    if private_source_text in json.dumps(enrichment_artifact, ensure_ascii=False):
        raise VerificationError("Enrichment artifact leaked raw source text.")
    if private_enrichment_text in json.dumps(enrichment_artifact, ensure_ascii=False):
        raise VerificationError("Enrichment artifact leaked raw enrichment text.")

    package = call_tool(tools, "study_anything_learning_package_export", session_id=session_id)
    if package.get("schema_version") != "learning-package-v1":
        raise VerificationError(f"Unexpected learning package schema: {package}")
    consumers = set(str(item) for item in package.get("intended_consumers", []))
    assert_contains_all(consumers, ["platform_agent", "notebooklm_bridge", "obsidian_pipeline"], "learning package consumers")
    package_privacy = package.get("privacy") or {}
    if package_privacy.get("raw_source_text_included") or package_privacy.get("raw_enrichment_text_included"):
        raise VerificationError(f"Learning package privacy flags are unsafe: {package_privacy}")
    if private_source_text in json.dumps(package, ensure_ascii=False):
        raise VerificationError("Learning package leaked raw source text.")
    if private_enrichment_text in json.dumps(package, ensure_ascii=False):
        raise VerificationError("Learning package leaked raw enrichment text.")

    serialized_evidence = json.dumps(
        {"audit": audit, "artifact": artifact, "quality": quality},
        ensure_ascii=False,
    )
    forbidden_fragments = [
        private_source_text,
        private_enrichment_text,
        private_answer,
        "Private Platform Tool Smoke",
        "platform-tools-smoke-user",
        "127.0.0.1:8787",
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
    ]
    leaks = [fragment for fragment in forbidden_fragments if fragment in serialized_evidence]
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9]{16,}", serialized_evidence):
        leaks.append("secret-looking sk token")
    if leaks:
        raise VerificationError(f"Platform evidence leaked private data: {leaks}")

    print(
        json.dumps(
            {
                "status": "ok",
                "manifest_schema": manifest["schema_version"],
                "tool_count": len(tools),
                "api_base": API_BASE,
                "session_id": session_id,
                "agent_audit_status": audit["status"],
                "eval_schema": artifact["schema_version"],
                "quality_schema": quality["schema_version"],
                "obsidian_schema": obsidian["schema_version"],
                "enrichment_artifact_schema": enrichment_artifact["schema_version"],
                "learning_package_schema": package["schema_version"],
                "adapter_ids": sorted(adapter_ids),
                "trajectory_tasks": trajectory,
                "teaching_tasks": teaching_tasks,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_agent_tools failed: {exc}", file=sys.stderr)
        sys.exit(1)
