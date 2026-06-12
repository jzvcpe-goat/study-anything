#!/usr/bin/env python3
"""Verify platform ecosystem path with importer, enrichment, retrieval, and eval gates."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


API_BASE = os.getenv("API_BASE", os.getenv("STUDY_ANYTHING_API_BASE", "http://127.0.0.1:8000")).rstrip("/")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("PLATFORM_ECOSYSTEM_EVAL_TIMEOUT_SECONDS", "15"))
ROOT = Path(__file__).resolve().parents[1]


class VerificationError(RuntimeError):
    """Readable ecosystem-smoke failure."""


def request(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{API_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise VerificationError(f"API returned {exc.code} for {path}: {detail}") from exc
    except URLError as exc:
        raise VerificationError(f"Cannot reach Study Anything at {API_BASE}: {exc}") from exc


def assert_schema(value: Dict[str, Any], schema_version: str, label: str) -> None:
    if value.get("schema_version") != schema_version:
        raise VerificationError(f"{label} returned invalid schema: {value}")


def assert_no_leaks(label: str, value: object, forbidden: list[str]) -> None:
    serialized = json.dumps(value, ensure_ascii=False)
    leaks = [fragment for fragment in forbidden if fragment and fragment in serialized]
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}", serialized):
        leaks.append("secret-looking sk token")
    if re.search(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{12,}", serialized):
        leaks.append("secret-looking key/value text")
    if leaks:
        raise VerificationError(f"{label} leaked private data: {leaks}")


def first_quiz_item(session: Dict[str, Any]) -> Dict[str, Any]:
    items = session.get("quiz_items") or []
    if not items or not isinstance(items[0], dict):
        raise VerificationError(f"Session did not produce quiz items: {session}")
    return items[0]


def run_external_eval(tool: str, session_id: str, *, query: str = "") -> Dict[str, Any]:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "run_external_agent_evals.py"),
        "--tool",
        tool,
        "--api-base",
        API_BASE,
        "--session-id",
        session_id,
        "--required",
        "--timeout-seconds",
        "45",
    ]
    if tool == "deepeval":
        command.append("--allow-native-quality-fallback")
    if tool == "retrieval":
        command.extend(["--query", query, "--limit", "3"])
    completed = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
        cwd=ROOT,
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"{tool} external eval failed.\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    try:
        return json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise VerificationError(f"Could not parse {tool} external eval output: {completed.stdout}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", default="platform-ecosystem-eval-user")
    parser.add_argument(
        "--query",
        default="AI product manager learning feedback vocabulary",
    )
    args = parser.parse_args()

    health = request("/v1/health")
    if health.get("status") != "ok":
        raise VerificationError(f"Health check failed: {health}")

    retrieval_status = request("/v1/retrieval/status")
    if retrieval_status.get("status") != "healthy":
        raise VerificationError(
            "Retrieval must be healthy for the ecosystem eval flow. "
            "Use STUDY_ANYTHING_RETRIEVAL_BACKEND=memory for local Skill Mode."
        )

    private_importer_text = (
        "Private importer note: AI PM learning improves when concepts, source evidence, "
        "glossary terms, feedback, and spaced review are connected."
    )
    private_platform_context = (
        "Private platform browser/video context: the learner needs a term map for retrieval "
        "practice, mastery deltas, and source-grounded synthesis."
    )
    private_answer = "Private answer: source evidence plus feedback makes recall more durable."
    importer = request(
        "/v1/importers/example-note-importer/run",
        {
            "inputs": {
                "note_reference": "obsidian://Study Anything/Platform Ecosystem Eval",
                "title": "Platform Ecosystem Eval",
                "markdown_excerpt": private_importer_text,
                "obsidian_backlinks": ["AI PM", "Retrieval", "Agent Eval"],
            },
            "confirmed_permissions": ["write:context"],
            "include_text": True,
        },
    )
    assert_schema(importer, "importer-run-v1", "importer runtime")
    package = importer.get("package")
    if not isinstance(package, dict):
        raise VerificationError(f"Importer did not return a package: {importer}")

    created_source = request(
        "/v1/sessions/from-context-package",
        {
            "user_id": args.user_id,
            "use_demo_agent": True,
            "package": package,
        },
    )
    source_session = created_source.get("session")
    if not isinstance(source_session, dict):
        raise VerificationError(f"Context package did not create a source session: {created_source}")
    source_session_id = str(source_session["session_id"])

    enrichment = request(
        f"/v1/sessions/{quote(source_session_id)}/enrichment",
        {
            "title": "Platform Agent External Context",
            "items": [
                {
                    "source_type": "web",
                    "reference": "https://platform.local/browser/ai-pm-learning",
                    "title": "Browser Context",
                    "locator": "section=ai-pm-learning",
                    "text": private_platform_context,
                    "provenance": {
                        "collector": "platform-agent-ecosystem-smoke",
                        "capture_method": "browser_excerpt",
                        "source_owner": "user",
                    },
                    "redaction_policy": "reference_only",
                    "metadata": {"collector": "platform-agent"},
                },
                {
                    "source_type": "video_slice",
                    "reference": "video://platform/ai-pm/clip-1",
                    "title": "Video Slice Context",
                    "locator": "00:01:12-00:02:05",
                    "text": private_platform_context,
                    "provenance": {
                        "collector": "platform-agent-ecosystem-smoke",
                        "capture_method": "video_transcript_slice",
                        "source_owner": "user",
                    },
                    "redaction_policy": "reference_only",
                    "metadata": {"collector": "platform-agent"},
                },
            ],
        },
    )
    assert_schema(enrichment, "learning-enrichment-v1", "platform enrichment")
    assert_no_leaks("platform enrichment response", enrichment, [private_platform_context])

    rebuilt = request(f"/v1/sessions/{quote(source_session_id)}/retrieval/rebuild", {})
    if rebuilt.get("indexed_count", 0) < 2:
        raise VerificationError(f"Retrieval rebuild did not index platform context: {rebuilt}")

    query_string = urlencode({"q": args.query, "limit": 3})
    retrieval_quality = request(
        f"/v1/sessions/{quote(source_session_id)}/retrieval/eval?{query_string}"
    )
    assert_schema(retrieval_quality, "retrieval-quality-eval-v1", "retrieval quality")
    if retrieval_quality.get("status") != "pass":
        raise VerificationError(f"Retrieval quality did not pass: {retrieval_quality}")
    assert_no_leaks(
        "retrieval quality",
        retrieval_quality,
        [private_importer_text, private_platform_context],
    )

    created_lesson = request(
        "/v1/sessions/from-retrieval",
        {
            "source_session_id": source_session_id,
            "query": args.query,
            "user_id": f"{args.user_id}-lesson",
            "use_demo_agent": True,
        },
    )
    assert_schema(created_lesson, "retrieval-session-v1", "retrieval lesson")
    lesson_session = created_lesson.get("session")
    if not isinstance(lesson_session, dict):
        raise VerificationError(f"Retrieval did not create a lesson: {created_lesson}")
    lesson_session_id = str(lesson_session["session_id"])

    teaching = request(
        f"/v1/sessions/{quote(lesson_session_id)}/teaching-layers",
        {"layers": ["overview", "glossary"], "language": "zh", "level": "beginner"},
    )
    assert_schema(teaching, "teaching-layers-v1", "teaching layers")
    running = request(f"/v1/sessions/{quote(lesson_session_id)}/run", {})
    quiz = first_quiz_item(running)
    completed = request(
        f"/v1/sessions/{quote(lesson_session_id)}/answers",
        {"answers": {str(quiz["item_id"]): private_answer}},
    )
    if completed.get("stage") != "completed":
        raise VerificationError(f"Lesson did not complete: {completed}")

    audit = request(f"/v1/sessions/{quote(lesson_session_id)}/agent-audit")
    artifact = request(f"/v1/sessions/{quote(lesson_session_id)}/agent-eval/artifact")
    quality = request(f"/v1/sessions/{quote(lesson_session_id)}/agent-eval/quality")
    enrichment_artifact = request(
        f"/v1/sessions/{quote(lesson_session_id)}/exports/enrichment-artifact"
    )
    obsidian = request(f"/v1/sessions/{quote(lesson_session_id)}/exports/obsidian")
    learning_package = request(f"/v1/sessions/{quote(lesson_session_id)}/exports/learning-package")
    assert_schema(audit, "agent-audit-v1", "agent audit")
    assert_schema(artifact, "agent-eval-artifact-v1", "agent eval artifact")
    assert_schema(quality, "agent-quality-eval-v1", "agent quality")
    assert_schema(enrichment_artifact, "learning-enrichment-artifact-v1", "enrichment artifact")
    assert_schema(obsidian, "obsidian-markdown-export-v1", "obsidian export")
    assert_schema(learning_package, "learning-package-v1", "learning package")
    if audit.get("status") != "verified" or quality.get("status") != "pass":
        raise VerificationError(f"Audit/quality gates failed: audit={audit} quality={quality}")

    retrieval_runner = run_external_eval("retrieval", source_session_id, query=args.query)
    deepeval_runner = run_external_eval("deepeval", lesson_session_id)
    if retrieval_runner.get("status") != "ok" or deepeval_runner.get("status") != "ok":
        raise VerificationError(
            f"External eval adapters did not pass: retrieval={retrieval_runner}, deepeval={deepeval_runner}"
        )

    redacted_eval_surfaces = {
        "audit": audit,
        "artifact": artifact,
        "quality": quality,
        "retrieval_quality": retrieval_quality,
        "retrieval_runner": retrieval_runner,
        "deepeval_runner": deepeval_runner,
    }
    assert_no_leaks(
        "ecosystem eval evidence",
        redacted_eval_surfaces,
        [private_importer_text, private_platform_context, private_answer, args.user_id],
    )
    # User-owned exports may include the learner's own answer and review history, but
    # they still must not accidentally contain credentials or secret-looking values.
    assert_no_leaks(
        "user-owned exports",
        {
            "enrichment_artifact": enrichment_artifact,
            "obsidian": obsidian,
            "learning_package": learning_package,
        },
        [],
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "api_base": API_BASE,
                "source_session_id": source_session_id,
                "lesson_session_id": lesson_session_id,
                "indexed_count": rebuilt["indexed_count"],
                "retrieval_quality_status": retrieval_quality["status"],
                "agent_quality_status": quality["status"],
                "retrieval_eval_tool": retrieval_runner["framework"],
                "deepeval_tool": deepeval_runner["tool"],
                "enrichment_artifact_schema": enrichment_artifact["schema_version"],
                "obsidian_schema": obsidian["schema_version"],
                "learning_package_schema": learning_package["schema_version"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_ecosystem_eval_flow failed: {exc}", file=sys.stderr)
        sys.exit(1)
