#!/usr/bin/env python3
"""Verify the Cognitive Loop -> Study Anything Learning Adapter bridge."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core.cognitive_loop_learning_adapter import (  # noqa: E402
    COGNITIVE_LOOP_STUDY_ADAPTER_SCHEMA_VERSION,
    run_cognitive_loop_study_adapter,
)


REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-study-anything-adapter.json"
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


class StudyAnythingAdapterVerificationError(RuntimeError):
    """Readable adapter verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def fixture_project_event() -> dict[str, Any]:
    return {
        "schema_version": "project-event-v1",
        "event_id": "event-study-adapter-001",
        "project_id": "cognitive-loop-demo",
        "actor": "agent",
        "event_type": "git_diff_changed",
        "summary": "A metadata-only watcher noticed a risky adapter boundary change.",
        "timestamp": GENERATED_AT,
        "target": "apps/api/study_anything/core/cognitive_loop_learning_adapter.py",
        "refs": [
            "path:apps/api/study_anything/core/cognitive_loop_learning_adapter.py",
            "evidence:metadata-only",
        ],
        "sensitivity": "internal",
    }


def fixture_decision_card() -> dict[str, Any]:
    return {
        "schema_version": "decision-card-v1",
        "decision_id": "decision-study-adapter-001",
        "project_id": "cognitive-loop-demo",
        "title": "Route risky project changes through Study Anything mastery checks",
        "status": "approved",
        "summary": (
            "Use Study Anything as the Cognitive Loop learning adapter so operators "
            "can prove mastery before risky project changes proceed."
        ),
        "event_ids": ["event-study-adapter-001"],
        "evidence_refs": [
            "path:apps/api/study_anything/core/cognitive_loop_learning_adapter.py",
            "check:python3 scripts/verify_cognitive_loop_study_anything_adapter.py --check",
        ],
        "risk": {
            "level": "high",
            "score": 0.82,
            "reasons": [
                "The adapter crosses project operations and human learning gates.",
                "A bad bridge could leak private source or answers into public evidence.",
            ],
        },
        "human_mastery_gate": {
            "required": True,
            "status": "approved",
            "reason": "Operator completed a source-bound learning check.",
        },
        "verification": {
            "status": "passed",
            "commands": [
                "python3 scripts/verify_cognitive_loop_study_anything_adapter.py --check",
                "./scripts/release_check.sh",
            ],
        },
        "rollback": {
            "strategy": "disable_study_anything_adapter_bridge",
            "checkpoint_ref": "git:main",
        },
    }


def build_report() -> dict[str, Any]:
    report = run_cognitive_loop_study_adapter(
        project_event=fixture_project_event(),
        decision_card=fixture_decision_card(),
        generated_at=GENERATED_AT,
    )
    assert_report(report)
    return report


def assert_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != COGNITIVE_LOOP_STUDY_ADAPTER_SCHEMA_VERSION:
        raise StudyAnythingAdapterVerificationError(f"Unexpected schema: {report.get('schema_version')}")
    if report.get("status") != "pass":
        raise StudyAnythingAdapterVerificationError("Adapter report did not pass.")

    context = report.get("learning_context") or {}
    if context.get("schema_version") != "learning-context-package-v1":
        raise StudyAnythingAdapterVerificationError("Learning context schema drifted.")
    if context.get("privacy", {}).get("bounded_excerpts_included") is not False:
        raise StudyAnythingAdapterVerificationError("Public learning context summary must exclude text.")
    if context.get("item_count") != 1 or not context.get("item_hashes"):
        raise StudyAnythingAdapterVerificationError("Learning context should expose exactly one hash-only item.")

    loop = report.get("study_anything_loop") or {}
    if loop.get("stage") != "completed":
        raise StudyAnythingAdapterVerificationError("Study Anything loop did not complete.")
    if loop.get("teaching_layer_count") != 2:
        raise StudyAnythingAdapterVerificationError("Expected overview and glossary teaching layers.")
    if loop.get("quiz_item_count") != 1 or loop.get("grading_result_count") != 1:
        raise StudyAnythingAdapterVerificationError("Expected one quiz item and one grading result.")

    agent = report.get("agent_evidence") or {}
    if agent.get("audit_status") != "verified":
        raise StudyAnythingAdapterVerificationError("Agent audit must be verified.")
    if agent.get("eval_status") != "ready_for_external_eval":
        raise StudyAnythingAdapterVerificationError("Agent eval artifact should be ready.")
    required_tasks = {"teach.overview", "teach.glossary", "quiz.generate", "answer.grade", "insight.synthesize"}
    if set(agent.get("observed_tasks") or []) != required_tasks:
        raise StudyAnythingAdapterVerificationError("Agent task coverage drifted.")

    projection = report.get("cognitive_loop_projection") or {}
    mastery = projection.get("mastery_record") or {}
    if mastery.get("schema_version") != "mastery-record-v1":
        raise StudyAnythingAdapterVerificationError("MasteryRecord schema drifted.")
    if mastery.get("level") != 0.5 or mastery.get("bloom") != "understand":
        raise StudyAnythingAdapterVerificationError("Mastery projection drifted.")
    loop_run = projection.get("loop_run") or {}
    if loop_run.get("schema_version") != "loop-run-v1" or loop_run.get("status") != "succeeded":
        raise StudyAnythingAdapterVerificationError("LoopRun projection drifted.")
    if mastery.get("record_id") not in " ".join(loop_run.get("artifact_refs") or []):
        raise StudyAnythingAdapterVerificationError("LoopRun must reference the projected MasteryRecord.")

    exports = report.get("exports") or {}
    if exports.get("second_brain_handoff_schema") != "second-brain-handoff-v1":
        raise StudyAnythingAdapterVerificationError("Second-brain handoff schema drifted.")
    if exports.get("strict_handoff_excludes_learner_answers") is not True:
        raise StudyAnythingAdapterVerificationError("Strict Cognitive Loop evidence must exclude learner answers.")

    privacy = report.get("privacy") or {}
    required_false = [
        "raw_source_text_in_report",
        "raw_diff_in_report",
        "learner_answers_in_report",
        "grading_feedback_in_report",
        "agent_endpoints_in_report",
        "agent_metadata_in_report",
        "model_keys_in_report",
        "study_anything_stores_real_model_keys",
    ]
    for key in required_false:
        if privacy.get(key) is not False:
            raise StudyAnythingAdapterVerificationError(f"Privacy flag must be false: {key}")
    if privacy.get("metadata_only_cognitive_loop_evidence") is not True:
        raise StudyAnythingAdapterVerificationError("Cognitive Loop evidence must be metadata-only.")
    assert_no_private_text(report)


def assert_no_private_text(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(serialized))
    if leaks:
        raise StudyAnythingAdapterVerificationError(f"Adapter report leaked private text: {leaks}")


def check_output(path: Path) -> None:
    expected = dump_json(build_report())
    if not path.is_file():
        raise StudyAnythingAdapterVerificationError(
            f"Study Anything adapter report is missing. Run: python3 scripts/verify_cognitive_loop_study_anything_adapter.py --write"
        )
    if path.read_text(encoding="utf-8") != expected:
        raise StudyAnythingAdapterVerificationError(
            "Study Anything adapter report is stale. "
            "Run: python3 scripts/verify_cognitive_loop_study_anything_adapter.py --write"
        )
    print("ok    Cognitive Loop Study Anything adapter report is up to date")


def write_output(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_json(build_report()), encoding="utf-8")
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
        print(f"verify_cognitive_loop_study_anything_adapter failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

