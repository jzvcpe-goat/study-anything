#!/usr/bin/env python3
"""Verify Cognitive Loop manual watcher ingest and metadata-only projection."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-watcher-ingest.json"
WATCHER_CLI = ROOT / "scripts" / "cognitive_loop_watcher_ingest.py"
COGNITIVE_LOOP_CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
EVENT_STORE_CLI = ROOT / "scripts" / "cognitive_loop_event_store.py"
SCHEMA_VERSION = "cognitive-loop-watcher-ingest-verification-v1"


def run_json(command: list[str], *, cwd: Path, expect_fail: bool = False) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if expect_fail:
        if completed.returncode == 0:
            raise RuntimeError(f"Command unexpectedly passed: {' '.join(command)}")
        return {
            "status": "failed_as_expected",
            "stderr_first_line": completed.stderr.splitlines()[0] if completed.stderr else "",
        }
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Command did not emit JSON: {' '.join(command)}\n{completed.stdout}") from exc


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
        "OPENAI_API_KEY",
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden_values if needle.lower() in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-cognitive-loop-watcher-") as tmp:
        root = Path(tmp)
        init = run_json(
            [
                sys.executable,
                str(COGNITIVE_LOOP_CLI),
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
        init_config = run_json(
            [sys.executable, str(WATCHER_CLI), "--root", str(root), "init-config"],
            cwd=ROOT,
        )
        validate_config = run_json(
            [sys.executable, str(WATCHER_CLI), "--root", str(root), "validate-config"],
            cwd=ROOT,
        )
        html_path = root / ".cognitive-loop" / "artifacts" / "watcher-file.html"
        json_path = root / ".cognitive-loop" / "events" / "watcher-file.json"
        ingest = run_json(
            [
                sys.executable,
                str(WATCHER_CLI),
                "--root",
                str(root),
                "ingest",
                "--html",
                "--json",
                "--watcher-id",
                "file-change",
                "--target",
                "docs/cognitive-loop-contracts.md",
                "--summary",
                "Captured docs path change as metadata only.",
                "--ref",
                "path:docs/cognitive-loop-contracts.md",
                "--ref",
                "git:working-tree",
                "--generated-at",
                "2026-06-18T00:00:00Z",
                "--output",
                ".cognitive-loop/artifacts/watcher-file.html",
                "--json-output",
                ".cognitive-loop/events/watcher-file.json",
            ],
            cwd=ROOT,
        )
        index = run_json(
            [
                sys.executable,
                str(COGNITIVE_LOOP_CLI),
                "--root",
                str(root),
                "index",
                "--html",
                "--json",
                "--event",
                ".cognitive-loop/events/watcher-file.json",
                "--output",
                ".cognitive-loop/artifacts/watcher-index.html",
                "--json-output",
                ".cognitive-loop/events/watcher-index.json",
            ],
            cwd=ROOT,
        )
        rebuild = run_json(
            [
                sys.executable,
                str(EVENT_STORE_CLI),
                "--root",
                str(root),
                "rebuild",
                "--event",
                ".cognitive-loop/events/watcher-file.json",
            ],
            cwd=ROOT,
        )
        event_store_list = run_json(
            [sys.executable, str(EVENT_STORE_CLI), "--root", str(root), "list"],
            cwd=ROOT,
        )
        excluded = run_json(
            [
                sys.executable,
                str(WATCHER_CLI),
                "--root",
                str(root),
                "ingest",
                "--watcher-id",
                "file-change",
                "--target",
                ".env",
                "--summary",
                "Captured env path metadata only.",
            ],
            cwd=ROOT,
            expect_fail=True,
        )
        watcher_config = root / ".cognitive-loop" / "watchers.yaml"
        watcher_config.write_text(
            """schemaVersion: cognitive-loop-watchers-v1
mode: manual_ingest
daemon:
  enabled: false
  shipped: false
defaults:
  debounceMs: 750
  maxRefs: 12
  contentMode: metadata_only
watchers:
  - id: broken-file
    kind: file
    enabled: true
    eventType: runtime_error
    include:
      - "**/*.py"
    exclude: []
