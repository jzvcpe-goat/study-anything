#!/usr/bin/env python3
"""Verify Cognitive Loop Watcher Runner Lite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-watcher-runner.json"
COGNITIVE_LOOP_CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
WATCHER_INGEST_CLI = ROOT / "scripts" / "cognitive_loop_watcher_ingest.py"
WATCHER_RUNNER_CLI = ROOT / "scripts" / "cognitive_loop_watcher_runner.py"
EVENT_STORE_CLI = ROOT / "scripts" / "cognitive_loop_event_store.py"
SCHEMA_VERSION = "cognitive-loop-watcher-runner-verification-v1"
GENERATED_AT = "2026-06-19T00:00:00Z"


class WatcherRunnerVerificationError(RuntimeError):
    """Readable watcher runner verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


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
            raise WatcherRunnerVerificationError(f"Command unexpectedly passed: {' '.join(command)}")
        return {
            "status": "failed_as_expected",
            "stderr_first_line": completed.stderr.splitlines()[0] if completed.stderr else "",
        }
    if completed.returncode != 0:
        raise WatcherRunnerVerificationError(
            f"Command failed: {' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise WatcherRunnerVerificationError(
            f"Command did not emit JSON: {' '.join(command)}\n{completed.stdout}"
        ) from exc


def assert_no_forbidden_text(value: Any, *, label: str) -> None:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    forbidden = [
        "sk-proj-",
        "bearer ",
        "raw private source text",
        "learner answer:",
        "diff --git",
        "api_key",
        "agent endpoint:",
        "http://127.0.0.1:8787",
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
    ]
    leaked = [needle for needle in forbidden if needle.lower() in lowered]
    if leaked:
        raise WatcherRunnerVerificationError(f"{label} leaked forbidden text: {leaked}")


