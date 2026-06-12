#!/usr/bin/env python3
"""Verify importer -> enrichment -> lesson -> quality -> export flow."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_BASE = os.getenv("API_BASE", os.getenv("STUDY_ANYTHING_API_BASE", "http://127.0.0.1:8000")).rstrip("/")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("IMPORTER_LESSON_TIMEOUT_SECONDS", "15"))
DEFAULT_FIXTURE = Path("fixtures/notebooklm/notebooklm-style-context-package.json")


class ImporterLessonVerificationError(RuntimeError):
    """Readable importer-smoke failure."""


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
        raise ImporterLessonVerificationError(
            f"API returned {exc.code} for {path}: {detail}"
        ) from exc
    except URLError as exc:
        raise ImporterLessonVerificationError(
            f"Cannot reach Study Anything at {API_BASE}: {exc}"
        ) from exc


def load_fixture(path: Path) -> Dict[str, Any]:
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ImporterLessonVerificationError(f"Cannot read fixture {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ImporterLessonVerificationError(f"Fixture is not valid JSON: {exc}") from exc
    if not isinstance(values, dict):
        raise ImporterLessonVerificationError("Fixture must contain a JSON object.")
    return values


def assert_schema(value: Dict[str, Any], schema_version: str, label: str) -> None:
    if value.get("schema_version") != schema_version:
        raise ImporterLessonVerificationError(f"{label} returned invalid schema: {value}")


def assert_no_leaks(label: str, value: object, forbidden: list[str]) -> None:
    serialized = json.dumps(value, ensure_ascii=False)
    leaks = [fragment for fragment in forbidden if fragment and fragment in serialized]
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise ImporterLessonVerificationError(f"{label} leaked private data: {leaks}")


def first_quiz_item(session: Dict[str, Any]) -> Dict[str, Any]:
    items = session.get("quiz_items") or []
    if not items or not isinstance(items[0], dict):
        raise ImporterLessonVerificationError(f"Session did not produce quiz items: {session}")
    return items[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--user-id", default="importer-lesson-smoke-user")
    parser.add_argument("--answer", default="The lesson should connect source-bound ideas to review.")
    args = parser.parse_args()

    health = request("/v1/health")
    if health.get("status") != "ok":
        raise ImporterLessonVerificationError(f"Health check failed: {health}")

    fixture = load_fixture(args.fixture)
    private_fragments = [
        str(item.get("text") or "")
        for item in fixture.get("items", [])
        if isinstance(item, dict)
    ]
    validation = request("/v1/context-packages/validate", {"package": fixture})
    assert_schema(validation, "learning-context-package-v1", "context package validation")
    if validation.get("status") != "valid":
        raise ImporterLessonVerificationError(f"Context package did not validate: {validation}")
    assert_no_leaks("context package validation summary", validation, private_fragments)

    created = request(
        "/v1/sessions/from-context-package",
        {
            "user_id": args.user_id,
            "use_demo_agent": True,
            "package": fixture,
        },
    )
    assert_schema(created, "learning-context-package-v1", "context package import")
    session = created.get("session")
    if not isinstance(session, dict):
        raise ImporterLessonVerificationError(f"Import did not return session: {created}")
    session_id = str(session["session_id"])
    source_types = {
        item.get("source_type")
        for item in session.get("enrichment_items", [])
        if isinstance(item, dict)
    }
    expected_source_types = {
        "web",
        "document",
        "video_slice",
        "app_context",
        "markdown_note",
        "obsidian_note",
    }
    if source_types != expected_source_types:
        raise ImporterLessonVerificationError(f"Imported source types mismatch: {source_types}")

    teaching = request(
        f"/v1/sessions/{quote(session_id)}/teaching-layers",
        {
            "layers": ["overview", "glossary"],
            "language": "zh",
            "level": "beginner",
        },
    )
    assert_schema(teaching, "teaching-layers-v1", "teaching layers")
    running = request(f"/v1/sessions/{quote(session_id)}/run", {})
    quiz = first_quiz_item(running)
    completed = request(
        f"/v1/sessions/{quote(session_id)}/answers",
        {"answers": {str(quiz["item_id"]): args.answer}},
    )
    if completed.get("stage") != "completed":
        raise ImporterLessonVerificationError(f"Session did not complete: {completed}")

    quality = request(f"/v1/sessions/{quote(session_id)}/agent-eval/quality")
    obsidian = request(f"/v1/sessions/{quote(session_id)}/exports/obsidian")
    package = request(f"/v1/sessions/{quote(session_id)}/exports/learning-package")
    assert_schema(quality, "agent-quality-eval-v1", "quality eval")
    assert_schema(obsidian, "obsidian-markdown-export-v1", "obsidian export")
    assert_schema(package, "learning-package-v1", "learning package")
    if quality.get("status") != "pass":
        raise ImporterLessonVerificationError(f"Quality eval did not pass: {quality}")
    if package.get("notebooklm_bridge", {}).get("raw_source_text_included") is not False:
        raise ImporterLessonVerificationError(f"NotebookLM bridge raw-source flag is unsafe: {package}")
    if "notebooklm_bridge" not in package.get("intended_consumers", []):
        raise ImporterLessonVerificationError("Learning package is missing notebooklm_bridge consumer.")
    markdown = str(obsidian.get("markdown") or "")
    for expected_link in ("[[AI PM]]", "[[Learning Systems]]", "[[NotebookLM Bridge]]"):
        if expected_link not in markdown:
            raise ImporterLessonVerificationError(f"Obsidian export missing backlink {expected_link}.")
    assert_no_leaks("obsidian raw fixture boundary", obsidian, private_fragments)
    assert_no_leaks("learning-package raw fixture boundary", package, private_fragments)

    print(
        json.dumps(
            {
                "status": "ok",
                "api_base": API_BASE,
                "fixture": str(args.fixture),
                "session_id": session_id,
                "source_types": sorted(source_types),
                "stage": completed["stage"],
                "quality_status": quality["status"],
                "obsidian_schema": obsidian["schema_version"],
                "learning_package_schema": package["schema_version"],
                "notebooklm_bridge_status": package["notebooklm_bridge"]["status"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_importer_lesson_flow failed: {exc}", file=sys.stderr)
        sys.exit(1)
