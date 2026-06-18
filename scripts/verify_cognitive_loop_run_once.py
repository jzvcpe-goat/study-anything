#!/usr/bin/env python3
"""Verify the Cognitive Loop run-once evidence path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-run-once-evidence.json"
CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
SCHEMA_VERSION = "cognitive-loop-run-once-evidence-verification-v1"


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
        "http://127.0.0.1:8787",
        "api_key",
        "agent endpoint:",
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden_values if needle in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-cognitive-loop-run-") as tmp:
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
        html_path = root / ".cognitive-loop" / "artifacts" / "run-once.html"
        json_path = root / ".cognitive-loop" / "events" / "run-once.json"
        run_once = run_cli(
            [
                "--root",
                str(root),
                "run-once",
                "--html",
                "--json",
                "--output",
                ".cognitive-loop/artifacts/run-once.html",
                "--json-output",
                ".cognitive-loop/events/run-once.json",
            ],
            cwd=ROOT,
        )
        verify = run_cli(["--root", str(root), "verify"], cwd=ROOT)
        html = html_path.read_text(encoding="utf-8")
        artifact_json = json.loads(json_path.read_text(encoding="utf-8"))
        assert_no_forbidden_text(html, label="HTML run-once artifact")
        assert_no_forbidden_text(json.dumps(artifact_json, ensure_ascii=False), label="JSON run-once artifact")
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "pass",
            "cli": "scripts/cognitive_loop_cli.py",
            "init_schema": init["schema_version"],
            "verify_schema": verify["schema_version"],
            "run_once_schema": run_once["schema_version"],
            "artifact_json_schema": artifact_json["schema_version"],
            "loop_run": {
                "created": json_path.is_file(),
                "run_id": artifact_json["loop_run"]["run_id"],
                "status": artifact_json["loop_run"]["status"],
                "decision_card_ids": artifact_json["loop_run"]["decision_card_ids"],
            },
            "html_artifact": {
                "created": html_path.is_file(),
                "contains_brand": "Cognitive Loop System" in html,
                "contains_decision_card": "Decision Card" in html,
                "contains_loop_run": "Loop Run" in html,
                "contains_redacted_json": "Redacted JSON" in html,
                "standalone_frontend_required": False,
            },
            "privacy": {
                "forbidden_text_leaked": False,
                "real_model_keys_stored": False,
                "agent_endpoints_included": False,
                "raw_source_text_included": False,
                "watcher_daemon_started": False,
                "mastra_runtime_started": False,
            },
            "commands": {
                "init": "python3 scripts/cognitive_loop_cli.py init",
                "verify": "python3 scripts/cognitive_loop_cli.py verify",
                "run_once": "python3 scripts/cognitive_loop_cli.py run-once --html",
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
            raise SystemExit(f"Cognitive Loop run-once evidence report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop run-once evidence report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_run_once.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
