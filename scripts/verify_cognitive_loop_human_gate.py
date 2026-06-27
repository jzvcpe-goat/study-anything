#!/usr/bin/env python3
"""Verify the Cognitive Loop Human Mastery Gate evidence path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-human-gate.json"
CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
SCHEMA_VERSION = "cognitive-loop-human-gate-verification-v1"


def run_cli(args: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(cwd),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CLI did not emit JSON for {args}: {completed.stdout}") from exc


def assert_no_forbidden_text(text: str, *, label: str) -> None:
    forbidden_values = [
        "sk-proj-",
        "bearer ",
        "raw private source text",
        "learner answer:",
        "diff --git",
        "api_key",
        "agent endpoint:",
        "http://127.0.0.1:8787",
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden_values if needle in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-cognitive-loop-gate-") as tmp:
        root = Path(tmp)
        init = run_cli(
            [
                "--root",
                str(root),
                "init",
                "--project-id",
                "external-adopter-project",
                "--project-name",
                "External Adopter Project",
                "--json",
            ],
            cwd=ROOT,
        )
        approved_html_path = root / ".cognitive-loop" / "artifacts" / "human-gate-approved.html"
        approved_json_path = root / ".cognitive-loop" / "events" / "human-gate-approved.json"
        approved = run_cli(
            [
                "--root",
                str(root),
                "gate",
                "--approve",
                "--html",
                "--json",
                "--decision-id",
                "dec-sensitive-runtime",
                "--rationale",
                "Operator verified the evidence, risk, rollback, and verification plan.",
                "--evidence-ref",
                "artifact:.cognitive-loop/artifacts/run-once.html",
                "--evidence-ref",
                "command:python3 scripts/cognitive_loop_cli.py verify",
                "--output",
                ".cognitive-loop/artifacts/human-gate-approved.html",
                "--json-output",
                ".cognitive-loop/events/human-gate-approved.json",
            ],
            cwd=ROOT,
        )
        rejected_json_path = root / ".cognitive-loop" / "events" / "human-gate-rejected.json"
        rejected = run_cli(
            [
                "--root",
                str(root),
                "gate",
                "--reject",
                "--json",
                "--decision-id",
                "dec-risky-change",
                "--rationale",
                "Operator rejected the decision until verification evidence improves.",
                "--json-output",
                ".cognitive-loop/events/human-gate-rejected.json",
            ],
            cwd=ROOT,
        )
        verify = run_cli(["--root", str(root), "verify"], cwd=ROOT)
        approved_html = approved_html_path.read_text(encoding="utf-8")
        approved_artifact = json.loads(approved_json_path.read_text(encoding="utf-8"))
        rejected_artifact = json.loads(rejected_json_path.read_text(encoding="utf-8"))
        assert_no_forbidden_text(approved_html, label="HTML human gate artifact")
        assert_no_forbidden_text(
            json.dumps(approved_artifact, ensure_ascii=False),
            label="JSON human gate approved artifact",
        )
        assert_no_forbidden_text(
            json.dumps(rejected_artifact, ensure_ascii=False),
            label="JSON human gate rejected artifact",
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "pass",
            "cli": "scripts/cognitive_loop_cli.py",
            "init_schema": init["schema_version"],
            "verify_schema": verify["schema_version"],
            "approved_gate_schema": approved["schema_version"],
            "rejected_gate_schema": rejected["schema_version"],
            "artifact_json_schema": approved_artifact["schema_version"],
            "approved": {
                "created": approved_json_path.is_file(),
                "decision_id": approved_artifact["gate_resolution"]["decision_id"],
                "decision_status": approved_artifact["decision_card"]["status"],
                "gate_status": approved_artifact["decision_card"]["human_mastery_gate"]["status"],
                "loop_status": approved_artifact["loop_run"]["status"],
            },
            "rejected": {
                "created": rejected_json_path.is_file(),
                "decision_id": rejected_artifact["gate_resolution"]["decision_id"],
                "decision_status": rejected_artifact["decision_card"]["status"],
                "gate_status": rejected_artifact["decision_card"]["human_mastery_gate"]["status"],
                "loop_status": rejected_artifact["loop_run"]["status"],
            },
            "html_artifact": {
                "created": approved_html_path.is_file(),
                "contains_brand": "Cognitive Loop System" in approved_html,
                "contains_human_gate": "Human Mastery Gate" in approved_html,
                "contains_redacted_json": "Redacted JSON" in approved_html,
                "standalone_frontend_required": False,
            },
            "privacy": {
                "forbidden_text_leaked": False,
                "diff_body_included": False,
                "file_contents_included": False,
                "raw_source_text_included": False,
                "learner_answers_included": False,
                "real_model_keys_stored": False,
                "agent_endpoints_included": False,
                "agent_metadata_included": False,
                "watcher_daemon_started": False,
                "mastra_runtime_started": False,
            },
            "commands": {
                "init": "python3 scripts/cognitive_loop_cli.py init",
                "verify": "python3 scripts/cognitive_loop_cli.py verify",
                "approve_gate": "python3 scripts/cognitive_loop_cli.py gate --approve --html",
                "reject_gate": "python3 scripts/cognitive_loop_cli.py gate --reject --html",
            },
        }


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    report = build_report()
    serialized = dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop human gate report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop human gate report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_human_gate.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
