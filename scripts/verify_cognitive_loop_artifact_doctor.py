#!/usr/bin/env python3
"""Verify the Cognitive Loop local artifact doctor path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-artifact-doctor.json"
CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
SCHEMA_VERSION = "cognitive-loop-artifact-doctor-verification-v1"


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
        "Operator verified the evidence, risk, rollback, and verification plan.",
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden_values if needle.lower() in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def build_clean_doctor(root: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
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
    doctor_html_path = root / ".cognitive-loop" / "artifacts" / "artifact-doctor.html"
    doctor_json_path = root / ".cognitive-loop" / "events" / "artifact-doctor.json"
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
    verify = run_cli(["--root", str(root), "verify"], cwd=ROOT)
    html = doctor_html_path.read_text(encoding="utf-8")
    artifact_json = json.loads(doctor_json_path.read_text(encoding="utf-8"))
    assert_no_forbidden_text(html, label="HTML artifact doctor")
    assert_no_forbidden_text(json.dumps(artifact_json, ensure_ascii=False), label="JSON artifact doctor")
    return (
        {
            "init_schema": init["schema_version"],
            "verify_schema": verify["schema_version"],
            "run_once_schema": run_once["schema_version"],
            "snapshot_schema": snapshot["schema_version"],
            "gate_schema": gate["schema_version"],
            "bundle_schema": bundle["schema_version"],
            "index_schema": index["schema_version"],
            "doctor_schema": doctor["schema_version"],
        },
        artifact_json,
        html,
    )


def build_bad_doctor(root: Path) -> dict[str, Any]:
    run_cli(
        [
            "--root",
            str(root),
            "init",
            "--project-id",
            "bad-external-adopter-project",
            "--project-name",
            "Bad External Adopter Project",
            "--json",
        ],
        cwd=ROOT,
    )
    event_dir = root / ".cognitive-loop" / "events"
    event_dir.mkdir(parents=True, exist_ok=True)
    duplicate_payload = '{"schema_version":"cognitive-loop-run-once-artifact-v1","status":"succeeded"}'
    (event_dir / "one.json").write_text(duplicate_payload, encoding="utf-8")
    (event_dir / "two.json").write_text(duplicate_payload, encoding="utf-8")
    stale_index = {
        "schema_version": "cognitive-loop-event-index-v1",
        "status": "ready",
        "event_index": {
            "entries": [
                {
                    "path": ".cognitive-loop/events/one.json",
                    "sha256": "0" * 64,
                }
            ]
        },
    }
    (event_dir / "cognitive-loop-event-index.json").write_text(json.dumps(stale_index), encoding="utf-8")
    return run_cli(["--root", str(root), "doctor", "--json"], cwd=ROOT)


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-cognitive-loop-doctor-") as clean_tmp:
        command_schemas, artifact_json, html = build_clean_doctor(Path(clean_tmp))
    doctor = artifact_json["artifact_doctor"]
    records = doctor["records"]
    issues = doctor["issues"]
    if issues:
        raise RuntimeError(f"Clean artifact doctor fixture produced issues: {issues}")
    with tempfile.TemporaryDirectory(prefix="study-anything-cognitive-loop-doctor-bad-") as bad_tmp:
        bad_doctor = build_bad_doctor(Path(bad_tmp))
    bad_codes = sorted({str(issue.get("code")) for issue in bad_doctor["artifact_doctor"]["issues"]})
    required_bad_codes = {
        "missing_html_pair",
        "duplicate_hash",
        "stale_event_index_hash_mismatch",
        "stale_event_index_missing_event",
    }
    missing_codes = sorted(required_bad_codes - set(bad_codes))
    if missing_codes:
        raise RuntimeError(f"Bad artifact doctor fixture did not detect: {missing_codes}")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "cli": "scripts/cognitive_loop_cli.py",
        **command_schemas,
        "artifact_json_schema": artifact_json["schema_version"],
        "artifact_doctor": {
            "created": True,
            "status": artifact_json["status"],
            "file_count": doctor["file_count"],
            "issue_count": doctor["issue_count"],
            "error_count": doctor["error_count"],
            "warning_count": doctor["warning_count"],
            "content_included": doctor["content_included"],
            "all_records_have_hash": all(bool(item.get("sha256")) for item in records),
            "all_records_exclude_content": all(item.get("content_included") is False for item in records),
        },
        "failure_modes": {
            "detected_codes": bad_codes,
            "missing_html_pair_detected": "missing_html_pair" in bad_codes,
            "duplicate_hash_detected": "duplicate_hash" in bad_codes,
            "stale_event_index_detected": any(code.startswith("stale_event_index") for code in bad_codes),
        },
        "html_artifact": {
            "created": True,
            "contains_brand": "Cognitive Black Box Protocol" in html,
            "contains_artifact_doctor": "Artifact Doctor" in html,
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
        },
        "commands": {
            "init": "python3 scripts/cognitive_loop_cli.py init",
            "verify": "python3 scripts/cognitive_loop_cli.py verify",
            "doctor": "python3 scripts/cognitive_loop_cli.py doctor --html",
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
            raise SystemExit(f"Cognitive Loop artifact doctor report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop artifact doctor report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_artifact_doctor.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
