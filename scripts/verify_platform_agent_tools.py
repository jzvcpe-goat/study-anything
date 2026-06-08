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
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
}
REQUIRED_ADAPTERS = {"promptfoo", "deepeval", "langchain-agentevals", "ragas"}
REQUIRED_TRAJECTORY = ["quiz.generate", "answer.grade", "insight.synthesize"]
REQUIRED_PLATFORM_PACKS = {"codex", "kimi", "workbuddy"}
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

    private_source_text = "Private platform tool smoke source text must stay out of audit artifacts."
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
    if trajectory != REQUIRED_TRAJECTORY:
        raise VerificationError(f"Eval artifact trajectory mismatch: {trajectory}")

    serialized_evidence = json.dumps({"audit": audit, "artifact": artifact}, ensure_ascii=False)
    forbidden_fragments = [
        private_source_text,
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
                "adapter_ids": sorted(adapter_ids),
                "trajectory_tasks": trajectory,
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
