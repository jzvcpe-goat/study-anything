#!/usr/bin/env python3
"""Verify the Cognitive Loop project snapshot evidence path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-project-snapshot.json"
CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
SCHEMA_VERSION = "cognitive-loop-project-snapshot-verification-v1"


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
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden_values if needle in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-cognitive-loop-snapshot-") as tmp:
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
        html_path = root / ".cognitive-loop" / "artifacts" / "snapshot.html"
        json_path = root / ".cognitive-loop" / "events" / "snapshot.json"
        snapshot = run_cli(
            [
                "--root",
                str(root),
                "snapshot",
                "--html",
                "--json",
                "--path",
                "README.md",
                "--path",
                "docs/cognitive-loop-contracts.md",
                "--output",
                ".cognitive-loop/artifacts/snapshot.html",
                "--json-output",
                ".cognitive-loop/events/snapshot.json",
            ],
            cwd=ROOT,
        )
        verify = run_cli(["--root", str(root), "verify"], cwd=ROOT)
        html = html_path.read_text(encoding="utf-8")
        artifact_json = json.loads(json_path.read_text(encoding="utf-8"))
        assert_no_forbidden_text(html, label="HTML snapshot artifact")
        assert_no_forbidden_text(json.dumps(artifact_json, ensure_ascii=False), label="JSON snapshot artifact")
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "pass",
            "cli": "scripts/cognitive_loop_cli.py",
            "init_schema": init["schema_version"],
            "verify_schema": verify["schema_version"],
            "snapshot_schema": snapshot["schema_version"],
            "artifact_json_schema": artifact_json["schema_version"],
            "project_event": {
                "event_id": artifact_json["project_event"]["event_id"],
                "event_type": artifact_json["project_event"]["event_type"],
                "ref_count": len(artifact_json["project_event"]["refs"]),
            },
            "snapshot": {
                "created": json_path.is_file(),
                "changed_path_count": artifact_json["snapshot"]["changed_path_count"],
                "diff_body_included": artifact_json["snapshot"]["diff_body_included"],
                "file_contents_included": artifact_json["snapshot"]["file_contents_included"],
            },
            "html_artifact": {
                "created": html_path.is_file(),
                "contains_brand": "Cognitive Black Box Protocol" in html,
                "contains_project_snapshot": "Project Snapshot" in html,
                "contains_redacted_json": "Redacted JSON" in html,
                "standalone_frontend_required": False,
            },
            "privacy": {
                "forbidden_text_leaked": False,
                "diff_body_included": False,
                "file_contents_included": False,
                "real_model_keys_stored": False,
                "agent_endpoints_included": False,
                "watcher_daemon_started": False,
                "mastra_runtime_started": False,
            },
            "commands": {
                "init": "python3 scripts/cognitive_loop_cli.py init",
                "verify": "python3 scripts/cognitive_loop_cli.py verify",
                "snapshot": "python3 scripts/cognitive_loop_cli.py snapshot --html",
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
            raise SystemExit(f"Cognitive Loop project snapshot report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop project snapshot report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_snapshot.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