def _runner_command(root: Path) -> list[str]:
    return [
        sys.executable,
        str(WATCHER_RUNNER_CLI),
        "--root",
        str(root),
        "run",
        "--html",
        "--json",
        "--study-adapter",
        "--poll-cycles",
        "2",
        "--changed-path",
        "docs/cognitive-loop-contracts.md",
        "--changed-path",
        "docs/cognitive-loop-contracts.md",
        "--changed-path",
        "apps/api/study_anything/core/workflow.py",
        "--changed-path",
        ".env",
        "--git-diff-summary",
        "Three files changed across learning workflow and contract metadata.",
        "--test-failure-summary",
        "api-tests failed in two cases before the current fix.",
        "--generated-at",
        GENERATED_AT,
    ]


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-watcher-runner-") as tmp:
        root = Path(tmp)
        init = run_json(
            [
                sys.executable,
                str(COGNITIVE_LOOP_CLI),
                "--root",
                str(root),
                "init",
                "--project-id",
                "watcher-runner-project",
                "--project-name",
                "Watcher Runner Project",
                "--json",
            ],
            cwd=ROOT,
        )
        init_config = run_json(
            [sys.executable, str(WATCHER_INGEST_CLI), "--root", str(root), "init-config"],
            cwd=ROOT,
        )
        first = run_json(_runner_command(root), cwd=ROOT)
        second = run_json(_runner_command(root), cwd=ROOT)
        event_store_list = run_json(
            [sys.executable, str(EVENT_STORE_CLI), "--root", str(root), "list"],
            cwd=ROOT,
        )
        raw_diff_rejected = run_json(
            [
                sys.executable,
                str(WATCHER_RUNNER_CLI),
                "--root",
                str(root),
                "run",
                "--changed-path",
                "apps/api/study_anything/core/workflow.py",
                "--git-diff-summary",
                "diff --git a/private.py b/private.py",
            ],
            cwd=ROOT,
            expect_fail=True,
        )

        runner_json = root / ".cognitive-loop" / "events" / "cognitive-loop-watcher-runner.json"
        runner_html = root / ".cognitive-loop" / "artifacts" / "cognitive-loop-watcher-runner.html"
        study_jsons = sorted((root / ".cognitive-loop" / "events").glob("watcher-runner-study-*.json"))
        watcher_events = [
            item
            for item in (event_store_list.get("event_store") or {}).get("events", [])
            if isinstance(item, dict)
        ]
        html = runner_html.read_text(encoding="utf-8")
        assert_no_forbidden_text(first, label="first watcher runner report")
        assert_no_forbidden_text(second, label="second watcher runner report")
        assert_no_forbidden_text(event_store_list, label="event store list")
        assert_no_forbidden_text(html, label="watcher runner HTML")

        if first.get("schema_version") != "cognitive-loop-watcher-runner-v1":
            raise WatcherRunnerVerificationError("Runner schema drifted.")
        if first.get("status") != "pass":
            raise WatcherRunnerVerificationError("Runner report did not pass.")
        observations = first.get("observations") or {}
        if observations.get("deduped_count") != 4:
            raise WatcherRunnerVerificationError("Runner should dedupe to four accepted observations.")
        if observations.get("skipped_count") < 1:
            raise WatcherRunnerVerificationError("Runner should skip excluded .env path.")
        if observations.get("duplicate_count") < 1:
            raise WatcherRunnerVerificationError("Runner should report duplicate path debounce.")
        event_store = first.get("event_store") or {}
        if event_store.get("event_count") != 4 or event_store.get("artifact_count") != 4:
            raise WatcherRunnerVerificationError("Event Store should contain four watcher events.")
        second_store = second.get("event_store") or {}
        if second_store.get("event_count") != 4 or second_store.get("artifact_count") != 4:
            raise WatcherRunnerVerificationError("Second runner pass should be idempotent.")
        study_gate = first.get("study_adapter_gate") or {}
        if study_gate.get("triggered") is not True:
            raise WatcherRunnerVerificationError("Study Adapter gate should trigger for high-risk events.")
        if study_gate.get("schema_version") != "cognitive-loop-study-anything-adapter-cli-v1":
            raise WatcherRunnerVerificationError("Study Adapter CLI schema drifted.")
        privacy = first.get("privacy") or {}
        for key in (
            "raw_source_text_included",
            "raw_diff_included",
            "diff_body_included",
            "file_contents_included",
            "test_output_included",
            "learner_answers_included",
            "agent_endpoints_included",
            "agent_metadata_included",
            "model_keys_included",
            "watcher_daemon_started",
            "background_service_started",
        ):
            if privacy.get(key) is not False:
                raise WatcherRunnerVerificationError(f"Privacy flag must be false: {key}")

        return {
            "schema_version": SCHEMA_VERSION,
            "status": "pass",
            "runner_schema": first["schema_version"],
            "init_schema": init["schema_version"],
            "watcher_config_schema": init_config["schema_version"],
            "runner_json_written": runner_json.is_file(),
            "runner_html_written": runner_html.is_file(),
            "accepted_observation_count": observations["deduped_count"],
            "skipped_count": observations["skipped_count"],
            "duplicate_count": observations["duplicate_count"],
            "event_store_event_count": event_store["event_count"],
            "second_pass_event_count": second_store["event_count"],
            "stored_event_count": (event_store_list.get("event_store") or {}).get("event_count"),
            "watcher_event_types": sorted({str(item.get("event_type")) for item in watcher_events}),
            "study_adapter_gate": {
                "triggered": study_gate["triggered"],
                "schema_version": study_gate["schema_version"],
                "status": study_gate["status"],
                "study_artifact_count": len(study_jsons),
                "external_agent_called": study_gate["external_agent_called"],
            },
            "failure_modes": {
                "excluded_env_path_skipped": observations["skipped_count"] >= 1,
                "raw_diff_rejected": raw_diff_rejected["status"] == "failed_as_expected",
                "duplicate_events_idempotent": second_store["event_count"] == event_store["event_count"],
            },
            "privacy": {
                "metadata_only": True,
                "forbidden_text_leaked": False,
                "raw_source_text_included": False,
                "raw_diff_included": False,
                "diff_body_included": False,
                "file_contents_included": False,
                "test_output_included": False,
                "learner_answers_included": False,
                "agent_endpoints_included": False,
                "agent_metadata_included": False,
                "model_keys_included": False,
                "watcher_daemon_started": False,
                "background_service_started": False,
            },
            "commands": {
                "run": ".venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter",
                "verify": ".venv/bin/python scripts/verify_cognitive_loop_watcher_runner.py --check",
                "release_check": "./scripts/release_check.sh",
            },
        }


def check_output(path: Path) -> None:
    expected = dump_json(build_report())
    if not path.is_file():
        raise WatcherRunnerVerificationError(
            "Cognitive Loop watcher runner report is missing. "
            "Run: .venv/bin/python scripts/verify_cognitive_loop_watcher_runner.py --write"
        )
    if path.read_text(encoding="utf-8") != expected:
        raise WatcherRunnerVerificationError(
            "Cognitive Loop watcher runner report is stale. "
            "Run: .venv/bin/python scripts/verify_cognitive_loop_watcher_runner.py --write"
        )
    print("ok    Cognitive Loop watcher runner report is up to date")


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
        print(f"verify_cognitive_loop_watcher_runner failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
