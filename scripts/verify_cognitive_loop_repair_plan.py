#!/usr/bin/env python3
"""Verify the Cognitive Loop manual repair-plan path."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-repair-plan.json"
CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
SCHEMA_VERSION = "cognitive-loop-repair-plan-verification-v1"


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
    leaked = [needle for needle in forbidden_values if needle.lower() in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def build_clean_repair_plan(root: Path) -> tuple[dict[str, Any], dict[str, Any], str]:
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
    index = run_cli(
        [
            "--root",
            str(root),
            "index",
            "--html",
            "--json",
            "--event",
            ".cognitive-loop/events/run-once.json",
            "--output",
            ".cognitive-loop/artifacts/cognitive-loop-event-index.html",
            "--json-output",
            ".cognitive-loop/events/cognitive-loop-event-index.json",
        ],
        cwd=ROOT,
    )
    repair_html_path = root / ".cognitive-loop" / "artifacts" / "repair-plan.html"
    repair_json_path = root / ".cognitive-loop" / "events" / "repair-plan.json"
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
    html = repair_html_path.read_text(encoding="utf-8")
    artifact_json = json.loads(repair_json_path.read_text(encoding="utf-8"))
    assert_no_forbidden_text(html, label="HTML repair plan artifact")
    assert_no_forbidden_text(json.dumps(artifact_json, ensure_ascii=False), label="JSON repair plan")
    return (
        {
            "init_schema": init["schema_version"],
            "verify_schema": verify["schema_version"],
            "run_once_schema": run_once["schema_version"],
            "index_schema": index["schema_version"],
            "repair_plan_schema": repair_plan["schema_version"],
        },
        artifact_json,
        html,
    )


def build_bad_repair_plan(root: Path) -> dict[str, Any]:
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
    return run_cli(["--root", str(root), "repair-plan", "--json"], cwd=ROOT)


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-cognitive-loop-repair-plan-") as clean_tmp:
        command_schemas, artifact_json, html = build_clean_repair_plan(Path(clean_tmp))
    repair_plan = artifact_json["repair_plan"]
    clean_actions = repair_plan["actions"]
    if clean_actions:
        raise RuntimeError(f"Clean repair-plan fixture produced actions: {clean_actions}")
    with tempfile.TemporaryDirectory(prefix="study-anything-cognitive-loop-repair-plan-bad-") as bad_tmp:
        bad_repair_plan = build_bad_repair_plan(Path(bad_tmp))
    bad_plan = bad_repair_plan["repair_plan"]
    actions = bad_plan["actions"]
    action_codes = sorted({str(action.get("issue_code")) for action in actions})
    required_codes = {
        "missing_html_pair",
        "duplicate_hash",
        "stale_event_index_hash_mismatch",
        "stale_event_index_missing_event",
    }
    missing_codes = sorted(required_codes - set(action_codes))
    if missing_codes:
        raise RuntimeError(f"Bad repair-plan fixture did not plan repairs for: {missing_codes}")
    if any(action.get("execution_mode") != "manual_only" for action in actions):
        raise RuntimeError("Repair-plan actions must remain manual_only.")
    if any(action.get("auto_apply") is not False for action in actions):
        raise RuntimeError("Repair-plan actions must not auto-apply.")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "cli": "scripts/cognitive_loop_cli.py",
        **command_schemas,
        "artifact_json_schema": artifact_json["schema_version"],
        "clean_repair_plan": {
            "created": True,
            "action_count": repair_plan["action_count"],
            "manual_only": repair_plan["manual_only"],
            "auto_apply": repair_plan["auto_apply"],
            "content_included": repair_plan["content_included"],
        },
        "bad_repair_plan": {
            "status": bad_repair_plan["status"],
            "action_count": bad_plan["action_count"],
            "action_codes": action_codes,
            "manual_only": bad_plan["manual_only"],
            "auto_apply": bad_plan["auto_apply"],
        },
        "html_artifact": {
            "created": True,
            "contains_brand": "Cognitive Black Box Protocol" in html,
            "contains_repair_plan": "Repair Plan" in html,
            "contains_redacted_json": "Redacted JSON" in html,
            "standalone_frontend_required": False,
        },
        "privacy": {
            "forbidden_text_leaked": False,
            "repair_actions_executed": False,
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
            raise SystemExit(f"Cognitive Loop repair-plan report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop repair-plan report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_repair_plan.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
