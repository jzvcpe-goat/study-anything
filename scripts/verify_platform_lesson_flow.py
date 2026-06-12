#!/usr/bin/env python3
"""Verify a platform agent can complete one enriched Study Anything lesson."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


API_BASE = os.getenv("API_BASE", os.getenv("STUDY_ANYTHING_API_BASE", "http://127.0.0.1:8000")).rstrip("/")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("PLATFORM_LESSON_TIMEOUT_SECONDS", "15"))


class LessonVerificationError(RuntimeError):
    """Readable lesson-smoke failure."""


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
        raise LessonVerificationError(f"API returned {exc.code} for {path}: {detail}") from exc
    except URLError as exc:
        raise LessonVerificationError(f"Cannot reach Study Anything at {API_BASE}: {exc}") from exc


def assert_schema(value: Dict[str, Any], schema_version: str, label: str) -> None:
    if value.get("schema_version") != schema_version:
        raise LessonVerificationError(f"{label} returned invalid schema: {value}")


def assert_no_leaks(label: str, value: object, forbidden: list[str]) -> None:
    serialized = json.dumps(value, ensure_ascii=False)
    leaks = [fragment for fragment in forbidden if fragment and fragment in serialized]
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9]{16,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise LessonVerificationError(f"{label} leaked private data: {leaks}")


def main() -> None:
    health = request("/v1/health")
    if health.get("status") != "ok":
        raise LessonVerificationError(f"Health check failed: {health}")

    private_source_text = "Private lesson source text about retrieval practice must not leak into redacted evidence."
    private_enrichment_text = "Private video-slice enrichment about desirable difficulty must not leak into shared evidence."
    private_answer = "Private learner answer: retrieval practice strengthens recall by forcing active reconstruction."
    session = request(
        "/v1/sessions",
        {
            "user_id": "platform-lesson-smoke-user",
            "track": "ACADEMIC",
            "use_demo_agent": True,
        },
    )
    session_id = session["session_id"]
    request(
        f"/v1/sessions/{quote(session_id)}/reading",
        {
            "source_type": "local_text",
            "reference": "demo://platform-lesson",
            "title": "Platform Lesson Smoke",
            "text": private_source_text,
        },
    )
    enrichment = request(
        f"/v1/sessions/{quote(session_id)}/enrichment",
        {
            "title": "Platform Lesson Enrichment",
            "items": [
                {
                    "source_type": "video_slice",
                    "reference": "video://platform-lesson/clip-1",
                    "title": "Desirable Difficulty Clip",
                    "locator": "00:00:05-00:00:42",
                    "text": private_enrichment_text,
                    "provenance": {
                        "collector": "platform-agent-smoke",
                        "capture_method": "video_transcript_slice",
                        "source_owner": "user",
                    },
                    "redaction_policy": "reference_only",
                    "metadata": {"collector": "platform-agent-smoke"},
                }
            ],
        },
    )
    assert_schema(enrichment, "learning-enrichment-v1", "enrichment")
    assert_no_leaks("enrichment response", enrichment, [private_enrichment_text])

    teaching = request(
        f"/v1/sessions/{quote(session_id)}/teaching-layers",
        {
            "layers": ["overview", "glossary"],
            "language": "zh",
            "level": "beginner",
        },
    )
    assert_schema(teaching, "teaching-layers-v1", "teaching layers")
    layer_names = {layer.get("layer") for layer in teaching.get("layers", []) if isinstance(layer, dict)}
    if not {"overview", "glossary"}.issubset(layer_names):
        raise LessonVerificationError(f"Teaching layers missing overview/glossary: {teaching}")

    running = request(f"/v1/sessions/{quote(session_id)}/run", {})
    quiz_items = running.get("quiz_items") or []
    if not quiz_items:
        raise LessonVerificationError(f"Run did not produce quiz items: {running}")
    quiz_id = quiz_items[0]["item_id"]

    completed = request(
        f"/v1/sessions/{quote(session_id)}/answers",
        {"answers": {quiz_id: private_answer}},
    )
    if completed.get("stage") != "completed":
        raise LessonVerificationError(f"Lesson did not complete: {completed}")

    audit = request(f"/v1/sessions/{quote(session_id)}/agent-audit")
    artifact = request(f"/v1/sessions/{quote(session_id)}/agent-eval/artifact")
    quality = request(f"/v1/sessions/{quote(session_id)}/agent-eval/quality")
    obsidian = request(f"/v1/sessions/{quote(session_id)}/exports/obsidian")
    package = request(f"/v1/sessions/{quote(session_id)}/exports/learning-package")
    enrichment_artifact = request(f"/v1/sessions/{quote(session_id)}/exports/enrichment-artifact")

    assert_schema(audit, "agent-audit-v1", "agent audit")
    assert_schema(artifact, "agent-eval-artifact-v1", "agent eval artifact")
    assert_schema(quality, "agent-quality-eval-v1", "quality eval")
    assert_schema(obsidian, "obsidian-markdown-export-v1", "obsidian export")
    assert_schema(package, "learning-package-v1", "learning package")
    assert_schema(enrichment_artifact, "learning-enrichment-artifact-v1", "enrichment artifact")
    if audit.get("status") != "verified":
        raise LessonVerificationError(f"Agent audit did not verify: {audit}")
    if quality.get("status") != "pass":
        raise LessonVerificationError(f"Quality eval did not pass: {quality}")

    redacted_forbidden = [
        private_source_text,
        private_enrichment_text,
        private_answer,
        "platform-lesson-smoke-user",
        "127.0.0.1:8787",
        "OPENAI_API_KEY",
    ]
    assert_no_leaks("agent audit", audit, redacted_forbidden)
    assert_no_leaks("agent eval artifact", artifact, redacted_forbidden)
    assert_no_leaks("quality eval", quality, redacted_forbidden)
    assert_no_leaks("learning package raw source boundary", package, [private_source_text, private_enrichment_text])
    assert_no_leaks("obsidian raw source boundary", obsidian, [private_source_text, private_enrichment_text])
    assert_no_leaks(
        "enrichment artifact raw source boundary",
        enrichment_artifact,
        [private_source_text, private_enrichment_text, private_answer],
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "api_base": API_BASE,
                "session_id": session_id,
                "stage": completed["stage"],
                "agent_audit_status": audit["status"],
                "quality_status": quality["status"],
                "obsidian_schema": obsidian["schema_version"],
                "learning_package_schema": package["schema_version"],
                "enrichment_artifact_schema": enrichment_artifact["schema_version"],
                "learning_package_consumers": package["intended_consumers"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_platform_lesson_flow failed: {exc}", file=sys.stderr)
        sys.exit(1)
