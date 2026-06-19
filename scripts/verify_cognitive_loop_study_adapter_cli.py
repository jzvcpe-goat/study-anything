#!/usr/bin/env python3
"""Verify the Cognitive Loop Study Anything Adapter CLI Lite."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from cognitive_loop_study_adapter_cli import (  # noqa: E402
    CLI_SCHEMA_VERSION,
    build_study_adapter_cli_report,
    dump_json,
)


REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-study-adapter-cli.json"
EVENT_FIXTURE = ROOT / "fixtures" / "cognitive-loop-study-adapter" / "project-event.json"
DECISION_FIXTURE = ROOT / "fixtures" / "cognitive-loop-study-adapter" / "decision-card.json"
GENERATED_AT = "2026-06-19T00:00:00Z"
FORBIDDEN_PATTERNS = [
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bdiff --git\b"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
    re.compile(r"/Users/[^\s\"']+"),
]
FORBIDDEN_LITERALS = [
    "Private raw diff",
    "Private source text",
    "learner answer:",
    "AGENT_ENDPOINT=http",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "This decision should be explained from the cited summary",
]


class StudyAdapterCliVerificationError(RuntimeError):
    """Readable CLI verification failure."""


def build_report() -> dict[str, Any]:
    report = build_study_adapter_cli_report(
        root=ROOT,
        event_path=EVENT_FIXTURE,
        decision_path=DECISION_FIXTURE,
        generated_at=GENERATED_AT,
        objective="Verify platform-Agent callable Study Anything adapter CLI evidence.",
        json_ref="platform/generated/study-anything-cognitive-loop-study-adapter-cli.json",
        html_ref=".cognitive-loop/artifacts/cognitive-loop-study-adapter.html",
    )
    assert_report(report)
    return report


def assert_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != CLI_SCHEMA_VERSION:
        raise StudyAdapterCliVerificationError(f"Unexpected schema: {report.get('schema_version')}")
    if report.get("status") != "pass":
        raise StudyAdapterCliVerificationError("Study Adapter CLI report did not pass.")
    core = report.get("adapter_core") or {}
    if core.get("schema_version") != "cognitive-loop-study-anything-adapter-v1":
        raise StudyAdapterCliVerificationError("Core adapter schema drifted.")
    learning = report.get("learning_status") or {}
    if learning.get("stage") != "completed":
        raise StudyAdapterCliVerificationError("Learning loop did not complete.")
    if learning.get("learning_context_text_included") is not False:
        raise StudyAdapterCliVerificationError("Learning context text must be excluded from CLI report.")
    study_card = report.get("study_card") or {}
    if study_card.get("schema_version") != "study-card-v1":
        raise StudyAdapterCliVerificationError("StudyCard schema drifted.")
    if study_card.get("content_included") is not False:
        raise StudyAdapterCliVerificationError("StudyCard must not include source content.")
    questions = study_card.get("practice_questions")
    if not isinstance(questions, list) or len(questions) < 3:
        raise StudyAdapterCliVerificationError("StudyCard should include at least three practice questions.")
    gaps = report.get("understanding_gaps")
    if not isinstance(gaps, list) or len(gaps) < 2:
        raise StudyAdapterCliVerificationError("Understanding gaps should be present.")
    scribe = report.get("scribe_summary") or {}
    if scribe.get("entry_count", 0) < 1:
        raise StudyAdapterCliVerificationError("Scribe summary should expose a positive entry count.")
    if scribe.get("answers_included") is not False or scribe.get("feedback_included") is not False:
        raise StudyAdapterCliVerificationError("Scribe summary must exclude answers and feedback.")
    agent = report.get("agent_task_coverage") or {}
    required_tasks = {"teach.overview", "teach.glossary", "quiz.generate", "answer.grade", "insight.synthesize"}
    if set(agent.get("observed_tasks") or []) != required_tasks:
        raise StudyAdapterCliVerificationError("Agent task coverage drifted.")
    mastery = report.get("mastery_record") or {}
    if mastery.get("schema_version") != "mastery-record-v1":
        raise StudyAdapterCliVerificationError("MasteryRecord schema drifted.")
    loop = report.get("loop_run") or {}
    if loop.get("schema_version") != "loop-run-v1" or loop.get("status") != "succeeded":
        raise StudyAdapterCliVerificationError("LoopRun schema or status drifted.")
    privacy = report.get("privacy") or {}
    for key in (
        "raw_source_text_included",
        "raw_diff_included",
        "learner_answers_included",
        "grading_feedback_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "model_keys_included",
        "input_file_contents_included",
        "standalone_frontend_required",
    ):
        if privacy.get(key) is not False:
            raise StudyAdapterCliVerificationError(f"Privacy flag must be false: {key}")
    if privacy.get("metadata_only_cognitive_loop_evidence") is not True:
        raise StudyAdapterCliVerificationError("CLI evidence must be metadata-only.")
    assert_no_private_text(report)


def assert_no_private_text(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise StudyAdapterCliVerificationError(f"Study Adapter CLI report leaked private text: {leaks}")


def assert_cli_roundtrip() -> None:
    with tempfile.TemporaryDirectory(prefix="study-adapter-cli-") as temp_name:
        temp_root = Path(temp_name)
        command = [
            sys.executable,
            str(ROOT / "scripts" / "cognitive_loop_cli.py"),
            "--root",
            str(temp_root),
            "study-adapter",
            "--event",
            str(EVENT_FIXTURE),
            "--decision",
            str(DECISION_FIXTURE),
            "--generated-at",
            GENERATED_AT,
            "--html",
        ]
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        json_output = temp_root / ".cognitive-loop" / "events" / "cognitive-loop-study-adapter.json"
        html_output = temp_root / ".cognitive-loop" / "artifacts" / "cognitive-loop-study-adapter.html"
        if not json_output.is_file() or not html_output.is_file():
            raise StudyAdapterCliVerificationError("CLI did not write JSON and HTML outputs.")
        if str(json_output) not in completed.stdout or str(html_output) not in completed.stdout:
            raise StudyAdapterCliVerificationError("CLI did not report written output paths.")
        cli_report = json.loads(json_output.read_text(encoding="utf-8"))
        assert_report(cli_report)
        html = html_output.read_text(encoding="utf-8")
        required = [
            "Cognitive Loop Study Adapter",
            "Study Card",
            "Understanding Gaps",
            "Scribe Summary",
            "Agent Task Coverage",
            "Cognitive Loop Projection",
        ]
        missing = [item for item in required if item not in html]
        if missing:
            raise StudyAdapterCliVerificationError(f"HTML output is missing sections: {missing}")
        assert_no_private_text(html)


def assert_private_title_rejected() -> None:
    decision = json.loads(DECISION_FIXTURE.read_text(encoding="utf-8"))
    decision["title"] = "Private raw diff should not appear in public adapter evidence"
    with tempfile.TemporaryDirectory(prefix="study-adapter-private-") as temp_name:
        decision_path = Path(temp_name) / "decision-card.json"
        decision_path.write_text(dump_json(decision), encoding="utf-8")
        try:
            build_study_adapter_cli_report(
                root=ROOT,
                event_path=EVENT_FIXTURE,
                decision_path=decision_path,
                generated_at=GENERATED_AT,
                objective="Reject private title fixture.",
                json_ref=".cognitive-loop/events/rejected.json",
                html_ref=".cognitive-loop/artifacts/rejected.html",
            )
        except Exception:
            return
    raise StudyAdapterCliVerificationError("Private-looking DecisionCard title was not rejected.")


def check_output(path: Path) -> None:
    expected = dump_json(build_report())
    if not path.is_file():
        raise StudyAdapterCliVerificationError(
            "Study Adapter CLI report is missing. "
            "Run: .venv/bin/python scripts/verify_cognitive_loop_study_adapter_cli.py --write"
        )
    if path.read_text(encoding="utf-8") != expected:
        raise StudyAdapterCliVerificationError(
            "Study Adapter CLI report is stale. "
            "Run: .venv/bin/python scripts/verify_cognitive_loop_study_adapter_cli.py --write"
        )
    assert_cli_roundtrip()
    assert_private_title_rejected()
    print("ok    Cognitive Loop Study Adapter CLI report is up to date")


def write_output(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(build_report()), encoding="utf-8")
    assert_cli_roundtrip()
    assert_private_title_rejected()
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=REPORT)
    args = parser.parse_args()

    if args.write:
        write_output(args.output)
    if args.check:
        check_output(args.output)
    if not args.write and not args.check:
        print(dump_json(build_report()), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"verify_cognitive_loop_study_adapter_cli failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
