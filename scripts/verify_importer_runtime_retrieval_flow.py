#!/usr/bin/env python3
"""Verify importer runtime -> retrieval -> lesson -> quality -> export flow."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


API_BASE = os.getenv("API_BASE", os.getenv("STUDY_ANYTHING_API_BASE", "http://127.0.0.1:8000")).rstrip("/")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("IMPORTER_RETRIEVAL_TIMEOUT_SECONDS", "15"))


class VerificationError(RuntimeError):
    """Readable smoke failure."""


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
    parser.add_argument("--user-id", default="importer-runtime-retrieval-smoke-user")
    parser.add_argument(
        "--excerpt",
        default=(
            "AI product learning improves when a learner connects overall product intent, "
            "technical vocabulary, source evidence, feedback, and spaced review."
        ),
    )
    parser.add_argument("--query", default="AI product learning feedback vocabulary")
    parser.add_argument("--answer", default="The lesson connects source evidence to feedback and review.")
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
    obsidian = request(f"/v1/sessions/{quote(lesson_session_id)}/exports/obsidian")
    learning_package = request(f"/v1/sessions/{quote(lesson_session_id)}/exports/learning-package")
    assert_schema(quality, "agent-quality-eval-v1", "quality eval")
    assert_schema(obsidian, "obsidian-markdown-export-v1", "obsidian export")
    assert_schema(learning_package, "learning-package-v1", "learning package")
    if quality.get("status") != "pass":
        raise VerificationError(f"Quality eval did not pass: {quality}")
    assert_no_secret_like_text("importer runtime retrieval flow", {
        "importer": importer,
        "retrieval": searched,
        "quality": quality,
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
                "lesson_stage": completed["stage"],
                "quality_status": quality["status"],
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
        print(f"verify_importer_runtime_retrieval_flow failed: {exc}", file=sys.stderr)
        sys.exit(1)