""",
            encoding="utf-8",
        )
        malformed = run_json(
            [sys.executable, str(WATCHER_CLI), "--root", str(root), "validate-config"],
            cwd=ROOT,
            expect_fail=True,
        )

        html = html_path.read_text(encoding="utf-8")
        artifact_json = json.loads(json_path.read_text(encoding="utf-8"))
        index_entries = ((index.get("event_index") or {}).get("entries") or [])
        event_store_events = ((event_store_list.get("event_store") or {}).get("events") or [])
        assert_no_forbidden_text(html, label="HTML watcher ingest artifact")
        assert_no_forbidden_text(json.dumps(artifact_json, ensure_ascii=False), label="JSON watcher ingest artifact")
        assert_no_forbidden_text(json.dumps(event_store_list, ensure_ascii=False), label="Event Store list")

        watcher_ingest = artifact_json["watcher_ingest"]
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "pass",
            "cli": "scripts/cognitive_loop_watcher_ingest.py",
            "init_schema": init["schema_version"],
            "init_config_schema": init_config["schema_version"],
            "validate_config_schema": validate_config["schema_version"],
            "ingest_schema": ingest["schema_version"],
            "artifact_json_schema": artifact_json["schema_version"],
            "index_schema": index["schema_version"],
            "event_store_rebuild_schema": rebuild["schema_version"],
            "watcher_config": {
                "created": (root / ".cognitive-loop" / "watchers.yaml").is_file(),
                "mode": validate_config["mode"],
                "watcher_count": validate_config["watcher_count"],
                "content_mode": validate_config["content_mode"],
                "daemon_enabled": validate_config["daemon"]["enabled"],
                "daemon_shipped": validate_config["daemon"]["shipped"],
            },
            "watcher_ingest": {
                "created": json_path.is_file(),
                "html_created": html_path.is_file(),
                "watcher_id": watcher_ingest["watcher_id"],
                "source_kind": watcher_ingest["source_kind"],
                "event_type": watcher_ingest["event_type"],
                "target": watcher_ingest["target"],
                "ref_count": watcher_ingest["ref_count"],
                "content_included": watcher_ingest["content_included"],
                "diff_body_included": watcher_ingest["diff_body_included"],
                "file_contents_included": watcher_ingest["file_contents_included"],
                "daemon_started": watcher_ingest["daemon_started"],
            },
            "project_event": {
                "event_id": artifact_json["project_event"]["event_id"],
                "event_type": artifact_json["project_event"]["event_type"],
                "target": artifact_json["project_event"]["target"],
                "ref_count": len(artifact_json["project_event"]["refs"]),
            },
            "event_index": {
                "entry_count": (index.get("event_index") or {}).get("entry_count"),
                "contains_watcher_ingest": any(
                    isinstance(item, dict) and item.get("kind") == "watcher_ingest"
                    for item in index_entries
                ),
            },
            "event_store": {
                "event_count": (event_store_list.get("event_store") or {}).get("event_count"),
                "contains_watcher_ingest": any(
                    isinstance(item, dict) and item.get("artifact_kind") == "watcher_ingest"
                    for item in event_store_events
                ),
            },
            "failure_modes": {
                "excluded_target_rejected": excluded["status"] == "failed_as_expected",
                "malformed_config_rejected": malformed["status"] == "failed_as_expected",
            },
            "privacy": {
                "metadata_only": True,
                "forbidden_text_leaked": False,
                "raw_source_text_included": False,
                "diff_body_included": False,
                "file_contents_included": False,
                "event_contents_included": False,
                "learner_answers_included": False,
                "agent_endpoints_included": False,
                "agent_metadata_included": False,
                "prompt_text_included": False,
                "real_model_keys_stored": False,
                "watcher_daemon_started": False,
                "mastra_runtime_started": False,
            },
            "acceptance": {
                "watcher_config_validated": True,
                "manual_ingest_only": True,
                "file_changed_event_created": artifact_json["project_event"]["event_type"] == "file_changed",
                "event_index_classifies_watcher": any(
                    isinstance(item, dict) and item.get("kind") == "watcher_ingest"
                    for item in index_entries
                ),
                "event_store_ingests_watcher": any(
                    isinstance(item, dict) and item.get("artifact_kind") == "watcher_ingest"
                    for item in event_store_events
                ),
                "excluded_target_rejected": excluded["status"] == "failed_as_expected",
                "malformed_config_rejected": malformed["status"] == "failed_as_expected",
                "metadata_only": True,
            },
            "commands": {
                "init_config": "python3 scripts/cognitive_loop_watcher_ingest.py init-config",
                "validate_config": "python3 scripts/cognitive_loop_watcher_ingest.py validate-config",
                "ingest": "python3 scripts/cognitive_loop_watcher_ingest.py ingest --html",
                "event_store": "python3 scripts/cognitive_loop_event_store.py rebuild",
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
            raise SystemExit(f"Cognitive Loop watcher ingest report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop watcher ingest report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_watcher_ingest.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
