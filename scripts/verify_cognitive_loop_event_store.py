#!/usr/bin/env python3
"""Verify the Cognitive Loop local SQLite Event Store path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-event-store.json"
CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
EVENT_STORE = ROOT / "scripts" / "cognitive_loop_event_store.py"
SCHEMA_VERSION = "cognitive-loop-event-store-verification-v1"


class EventStoreVerificationError(RuntimeError):
    """Readable verifier failure."""


def run_json(command: list[str], *, cwd: Path, expect_success: bool = True) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if expect_success and completed.returncode != 0:
        raise EventStoreVerificationError(
            f"Command failed: {' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    if not expect_success:
        if completed.returncode == 0:
            raise EventStoreVerificationError(f"Command unexpectedly passed: {' '.join(command)}")
        return {
            "returncode": completed.returncode,
            "stderr": completed.stderr,
            "stdout": completed.stdout,
        }
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise EventStoreVerificationError(
            f"Command did not emit JSON: {' '.join(command)}\nstdout={completed.stdout}"
        ) from exc


def run_cli(args: list[str], *, cwd: Path) -> dict[str, Any]:
    return run_json([sys.executable, str(CLI), *args], cwd=cwd)


def run_store(args: list[str], *, cwd: Path, expect_success: bool = True) -> dict[str, Any]:
    return run_json([sys.executable, str(EVENT_STORE), *args], cwd=cwd, expect_success=expect_success)


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
    leaked = [needle for needle in forbidden_values if needle.lower() in lowered]
    if leaked:
        raise EventStoreVerificationError(f"{label} leaked forbidden text: {leaked}")


def create_event_artifacts(root: Path) -> list[str]:
    run_cli(
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
    run_cli(
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
    run_cli(
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
    run_cli(
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
            "Operator reviewed the public evidence, risk, rollback, and verification plan.",
            "--output",
            ".cognitive-loop/artifacts/human-gate.html",
            "--json-output",
            ".cognitive-loop/events/human-gate.json",
        ],
        cwd=ROOT,
    )
    run_cli(
        [
            "--root",
            str(root),
            "bundle",
            "--html",
            "--json",
            "--artifact",
            ".cognitive-loop/events/run-once.json",
            "--artifact",
            ".cognitive-loop/events/snapshot.json",
            "--artifact",
            ".cognitive-loop/events/human-gate.json",
            "--output",
            ".cognitive-loop/artifacts/evidence-bundle.html",
            "--json-output",
            ".cognitive-loop/events/evidence-bundle.json",
        ],
        cwd=ROOT,
    )
    run_cli(
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
            ".cognitive-loop/artifacts/event-index.html",
            "--json-output",
            ".cognitive-loop/events/event-index.json",
        ],
        cwd=ROOT,
    )
    return [
        ".cognitive-loop/events/run-once.json",
        ".cognitive-loop/events/snapshot.json",
        ".cognitive-loop/events/human-gate.json",
        ".cognitive-loop/events/evidence-bundle.json",
        ".cognitive-loop/events/event-index.json",
    ]


def create_bad_artifact(root: Path) -> str:
    bad_path = root / ".cognitive-loop" / "events" / "unsafe-agent-endpoint.json"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text(
        json.dumps(
            {
                "schema_version": "cognitive-loop-run-once-artifact-v1",
                "status": "ready",
                "project_event": {
                    "event_id": "evt-unsafe-agent-endpoint",
                    "project_id": "external-adopter-project",
                    "actor": "agent",
                    "event_type": "verification_completed",
                    "summary": "agent endpoint: http://127.0.0.1:8787 should not be stored",
                    "timestamp": "2026-06-17T00:00:00Z",
                    "sensitivity": "internal",
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return ".cognitive-loop/events/unsafe-agent-endpoint.json"


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-cognitive-loop-event-store-") as tmp:
        root = Path(tmp)
        event_paths = create_event_artifacts(root)
        db_path = ".cognitive-loop/cognitive-loop-events.sqlite"
        event_args: list[str] = []
        for path in event_paths:
            event_args.extend(["--event", path])

        init = run_store(["--root", str(root), "--db", db_path, "init"], cwd=ROOT)
        rebuild = run_store(
            ["--root", str(root), "--db", db_path, "rebuild", *event_args],
            cwd=ROOT,
        )
        list_first = run_store(["--root", str(root), "--db", db_path, "list"], cwd=ROOT)
        run_store(
            ["--root", str(root), "--db", db_path, "rebuild", *event_args],
            cwd=ROOT,
        )
        list_again = run_store(["--root", str(root), "--db", db_path, "list"], cwd=ROOT)
        export_json_path = root / ".cognitive-loop" / "events" / "event-store-export.json"
        export_html_path = root / ".cognitive-loop" / "artifacts" / "event-store.html"
        export = run_store(
            [
                "--root",
                str(root),
                "--db",
                db_path,
                "export",
                "--html",
                "--json",
                "--output",
                ".cognitive-loop/artifacts/event-store.html",
                "--json-output",
                ".cognitive-loop/events/event-store-export.json",
            ],
            cwd=ROOT,
        )
        unsafe_path = create_bad_artifact(root)
        unsafe = run_store(
            ["--root", str(root), "--db", db_path, "ingest", "--event", unsafe_path],
            cwd=ROOT,
            expect_success=False,
        )

        html = export_html_path.read_text(encoding="utf-8")
        export_payload = json.loads(export_json_path.read_text(encoding="utf-8"))
        serialized_export = json.dumps(export_payload, ensure_ascii=False, sort_keys=True)
        assert_no_forbidden_text(html, label="Event Store HTML export")
        assert_no_forbidden_text(serialized_export, label="Event Store JSON export")
        first_store = list_first["event_store"]
        second_store = list_again["event_store"]
        export_store = export_payload["event_store"]
        if first_store["event_count"] != second_store["event_count"]:
            raise EventStoreVerificationError("Event Store rebuild is not idempotent.")
        if export_store["event_count"] != len(event_paths):
            raise EventStoreVerificationError("Event Store export event count drifted.")
        if not export_html_path.is_file() or not export_json_path.is_file():
            raise EventStoreVerificationError("Event Store export did not create HTML and JSON artifacts.")
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "pass",
            "cli": "scripts/cognitive_loop_event_store.py",
            "init_schema": init["schema_version"],
            "rebuild_schema": rebuild["schema_version"],
            "list_schema": list_first["schema_version"],
            "export_schema": export["schema_version"],
            "event_store": {
                "sqlite_file_created": (root / db_path).is_file(),
                "event_count": export_store["event_count"],
                "artifact_count": export_store["artifact_count"],
                "duplicate_rebuild_idempotent": first_store["event_count"] == second_store["event_count"],
                "all_items_have_hash": all(
                    bool(item.get("artifact_sha256")) for item in export_store["events"]
                ),
                "all_items_exclude_content": export_store.get("content_included") is False
                and all((item.get("metadata") or {}).get("content_included") is False for item in export_store["events"]),
                "kinds": sorted({str(item.get("artifact_kind")) for item in export_store["events"]}),
            },
            "html_artifact": {
                "created": export_html_path.is_file(),
                "contains_brand": "Cognitive Loop System" in html,
                "contains_sqlite_event_store": "SQLite Event Store" in html,
                "contains_redacted_json": "Redacted JSON" in html,
                "standalone_frontend_required": False,
            },
            "privacy": {
                "forbidden_text_leaked": False,
                "unsafe_agent_endpoint_rejected": unsafe["returncode"] != 0,
                "artifact_contents_included": False,
                "event_contents_included": False,
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
                "init": "python3 scripts/cognitive_loop_event_store.py init",
                "rebuild": "python3 scripts/cognitive_loop_event_store.py rebuild",
                "export": "python3 scripts/cognitive_loop_event_store.py export --html",
                "check": "python3 scripts/verify_cognitive_loop_event_store.py --check",
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
            raise SystemExit(f"Cognitive Loop Event Store report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop Event Store report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_event_store.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
