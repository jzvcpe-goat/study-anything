#!/usr/bin/env python3
"""Verify importer runtime -> retrieval -> lesson -> quality -> export flow."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import (
    format_api_unreachable,
    redact_diagnostic,
    resolve_api_base,
    verifier_name_from_file,
)


API_BASE = resolve_api_base()
REQUEST_TIMEOUT_SECONDS = int(os.getenv("IMPORTER_RETRIEVAL_TIMEOUT_SECONDS", "15"))
VERIFIER_NAME = verifier_name_from_file(__file__)
DEFAULT_PRIVATE_USER = "importer-runtime-retrieval-smoke-user"
DEFAULT_EXCERPT = (
    "AI product learning improves when a learner connects overall product intent, "
    "technical vocabulary, source evidence, feedback, and spaced review."
)
DEFAULT_QUERY = "AI product learning feedback vocabulary"
DEFAULT_ANSWER = "The lesson connects source evidence to feedback and review."
FORBIDDEN_LITERALS = (
    DEFAULT_PRIVATE_USER,
    DEFAULT_EXCERPT,
    DEFAULT_ANSWER,
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
)


class VerificationError(RuntimeError):
    """Readable smoke failure."""


def sanitize_text(value: str | bytes | None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    text = text.replace(DEFAULT_PRIVATE_USER, "<private-user>")
    text = text.replace(DEFAULT_EXCERPT, "<private-source-text>")
    text = text.replace(DEFAULT_ANSWER, "<private-answer>")
    text = re.sub(r"(?i)ai product learning improves[^\"']*", "<private-source-text>", text)
    text = re.sub(r"(?i)the lesson connects source evidence[^\"']*", "<private-answer>", text)
    return redact_diagnostic(text).strip()[:1600]


def classify_failure(message: str) -> str:
    lowered = message.lower()
    if (
        "runner appears to block localhost sockets" in lowered
        or "blocks localhost" in lowered
        or "operation not permitted" in lowered
        or "permission denied" in lowered
        or "localhost_socket_blocked" in lowered
    ):
        return "localhost_socket_blocked"
    if "cannot reach" in lowered or "connection refused" in lowered or "urlopen error" in lowered:
        return "api_unreachable"
    if "health check failed" in lowered:
        return "api_health_not_ok"
    if "retrieval is not healthy" in lowered:
        return "retrieval_unhealthy"
    if "importer did not return" in lowered or "importer package did not create" in lowered:
        return "importer_context_failed"
    if "retrieval rebuild indexed no documents" in lowered:
        return "retrieval_rebuild_failed"
    if "retrieval search returned no results" in lowered:
        return "retrieval_search_failed"
    if "retrieval quality eval did not pass" in lowered:
        return "retrieval_quality_failed"
    if "lesson did not complete" in lowered or "session did not produce quiz items" in lowered:
        return "learning_flow_incomplete"
    if "quality eval did not pass" in lowered:
        return "quality_eval_failed"
    if "agent eval report native gate failed" in lowered:
        return "agent_eval_failed"
    if "leaked secret-looking" in lowered or "leaked private" in lowered:
        return "privacy_leak"
    if "returned invalid schema" in lowered:
        return "response_schema_invalid"
    return "importer_runtime_retrieval_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "STUDY_ANYTHING_RETRIEVAL_BACKEND=memory ./scripts/launch_skill_mode.sh",
        f"API_BASE={API_BASE} python3 scripts/verify_importer_runtime_retrieval_flow.py",
        "python3 scripts/diagnose_adoption.py",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run the verifier from a normal terminal or host shell that permits localhost sockets.",
            "If this came from Codex or another sandboxed Agent, collect this blocked report and rerun outside the sandbox.",
        ],
        "api_unreachable": [
            "Start the Study Anything API first with in-memory retrieval for a zero-config smoke.",
            "If the API is already running on another port, pass it with `API_BASE=http://127.0.0.1:<port>`.",
        ],
        "api_health_not_ok": [
            "Open `/v1/health` on the configured API_BASE and inspect the reported service status.",
            "Restart Skill Mode with retrieval enabled, then rerun this verifier.",
        ],
        "retrieval_unhealthy": [
            "For local smoke, set `STUDY_ANYTHING_RETRIEVAL_BACKEND=memory` before starting Skill Mode.",
            "For full stack, enable and verify LanceDB before rerunning retrieval evidence.",
        ],
        "importer_context_failed": [
            "Validate importer output independently with the context-package APIs.",
            "Run `python3 scripts/verify_importer_lesson_flow.py` first to isolate importer/package issues.",
        ],
        "retrieval_rebuild_failed": [
            "Confirm the source session contains imported context package text.",
            "Rerun retrieval rebuild after confirming the retrieval backend is healthy.",
        ],
        "retrieval_search_failed": [
            "Try a broader query with `--query` or rerun with the bundled default importer excerpt.",
            "Inspect `/v1/sessions/<source_session_id>/retrieval/search` locally for ranking details.",
        ],
        "retrieval_quality_failed": [
            "Inspect `/v1/sessions/<source_session_id>/retrieval/eval` locally.",
            "Use the memory backend for first-run smoke before testing LanceDB quality evidence.",
        ],
        "learning_flow_incomplete": [
            "Check lesson session events locally for the first failed workflow stage.",
            "Rerun `python3 scripts/verify_platform_lesson_flow.py` to isolate quiz/grading/synthesis failures.",
        ],
        "quality_eval_failed": [
            "Inspect `/v1/sessions/<lesson_session_id>/agent-eval/quality` locally.",
            "Do not publish the run as evidence until quality status is pass.",
        ],
        "agent_eval_failed": [
            "Run `python3 scripts/verify_agent_eval_flow.py` first to isolate eval failures.",
            "Do not publish raw source, query, or answers while debugging.",
        ],
        "privacy_leak": [
            "Do not share the raw transcript publicly.",
            "Fix the leaking API response or export before using this run as evidence.",
        ],
        "response_schema_invalid": [
            "Confirm the API server and verifier come from the same checkout.",
            "Rerun setup with `python3 scripts/setup_env.py` if the API surface is stale.",
        ],
    }
    return matrix.get(classification, ["Rerun after starting the local API with retrieval enabled."]) + common


def failure_report(exc: BaseException) -> dict[str, Any]:
    diagnostic = sanitize_text(str(exc))
    classification = classify_failure(diagnostic)
    report = {
        "status": "blocked",
        "classification": classification,
        "diagnostic": diagnostic,
        "next_steps": failure_next_steps(classification),
        "source": {
            "verifier": VERIFIER_NAME,
            "api_base": sanitize_text(API_BASE),
            "retrieval_backend": sanitize_text(os.getenv("STUDY_ANYTHING_RETRIEVAL_BACKEND", "")),
        },
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "real_model_keys_included": False,
            "local_absolute_paths_included": False,
        },
    }
    assert_failure_report_redacted(report)
    return report


def format_failure_for_human(report: dict[str, Any]) -> str:
    steps = [
        f"- {sanitize_text(str(step))}"
        for step in report.get("next_steps", [])
        if isinstance(step, str) and step.strip()
    ]
    return "\n".join(
        [
            f"{VERIFIER_NAME} failed:",
            f"classification: {sanitize_text(str(report.get('classification') or 'importer_runtime_retrieval_failed'))}",
            f"Diagnostic: {sanitize_text(str(report.get('diagnostic') or '')) or '(empty)'}",
            "Next steps:",
            *(steps or ["- Start the local API with retrieval enabled, then rerun this verifier."]),
        ]
    )


def format_cli_failure(exc: BaseException) -> str:
    return format_failure_for_human(failure_report(exc))


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"/private/(?:var/)?folders/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise VerificationError(f"Importer runtime retrieval verifier failure report leaked private data: {leaks}")


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
    except (URLError, OSError) as exc:
        raise VerificationError(
            format_api_unreachable(API_BASE, exc, verifier=VERIFIER_NAME)
        ) from exc


def assert_schema(value: Dict[str, Any], schema_version: str, label: str) -> None:
    if value.get("schema_version") != schema_version:
        raise VerificationError(f"{label} returned invalid schema: {value}")


def assert_no_secret_like_text(label: str, value: object) -> None:
    serialized = json.dumps(value, ensure_ascii=False)
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}", serialized):
        raise VerificationError(f"{label} leaked secret-looking token.")
    if re.search(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{12,}", serialized):
        raise VerificationError(f"{label} leaked secret-looking key/value text.")


def first_quiz_item(session: Dict[str, Any]) -> Dict[str, Any]:
    items = session.get("quiz_items") or []
    if not items or not isinstance(items[0], dict):
        raise VerificationError(f"Session did not produce quiz items: {session}")
    return items[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", default=DEFAULT_PRIVATE_USER)
    parser.add_argument("--excerpt", default=DEFAULT_EXCERPT)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--answer", default=DEFAULT_ANSWER)
    args = parser.parse_args()

    health = request("/v1/health")
    if health.get("status") != "ok":
        raise VerificationError(f"Health check failed: {health}")

    retrieval_status = request("/v1/retrieval/status")
    if retrieval_status.get("status") != "healthy":
        raise VerificationError(
            "Retrieval is not healthy. For local smoke, start the API with "
            "STUDY_ANYTHING_RETRIEVAL_BACKEND=memory; for full stack, enable LanceDB."
        )

    importer = request(
        "/v1/importers/example-note-importer/run",
        {
            "inputs": {
                "note_reference": "obsidian://Study Anything/AI PM Lesson 1",
                "title": "AI PM Lesson 1",
                "markdown_excerpt": args.excerpt,
                "obsidian_backlinks": ["AI PM", "Learning Systems", "NotebookLM Bridge"],
            },
            "confirmed_permissions": ["write:context"],
            "include_text": True,
        },
    )
    assert_schema(importer, "importer-run-v1", "importer runtime")
    package = importer.get("package")
    if not isinstance(package, dict):
        raise VerificationError(f"Importer did not return a package object: {importer}")
    assert_schema(package, "learning-context-package-v1", "importer package")

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
        raise VerificationError(f"Importer package did not create a source session: {created_source}")
    source_session_id = str(source_session["session_id"])

    rebuilt = request(f"/v1/sessions/{quote(source_session_id)}/retrieval/rebuild", {})
    if rebuilt.get("indexed_count", 0) < 1:
        raise VerificationError(f"Retrieval rebuild indexed no documents: {rebuilt}")

    search_query = urlencode({"q": args.query, "limit": 3})
    searched = request(f"/v1/sessions/{quote(source_session_id)}/retrieval/search?{search_query}")
    assert_schema(searched, "retrieval-search-v1", "retrieval search")
    if searched.get("status") != "ready" or not searched.get("results"):
        raise VerificationError(f"Retrieval search returned no results: {searched}")

    retrieval_quality = request(
        f"/v1/sessions/{quote(source_session_id)}/retrieval/eval?{search_query}"
    )
    assert_schema(retrieval_quality, "retrieval-quality-eval-v1", "retrieval quality")
    if retrieval_quality.get("status") != "pass":
        raise VerificationError(f"Retrieval quality eval did not pass: {retrieval_quality}")

    created_lesson = request(
        "/v1/sessions/from-retrieval",
        {
            "source_session_id": source_session_id,
            "query": args.query,
            "user_id": f"{args.user_id}-lesson",
            "use_demo_agent": True,
        },
    )
    assert_schema(created_lesson, "retrieval-session-v1", "retrieval session")
    lesson_session = created_lesson.get("session")
    if not isinstance(lesson_session, dict):
        raise VerificationError(f"Retrieval did not create a lesson session: {created_lesson}")
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
        {"answers": {str(quiz["item_id"]): args.answer}},
    )
    if completed.get("stage") != "completed":
        raise VerificationError(f"Lesson did not complete: {completed}")

    quality = request(f"/v1/sessions/{quote(lesson_session_id)}/agent-eval/quality")
    eval_report = request(f"/v1/sessions/{quote(lesson_session_id)}/agent-eval/report")
    obsidian = request(f"/v1/sessions/{quote(lesson_session_id)}/exports/obsidian")
    learning_package = request(f"/v1/sessions/{quote(lesson_session_id)}/exports/learning-package")
    assert_schema(quality, "agent-quality-eval-v1", "quality eval")
    assert_schema(eval_report, "agent-eval-report-v1", "Agent eval report")
    assert_schema(obsidian, "obsidian-markdown-export-v1", "obsidian export")
    assert_schema(learning_package, "learning-package-v1", "learning package")
    if quality.get("status") != "pass":
        raise VerificationError(f"Quality eval did not pass: {quality}")
    if (eval_report.get("native_fast_gate") or {}).get("status") != "pass":
        raise VerificationError(f"Agent eval report native gate failed: {eval_report}")
    assert_no_secret_like_text("importer runtime retrieval flow", {
        "importer": importer,
        "retrieval": searched,
        "retrieval_quality": retrieval_quality,
        "quality": quality,
        "eval_report": eval_report,
        "obsidian": obsidian,
        "learning_package": learning_package,
    })

    print(
        json.dumps(
            {
                "status": "ok",
                "api_base": API_BASE,
                "source_session_id": source_session_id,
                "lesson_session_id": lesson_session_id,
                "retrieval_status": retrieval_status["status"],
                "indexed_count": rebuilt["indexed_count"],
                "retrieval_result_count": len(searched["results"]),
                "retrieval_quality_status": retrieval_quality["status"],
                "lesson_stage": completed["stage"],
                "quality_status": quality["status"],
                "agent_eval_report_schema": eval_report["schema_version"],
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
        report = failure_report(exc)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        print(format_failure_for_human(report), file=sys.stderr)
        sys.exit(1)
