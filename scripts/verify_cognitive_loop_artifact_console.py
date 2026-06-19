#!/usr/bin/env python3
"""Verify Cognitive Loop HTML Artifact Console Lite."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-artifact-console.json"
CONSOLE = ROOT / "scripts" / "cognitive_loop_artifact_console.py"
CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
WATCHER_INGEST = ROOT / "scripts" / "cognitive_loop_watcher_ingest.py"
WATCHER_RUNNER = ROOT / "scripts" / "cognitive_loop_watcher_runner.py"
SCHEMA_VERSION = "cognitive-loop-artifact-console-verification-v1"


def run_json(command: list[str], *, cwd: Path = ROOT, required: bool = True) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if required and completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    if completed.returncode != 0:
        return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Command did not emit JSON: {' '.join(command)}\n{completed.stdout}") from exc


def assert_no_forbidden_text(text: str, *, label: str) -> None:
    forbidden = [
        "sk-proj-",
        "bearer ",
        "raw private source text",
        "private source text",
        "learner answer:",
        "diff --git",
        "api_key",
        "agent endpoint:",
        "http://127.0.0.1:8787",
        "raw test output",
    ]
    lowered = text.lower()
    leaked = [needle for needle in forbidden if needle.lower() in lowered]
    if leaked:
        raise RuntimeError(f"{label} leaked forbidden text: {leaked}")


def init_project(root: Path) -> None:
    run_json(
        [
            sys.executable,
            str(CLI),
            "--root",
            str(root),
            "init",
            "--project-id",
            "artifact-console-project",
            "--project-name",
            "Artifact Console Project",
            "--json",
        ]
    )


def build_console(root: Path, *, html: bool = True) -> tuple[dict[str, Any], str]:
    html_path = root / ".cognitive-loop" / "artifacts" / "console" / "index.html"
    manifest_path = root / ".cognitive-loop" / "artifacts" / "console" / "manifest.json"
    args = [
        sys.executable,
        str(CONSOLE),
        "build",
        "--root",
        str(root),
        "--json",
        "--output",
        ".cognitive-loop/artifacts/console/index.html",
        "--json-output",
        ".cognitive-loop/artifacts/console/manifest.json",
    ]
    if html:
        args.insert(args.index("--json"), "--html")
    report = run_json(args)
    html_text = html_path.read_text(encoding="utf-8") if html else ""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report != manifest:
        raise RuntimeError("Console stdout JSON and manifest JSON drifted.")
    assert_no_forbidden_text(json.dumps(manifest, ensure_ascii=False), label="console manifest")
    if html:
        assert_no_forbidden_text(html_text, label="console HTML")
    return manifest, html_text


def run_watcher_runner(root: Path) -> dict[str, Any]:
    run_json([sys.executable, str(WATCHER_INGEST), "--root", str(root), "init-config", "--force"])
    return run_json(
        [
            sys.executable,
            str(WATCHER_RUNNER),
            "--root",
            str(root),
            "run",
            "--html",
            "--json",
            "--study-adapter",
            "--poll-cycles",
            "2",
            "--changed-path",
            "apps/api/study_anything/core/workflow.py",
            "--changed-path",
            "apps/api/study_anything/core/workflow.py",
            "--changed-path",
            ".env",
            "--git-diff-summary",
            "Metadata-only workflow boundary changed.",
            "--test-failure-summary",
            "API tests failed before the current fix.",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )


def verify_empty_console() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-artifact-console-empty-") as tmp:
        root = Path(tmp)
        init_project(root)
        manifest, html = build_console(root)
    sections = manifest["sections"]
    if manifest["status"] != "ready":
        raise RuntimeError(f"Empty console should still be ready, got {manifest['status']}")
    if sections["event_store"]["event_count"] != 0:
        raise RuntimeError("Empty console should have zero Event Store rows.")
    if "No Event Store rows yet." not in html:
        raise RuntimeError("Empty console HTML does not explain the empty Event Store.")
    return {
        "status": manifest["status"],
        "event_count": sections["event_store"]["event_count"],
        "artifact_count": sections["artifact_health"]["artifact_count"],
        "html_has_empty_state": True,
    }


def verify_runner_console() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-artifact-console-runner-") as tmp:
        root = Path(tmp)
        init_project(root)
        runner = run_watcher_runner(root)
        manifest, html = build_console(root)
        sections = manifest["sections"]
        runner_section = sections["watcher_runner"]
        study_section = sections["study_adapter"]
        event_section = sections["event_store"]
        if runner_section["accepted_observation_count"] < 3:
            raise RuntimeError(f"Expected runner observations in console: {runner_section}")
        if runner_section["duplicate_observation_count"] < 1:
            raise RuntimeError("Console did not carry runner duplicate debounce evidence.")
        if runner_section["skipped_observation_count"] < 1:
            raise RuntimeError("Console did not carry excluded-path evidence.")
        if runner_section["study_adapter_triggered"] is not True:
            raise RuntimeError("Console did not link Study Adapter gate trigger.")
        if study_section["study_adapter_artifact_count"] < 1:
            raise RuntimeError("Console missed Study Adapter artifacts.")
        if event_section["event_count"] < 3:
            raise RuntimeError("Console missed Event Store rows.")
        required_html = [
            '<meta name="viewport"',
            "@media (max-width: 760px)",
            "Cognitive Loop Artifact Console",
            "Watcher Runner",
            "Study Adapter",
            "Decision, Gate, Loop",
            "Artifact Health",
            "Redacted Manifest",
        ]
        missing = [needle for needle in required_html if needle not in html]
        if missing:
            raise RuntimeError(f"Console HTML missed required structure: {missing}")
        manifest_path = root / ".cognitive-loop" / "artifacts" / "console" / "manifest.json"
        deleted_source = root / event_section["latest_events"][0]["source_path"]
        deleted_source.unlink()
        degraded, _ = build_console(root)
    return {
        "runner_status": runner["status"],
        "console_status": manifest["status"],
        "event_count": event_section["event_count"],
        "accepted_observation_count": runner_section["accepted_observation_count"],
        "duplicate_observation_count": runner_section["duplicate_observation_count"],
        "skipped_observation_count": runner_section["skipped_observation_count"],
        "study_adapter_artifact_count": study_section["study_adapter_artifact_count"],
        "study_adapter_html_linked": bool(study_section["cards"][0]["html_ref"]),
        "manifest_written": manifest_path.name == "manifest.json",
        "degraded_status": degraded["status"],
        "missing_event_source_count": degraded["sections"]["artifact_health"]["missing_event_source_count"],
        "mobile_structure": "ok",
    }


def verify_forbidden_text_rejection() -> bool:
    with tempfile.TemporaryDirectory(prefix="study-anything-artifact-console-secret-") as tmp:
        root = Path(tmp)
        init_project(root)
        events = root / ".cognitive-loop" / "events"
        events.mkdir(parents=True, exist_ok=True)
        (events / "private.json").write_text(
            json.dumps(
                {
                    "schema_version": "private-fixture-v1",
                    "status": "pass",
                    "summary": "diff --git a/private b/private",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(CONSOLE),
                "build",
                "--root",
                str(root),
                "--html",
                "--json",
            ],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    return completed.returncode != 0 and "private-looking text" in completed.stderr


def build_report() -> dict[str, Any]:
    empty = verify_empty_console()
    runner = verify_runner_console()
    forbidden_rejected = verify_forbidden_text_rejection()
    if not forbidden_rejected:
        raise RuntimeError("Console did not reject forbidden private-looking text.")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "console_schema": "cognitive-loop-artifact-console-v1",
        "empty_console": empty,
        "runner_console": runner,
        "failure_modes": {
            "forbidden_private_text_rejected": forbidden_rejected,
            "missing_artifact_degrades_console": runner["degraded_status"] == "partial",
        },
        "privacy": {
            "metadata_only": True,
            "event_json_contents_included": False,
            "html_contents_included": False,
            "markdown_contents_included": False,
            "source_text_included": False,
            "raw_diff_included": False,
            "test_output_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "model_keys_included": False,
            "standalone_frontend_required": False,
            "watcher_daemon_started": False,
        },
        "commands": {
            "console": "python3 scripts/cognitive_loop_artifact_console.py build --html",
            "verify": "python3 scripts/verify_cognitive_loop_artifact_console.py --check",
            "runner": ".venv/bin/python scripts/cognitive_loop_watcher_runner.py run --html --study-adapter",
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
            raise SystemExit(f"Cognitive Loop artifact console report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop artifact console report is stale. "
                "Run: python3 scripts/verify_cognitive_loop_artifact_console.py --write"
            )
    if not args.write and not args.check:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
