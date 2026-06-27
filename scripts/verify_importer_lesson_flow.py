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


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import format_api_unreachable, resolve_api_base, verifier_name_from_file


API_BASE = resolve_api_base()
REQUEST_TIMEOUT_SECONDS = int(os.getenv("IMPORTER_LESSON_TIMEOUT_SECONDS", "15"))
DEFAULT_FIXTURE = Path("fixtures/notebooklm/notebooklm-style-context-package.json")
VERIFIER_NAME = verifier_name_from_file(__file__)
DEFAULT_PRIVATE_ANSWER = "The lesson should connect source-bound ideas to review."
DEFAULT_PRIVATE_USER = "importer-lesson-smoke-user"
FORBIDDEN_LITERALS = (
    DEFAULT_PRIVATE_ANSWER,
    DEFAULT_PRIVATE_USER,
    "Private fixture web excerpt",
    "Private fixture document excerpt",
    "Private fixture video excerpt",
    "Private fixture app context excerpt",
    "Private fixture markdown excerpt",
    "Private fixture obsidian excerpt",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
)


class ImporterLessonVerificationError(RuntimeError):
    """Readable importer-smoke failure."""


def sanitize_text(value: str | bytes | None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    text = text.replace(DEFAULT_PRIVATE_ANSWER, "<private-answer>")
    text = text.replace(DEFAULT_PRIVATE_USER, "<private-user>")
    text = re.sub(r"(?i)private fixture [^:]{1,80} excerpt:[^\"'\n.]*\.?", "<private-fixture-text>", text)
    text = re.sub(r"(?i)private [^\"'\n:<]{0,120}(?:answer|source|context|excerpt)[^\"'\n.<]*\.?", "<private-text>", text)
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
    if "cannot read fixture" in lowered or "fixture is not valid json" in lowered:
        return "fixture_unavailable"
    if "health check failed" in lowered:
        return "api_health_not_ok"
    if "returned invalid schema" in lowered:
        return "response_schema_invalid"
    if "context package did not validate" in lowered or "import did not return session" in lowered:
        return "context_package_failed"
    if "imported source types mismatch" in lowered:
        return "context_package_failed"
    if "did not produce quiz items" in lowered or "session did not complete" in lowered:
        return "learning_flow_incomplete"
    if "quality eval did not pass" in lowered or "agent eval report native gate failed" in lowered:
        return "agent_eval_failed"
    if "leaked private data" in lowered or "raw fixture boundary" in lowered or "strict fixture boundary" in lowered:
        return "privacy_leak"
    if "notebooklm bridge" in lowered or "obsidian export missing backlink" in lowered:
        return "export_contract_failed"
    return "importer_lesson_flow_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "./scripts/launch_skill_mode.sh",
        f"API_BASE={API_BASE} python3 scripts/verify_importer_lesson_flow.py",
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
        "fixture_unavailable": [
            "Run this command from the repository root so the NotebookLM fixture path resolves.",
            "If using a custom fixture, pass it explicitly with `--fixture <path>`.",
        ],
        "api_health_not_ok": [
            "Open `/v1/health` on the configured API_BASE and inspect the reported service status.",
            "Restart Skill Mode, then rerun the importer lesson verifier.",
        ],
        "response_schema_invalid": [
            "Confirm the API server and verifier come from the same checkout.",
            "Rerun setup with `python3 scripts/setup_env.py` if the API surface is stale.",
        ],
        "context_package_failed": [
            "Validate the Learning Context Package independently with the context-package API.",
            "Use the bundled NotebookLM fixture first before testing a custom export.",
        ],
        "learning_flow_incomplete": [
            "Check session events locally for the first failed workflow stage.",
            "Rerun after confirming quiz generation and answer grading are healthy.",
        ],
        "agent_eval_failed": [
            "Run `python3 scripts/verify_agent_eval_flow.py` first to isolate eval failures.",
            "Do not publish raw fixture text or learner answers while debugging.",
        ],
        "privacy_leak": [
            "Do not share the raw transcript publicly.",
            "Fix the leaking import/export boundary before using this run as evidence.",
        ],
        "export_contract_failed": [
            "Check Obsidian, NotebookLM bridge, learning package, and second-brain export contracts locally.",
            "Rerun after generated platform assets are in sync with the API.",
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
            "raw_fixture_text_included": False,
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
            f"classification: {sanitize_text(str(report.get('classification') or 'importer_lesson_flow_failed'))}",
            f"Diagnostic: {sanitize_text(str(report.get('diagnostic') or '')) or '(empty)'}",
            "Next steps:",
            *(steps or ["- Run ./scripts/launch_skill_mode.sh, then rerun this verifier."]),
        ]
    )


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"(?i)private fixture [^\"']+", serialized):
        leaks.append("private fixture text")
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"/private/(?:var/)?folders/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise ImporterLessonVerificationError(
            f"Importer lesson verifier failure report leaked private data: {leaks}"
        )


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
    except (URLError, OSError) as exc:
        raise ImporterLessonVerificationError(
            format_api_unreachable(API_BASE, exc, verifier=VERIFIER_NAME)
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
    parser.add_argument("--user-id", default=DEFAULT_PRIVATE_USER)
    parser.add_argument("--answer", default=DEFAULT_PRIVATE_ANSWER)
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
    eval_report = request(f"/v1/sessions/{quote(session_id)}/agent-eval/report")
    obsidian = request(f"/v1/sessions/{quote(session_id)}/exports/obsidian")
    package = request(f"/v1/sessions/{quote(session_id)}/exports/learning-package")
    second_brain = request(f"/v1/sessions/{quote(session_id)}/exports/second-brain-handoff")
    assert_schema(quality, "agent-quality-eval-v1", "quality eval")
    assert_schema(eval_report, "agent-eval-report-v1", "Agent eval report")
    assert_schema(obsidian, "obsidian-markdown-export-v1", "obsidian export")
    assert_schema(package, "learning-package-v1", "learning package")
    assert_schema(second_brain, "second-brain-handoff-v1", "second-brain handoff")
    if quality.get("status") != "pass":
        raise ImporterLessonVerificationError(f"Quality eval did not pass: {quality}")
    if (eval_report.get("native_fast_gate") or {}).get("status") != "pass":
        raise ImporterLessonVerificationError(f"Agent eval report native gate failed: {eval_report}")
    if package.get("notebooklm_bridge", {}).get("raw_source_text_included") is not False:
        raise ImporterLessonVerificationError(f"NotebookLM bridge raw-source flag is unsafe: {package}")
    if "notebooklm_bridge" not in package.get("intended_consumers", []):
        raise ImporterLessonVerificationError("Learning package is missing notebooklm_bridge consumer.")
    markdown = str(obsidian.get("markdown") or "")
    for expected_link in ("[[AI PM]]", "[[Learning Systems]]", "[[NotebookLM Bridge]]"):
        if expected_link not in markdown:
            raise ImporterLessonVerificationError(f"Obsidian export missing backlink {expected_link}.")
    assert_no_leaks("obsidian raw fixture boundary", obsidian, private_fragments)
    assert_no_leaks("Agent eval report raw fixture boundary", eval_report, private_fragments + [args.answer])
    assert_no_leaks("learning-package raw fixture boundary", package, private_fragments)
    assert_no_leaks("second-brain strict fixture boundary", second_brain, private_fragments + [args.answer])

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
                "agent_eval_report_schema": eval_report["schema_version"],
                "obsidian_schema": obsidian["schema_version"],
                "learning_package_schema": package["schema_version"],
                "second_brain_schema": second_brain["schema_version"],
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
        report = failure_report(exc)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        print(format_failure_for_human(report), file=sys.stderr)
        sys.exit(1)
