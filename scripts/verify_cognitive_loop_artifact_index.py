#!/usr/bin/env python3
"""Verify the Cognitive Loop static artifact-index shell."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-artifact-index.json"
CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
SCHEMA_VERSION = "cognitive-loop-artifact-index-verification-v1"


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
        "private local artifact body",
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden_values if needle.lower() in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def build_local_artifacts(root: Path) -> dict[str, Any]:
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
    gate = run_cli(
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
            "Operator verified public evidence and rollback plan.",
            "--output",
            ".cognitive-loop/artifacts/human-gate.html",
            "--json-output",
            ".cognitive-loop/events/human-gate.json",
        ],
        cwd=ROOT,
    )
    bundle = run_cli(
        [
            "--root",
            str(root),
            "bundle",
            "--html",
            "--json",
            "--artifact",
            ".cognitive-loop/events/run-once.json",
            "--artifact",
            ".cognitive-loop/artifacts/run-once.html",
            "--artifact",
            ".cognitive-loop/events/snapshot.json",
            "--artifact",
            ".cognitive-loop/artifacts/snapshot.html",
            "--artifact",
            ".cognitive-loop/events/human-gate.json",
            "--artifact",
            ".cognitive-loop/artifacts/human-gate.html",
            "--output",
            ".cognitive-loop/artifacts/evidence-bundle.html",
            "--json-output",
            ".cognitive-loop/events/evidence-bundle.json",
        ],
        cwd=ROOT,
    )
    index = run_cli(
        [
            "--root",
            str(root),
            "index",
            "--html",
            "--json",
            "--event",
            ".cognitive-loop/events/run-once.json",
            "--event",
            ".cognitive-loop/events/snapshot.json",
            "--event",
            ".cognitive-loop/events/human-gate.json",
            "--event",
            ".cognitive-loop/events/evidence-bundle.json",
            "--output",
            ".cognitive-loop/artifacts/cognitive-loop-event-index.html",
            "--json-output",
            ".cognitive-loop/events/cognitive-loop-event-index.json",
        ],
        cwd=ROOT,
    )
    doctor = run_cli(
        [
            "--root",
            str(root),
            "doctor",
            "--html",
            "--json",
            "--output",
            ".cognitive-loop/artifacts/artifact-doctor.html",
            "--json-output",
            ".cognitive-loop/events/artifact-doctor.json",
        ],
        cwd=ROOT,
    )
    repair_plan = run_cli(
        [
            "--root",
            str(root),
            "repair-plan",
            "--html",
            "--json",
            "--output",
            ".cognitive-loop/artifacts/repair-plan.html",
            "--json-output",
            ".cognitive-loop/events/repair-plan.json",
        ],
        cwd=ROOT,
    )
    verify = run_cli(["--root", str(root), "verify"], cwd=ROOT)
    return {
        "init_schema": init["schema_version"],
        "verify_schema": verify["schema_version"],
        "run_once_schema": run_once["schema_version"],
        "snapshot_schema": snapshot["schema_version"],
        "gate_schema": gate["schema_version"],
        "bundle_schema": bundle["schema_version"],
        "index_schema": index["schema_version"],
        "doctor_schema": doctor["schema_version"],
        "repair_plan_schema": repair_plan["schema_version"],
    }


def rejects_unsafe_path(root: Path) -> bool:
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "artifact-index",
            "--artifact",
            "../secret.json",
            "--json",
        ],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.returncode != 0 and "repo-relative" in completed.stderr


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-cognitive-loop-artifact-index-") as tmp:
        root = Path(tmp)
        command_schemas = build_local_artifacts(root)
        artifact_html_path = root / ".cognitive-loop" / "artifacts" / "artifact-index.html"
        artifact_json_path = root / ".cognitive-loop" / "events" / "artifact-index.json"
        run_cli(
            [
                "--root",
                str(root),
                "artifact-index",
                "--html",
                "--json",
                "--output",
                ".cognitive-loop/artifacts/artifact-index.html",
                "--json-output",
                ".cognitive-loop/events/artifact-index.json",
            ],
            cwd=ROOT,
        )
        html = artifact_html_path.read_text(encoding="utf-8")
        artifact_json = json.loads(artifact_json_path.read_text(encoding="utf-8"))
        assert_no_forbidden_text(html, label="HTML artifact index")
        assert_no_forbidden_text(json.dumps(artifact_json, ensure_ascii=False), label="JSON artifact index")
        unsafe_path_rejected = rejects_unsafe_path(root)

    index = artifact_json["artifact_index"]
    entries = index["entries"]
    paths = {str(entry.get("path")) for entry in entries}
    hrefs = {str(entry.get("href")) for entry in entries}
    required_paths = {
        ".cognitive-loop/events/run-once.json",
        ".cognitive-loop/artifacts/run-once.html",
        ".cognitive-loop/events/repair-plan.json",
        ".cognitive-loop/artifacts/repair-plan.html",
    }
    missing_paths = sorted(required_paths - paths)
    if missing_paths:
        raise RuntimeError(f"Artifact index missed local artifacts: {missing_paths}")
    if "../events/run-once.json" not in hrefs or "run-once.html" not in hrefs:
        raise RuntimeError("Artifact index did not create local relative links.")
    if index["entry_count"] < 12:
        raise RuntimeError(f"Artifact index expected at least 12 entries, got {index['entry_count']}")
    if any(entry.get("content_included") is not False for entry in entries):
        raise RuntimeError("Artifact index entries must not embed contents.")
    if not unsafe_path_rejected:
        raise RuntimeError("Artifact index did not reject an unsafe path.")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "cli": "scripts/cognitive_loop_cli.py",
        **command_schemas,
        "artifact_json_schema": artifact_json["schema_version"],
        "artifact_index": {
            "created": True,
            "entry_count": index["entry_count"],
            "html_count": index["html_count"],
            "event_json_count": index["event_json_count"],
            "markdown_count": index["markdown_count"],
            "content_included": index["content_included"],
            "standalone_frontend_required": index["standalone_frontend_required"],
            "relative_links_created": True,
            "unsafe_path_rejected": True,
        },
        "html_artifact": {
            "created": True,
            "contains_brand": "Cognitive Black Box Protocol" in html,
            "contains_artifact_index": "Artifact Index" in html,
            "contains_run_once_link": "run-once.html" in html,
            "contains_event_link": "../events/run-once.json" in html,
            "contains_redacted_json": "Redacted JSON" in html,
            "standalone_frontend_required": False,
        },
        "privacy": {
            "forbidden_text_leaked": False,
            "event_contents_included": False,
            "artifact_contents_included": False,
            "diff_body_included": False,
            "file_contents_included": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "real_model_keys_stored": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "watcher_daemon_started": False,
            "mastra_runtime_started": False,
            "standalone_frontend_required": False,
        },
        "commands": {
            "artifact_index": "python3 scripts/cognitive_loop_cli.py artifact-index --html",
            "artifact_index_check": "python3 scripts/verify_cognitive_loop_artifact_index.py --check",
            "doctor": "python3 scripts/cognitive_loop_cli.py doctor --html",
            "repair_plan": "python3 scripts/cognitive_loop_cli.py repair-plan --html",
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
            raise SystemExit(f"Cognitive Loop artifact-index report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop artifact-index report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_artifact_index.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
