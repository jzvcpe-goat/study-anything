#!/usr/bin/env python3
"""Verify a platform agent can complete one enriched Study Anything lesson."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import format_api_unreachable, resolve_api_base, verifier_name_from_file


API_BASE = resolve_api_base()
REQUEST_TIMEOUT_SECONDS = int(os.getenv("PLATFORM_LESSON_TIMEOUT_SECONDS", "15"))
VERIFIER_NAME = verifier_name_from_file(__file__)
PRIVATE_SOURCE_TEXT = "Private lesson source text about retrieval practice must not leak into redacted evidence."
PRIVATE_ENRICHMENT_TEXT = "Private video-slice enrichment about desirable difficulty must not leak into shared evidence."
PRIVATE_ANSWER = "Private learner answer: retrieval practice strengthens recall by forcing active reconstruction."
PRIVATE_USER = "platform-lesson-smoke-user"
PRIVATE_REFERENCE = "demo://platform-lesson"
PRIVATE_TITLE = "Platform Lesson Smoke"
PRIVATE_ENRICHMENT_TITLE = "Platform Lesson Enrichment"
FORBIDDEN_LITERALS = (
    PRIVATE_SOURCE_TEXT,
    PRIVATE_ENRICHMENT_TEXT,
    PRIVATE_ANSWER,
    PRIVATE_USER,
    PRIVATE_REFERENCE,
    PRIVATE_TITLE,
    PRIVATE_ENRICHMENT_TITLE,
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
)


class LessonVerificationError(RuntimeError):
    """Readable lesson-smoke failure."""


def sanitize_text(value: str | bytes | None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    replacements = {
        PRIVATE_SOURCE_TEXT: "<private-source-text>",
        PRIVATE_ENRICHMENT_TEXT: "<private-enrichment-text>",
        PRIVATE_ANSWER: "<private-answer>",
        PRIVATE_USER: "<private-user>",
        PRIVATE_REFERENCE: "<private-reference>",
        PRIVATE_TITLE: "<private-title>",
        PRIVATE_ENRICHMENT_TITLE: "<private-enrichment-title>",
    }
    for literal, replacement in replacements.items():
        text = text.replace(literal, replacement)
    text = re.sub(r"(?i)private lesson source text[^\"'.]*", "<private-source-text>", text)
    text = re.sub(r"(?i)private video-slice enrichment[^\"'.]*", "<private-enrichment-text>", text)
    text = re.sub(r"(?i)private learner answer[^\"'.]*", "<private-answer>", text)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", text)
    text = re.sub(r"/Users/[^\s\"'?&]+", "<local-path>", text)
    text = re.sub(r"/private/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", r"\1=<redacted>", text)
    text = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "sk-<redacted>", text)
    text = re.sub(r"([?&](?:api[_-]?key|token|secret)=)[^&\s\"']+", r"\1<redacted>", text, flags=re.IGNORECASE)
    return text.strip()[:1600]


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
    if "cannot reach study anything" in lowered or "connection refused" in lowered or "urlopen error" in lowered:
        return "api_unreachable"
    if "health check failed" in lowered:
        return "api_health_not_ok"
    if "returned invalid schema" in lowered:
        return "response_schema_invalid"
    if "leaked private data" in lowered or "raw source boundary" in lowered or "privacy boundary" in lowered:
        return "privacy_leak"
    if "teaching layers missing" in lowered:
        return "teaching_layer_failed"
    if "did not produce quiz items" in lowered or "lesson did not complete" in lowered:
        return "learning_flow_incomplete"
    if "agent audit did not verify" in lowered:
        return "agent_audit_failed"
    if "quality eval did not pass" in lowered or "agent eval report native gate failed" in lowered:
        return "agent_eval_failed"
    return "platform_lesson_flow_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "./scripts/launch_skill_mode.sh",
        f"API_BASE={API_BASE} python3 scripts/verify_platform_lesson_flow.py",
        "python3 scripts/diagnose_adoption.py",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run the verifier from a normal terminal or host shell that permits localhost sockets.",
            "If this came from Codex or another sandboxed Agent, collect this blocked report and rerun outside the sandbox.",
        ],
        "api_unreachable": [
            "Start the Study Anything API first with `./scripts/launch_skill_mode.sh`.",
            "If the API is already running on another port, pass it with `API_BASE=http://127.0.0.1:<port>`.",
        ],
        "api_health_not_ok": [
            "Open `/v1/health` on the configured API_BASE and inspect the reported service status.",
            "Restart Skill Mode, then rerun the platform lesson verifier.",
        ],
        "response_schema_invalid": [
            "Confirm the API server and verifier come from the same checkout.",
            "Rerun setup with `python3 scripts/setup_env.py` if the API surface is stale.",
        ],
        "privacy_leak": [
            "Do not share the raw transcript publicly.",
            "Fix the leaking export/artifact boundary before using this run as evidence.",
        ],
        "teaching_layer_failed": [
            "Confirm the configured Agent supports `teach.overview` and `teach.glossary`.",
            "Retry with the bundled fake agent path before validating a custom Agent.",
        ],
        "learning_flow_incomplete": [
            "Check session events locally for the first failed workflow stage.",
            "Rerun after confirming quiz generation and answer grading are healthy.",
        ],
        "agent_audit_failed": [
            "Inspect `/v1/sessions/<session_id>/agent-audit` locally for observed task coverage.",
            "Do not publish raw source, enrichment, or answers while debugging.",
        ],
        "agent_eval_failed": [
            "Inspect the local agent-eval report; native quality gates must pass before release evidence is valid.",
            "Rerun the basic `verify_agent_eval_flow.py` first to isolate eval failures.",
        ],
    }
    return matrix.get(classification, ["Rerun after starting the local API."]) + common


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
        },
        "privacy": {
            "raw_source_text_included": False,
            "raw_enrichment_text_included": False,
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
            f"classification: {sanitize_text(str(report.get('classification') or 'platform_lesson_flow_failed'))}",
            f"Diagnostic: {sanitize_text(str(report.get('diagnostic') or '')) or '(empty)'}",
            "Next steps:",
            *(steps or ["- Run ./scripts/launch_skill_mode.sh, then rerun this verifier."]),
        ]
    )


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
        raise LessonVerificationError(f"Platform lesson verifier failure report leaked private data: {leaks}")


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
    except (URLError, OSError) as exc:
        raise LessonVerificationError(
            format_api_unreachable(API_BASE, exc, verifier=VERIFIER_NAME)
        ) from exc


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

    session = request(
        "/v1/sessions",
        {
            "user_id": PRIVATE_USER,
            "track": "ACADEMIC",
            "use_demo_agent": True,
        },
    )
    session_id = session["session_id"]
    request(
        f"/v1/sessions/{quote(session_id)}/reading",
        {
            "source_type": "local_text",
            "reference": PRIVATE_REFERENCE,
            "title": PRIVATE_TITLE,
            "text": PRIVATE_SOURCE_TEXT,
        },
    )
    enrichment = request(
        f"/v1/sessions/{quote(session_id)}/enrichment",
        {
            "title": PRIVATE_ENRICHMENT_TITLE,
            "items": [
                {
                    "source_type": "video_slice",
                    "reference": "video://platform-lesson/clip-1",
                    "title": "Desirable Difficulty Clip",
                    "locator": "00:00:05-00:00:42",
                    "text": PRIVATE_ENRICHMENT_TEXT,
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
    assert_no_leaks("enrichment response", enrichment, [PRIVATE_ENRICHMENT_TEXT])

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
        {"answers": {quiz_id: PRIVATE_ANSWER}},
    )
    if completed.get("stage") != "completed":
        raise LessonVerificationError(f"Lesson did not complete: {completed}")

    audit = request(f"/v1/sessions/{quote(session_id)}/agent-audit")
    artifact = request(f"/v1/sessions/{quote(session_id)}/agent-eval/artifact")
    quality = request(f"/v1/sessions/{quote(session_id)}/agent-eval/quality")
    eval_report = request(f"/v1/sessions/{quote(session_id)}/agent-eval/report")
    obsidian = request(f"/v1/sessions/{quote(session_id)}/exports/obsidian")
    package = request(f"/v1/sessions/{quote(session_id)}/exports/learning-package")
    enrichment_artifact = request(f"/v1/sessions/{quote(session_id)}/exports/enrichment-artifact")
    second_brain = request(f"/v1/sessions/{quote(session_id)}/exports/second-brain-handoff")

    assert_schema(audit, "agent-audit-v1", "agent audit")
    assert_schema(artifact, "agent-eval-artifact-v1", "agent eval artifact")
    assert_schema(quality, "agent-quality-eval-v1", "quality eval")
    assert_schema(eval_report, "agent-eval-report-v1", "Agent eval report")
    assert_schema(obsidian, "obsidian-markdown-export-v1", "obsidian export")
    assert_schema(package, "learning-package-v1", "learning package")
    assert_schema(enrichment_artifact, "learning-enrichment-artifact-v1", "enrichment artifact")
    assert_schema(second_brain, "second-brain-handoff-v1", "second-brain handoff")
    if audit.get("status") != "verified":
        raise LessonVerificationError(f"Agent audit did not verify: {audit}")
    if quality.get("status") != "pass":
        raise LessonVerificationError(f"Quality eval did not pass: {quality}")
    if (eval_report.get("native_fast_gate") or {}).get("status") != "pass":
        raise LessonVerificationError(f"Agent eval report native gate failed: {eval_report}")

    redacted_forbidden = [
        PRIVATE_SOURCE_TEXT,
        PRIVATE_ENRICHMENT_TEXT,
        PRIVATE_ANSWER,
        PRIVATE_USER,
        "127.0.0.1:8787",
        "OPENAI_API_KEY",
    ]
    assert_no_leaks("agent audit", audit, redacted_forbidden)
    assert_no_leaks("agent eval artifact", artifact, redacted_forbidden)
    assert_no_leaks("quality eval", quality, redacted_forbidden)
    assert_no_leaks("Agent eval report", eval_report, redacted_forbidden)
    assert_no_leaks("learning package raw source boundary", package, [PRIVATE_SOURCE_TEXT, PRIVATE_ENRICHMENT_TEXT])
    assert_no_leaks("obsidian raw source boundary", obsidian, [PRIVATE_SOURCE_TEXT, PRIVATE_ENRICHMENT_TEXT])
    assert_no_leaks(
        "enrichment artifact raw source boundary",
        enrichment_artifact,
        [PRIVATE_SOURCE_TEXT, PRIVATE_ENRICHMENT_TEXT, PRIVATE_ANSWER],
    )
    assert_no_leaks(
        "second-brain handoff strict privacy boundary",
        second_brain,
        [PRIVATE_SOURCE_TEXT, PRIVATE_ENRICHMENT_TEXT, PRIVATE_ANSWER],
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
                "agent_eval_report_schema": eval_report["schema_version"],
                "obsidian_schema": obsidian["schema_version"],
                "learning_package_schema": package["schema_version"],
                "enrichment_artifact_schema": enrichment_artifact["schema_version"],
                "second_brain_schema": second_brain["schema_version"],
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
        report = failure_report(exc)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        print(format_failure_for_human(report), file=sys.stderr)
        sys.exit(1)
