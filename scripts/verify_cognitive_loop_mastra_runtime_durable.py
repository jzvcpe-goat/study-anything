#!/usr/bin/env python3
"""Verify durable repo-local Cognitive Loop Mastra suspend/resume receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "platform" / "mastra-runtime"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-mastra-runtime-durable.json"
WATCHER_CLI = ROOT / "scripts" / "cognitive_loop_watcher_ingest.py"
COGNITIVE_LOOP_CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
EVENT_STORE_CLI = ROOT / "scripts" / "cognitive_loop_event_store.py"
SCHEMA_VERSION = "cognitive-loop-mastra-runtime-durable-verification-v1"

FORBIDDEN_TEXT = (
    "sk-proj-",
    "bearer ",
    "raw private source text",
    "learner answer:",
    "diff --git",
    "agent endpoint:",
    "http://127.0.0.1:8787",
    "prompt text:",
    "OPENAI_API_KEY",
)


class MastraRuntimeDurableError(RuntimeError):
    """Readable durable runtime verifier failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_no_forbidden_text(value: Any, *, label: str) -> None:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    leaked = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
    if leaked:
        raise MastraRuntimeDurableError(f"{label} leaked private or secret-like text: {leaked}")


def run_command(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise MastraRuntimeDurableError(
            f"Command failed: {' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    assert_no_forbidden_text(completed.stdout, label=f"stdout:{' '.join(command)}")
    assert_no_forbidden_text(completed.stderr, label=f"stderr:{' '.join(command)}")
    return completed


def run_json(command: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = run_command(command, cwd=cwd)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MastraRuntimeDurableError(
            f"Command did not emit JSON: {' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        ) from exc
    assert_no_forbidden_text(payload, label=f"json:{' '.join(command)}")
    return payload


def ensure_dependencies() -> None:
    if not (PACKAGE_DIR / "node_modules").is_dir():
        command = ["npm", "ci"] if (PACKAGE_DIR / "package-lock.json").is_file() else ["npm", "install"]
        run_command(command, cwd=PACKAGE_DIR)


def verify_package_files() -> list[dict[str, Any]]:
    required = [
        PACKAGE_DIR / "package.json",
        PACKAGE_DIR / "package-lock.json",
        PACKAGE_DIR / "tsconfig.json",
        PACKAGE_DIR / "README.md",
        PACKAGE_DIR / "src" / "runtime.ts",
        PACKAGE_DIR / "src" / "run-once.ts",
        PACKAGE_DIR / "src" / "durable-run.ts",
        PACKAGE_DIR / "src" / "workflows" / "cognitive-loop-mastra-adapter.ts",
        ROOT / "platform" / "mastra" / "cognitive-loop-mastra-adapter.ts",
    ]
    records: list[dict[str, Any]] = []
    for path in required:
        if not path.is_file():
            raise MastraRuntimeDurableError(f"Required runtime file is missing: {relative_path(path)}")
        text = path.read_text(encoding="utf-8")
        assert_no_forbidden_text(text, label=relative_path(path))
        records.append(
            {
                "path": relative_path(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    package = json.loads((PACKAGE_DIR / "package.json").read_text(encoding="utf-8"))
    if package.get("dependencies", {}).get("@mastra/libsql") != "1.13.2":
        raise MastraRuntimeDurableError("Mastra durable runtime must pin @mastra/libsql 1.13.2.")
    if package.get("scripts", {}).get("run-durable") != "tsx src/durable-run.ts":
        raise MastraRuntimeDurableError("Mastra runtime package must expose run-durable.")
    if (
        (PACKAGE_DIR / "src" / "workflows" / "cognitive-loop-mastra-adapter.ts").read_text(encoding="utf-8")
        != (ROOT / "platform" / "mastra" / "cognitive-loop-mastra-adapter.ts").read_text(encoding="utf-8")
    ):
        raise MastraRuntimeDurableError("Runtime workflow source must match the public adapter pack.")
    return records


def build_watcher_event(root: Path) -> dict[str, Any]:
    run_json(
        [
            sys.executable,
            str(COGNITIVE_LOOP_CLI),
            "--root",
            str(root),
            "init",
            "--project-id",
            "durable-mastra-runtime-project",
            "--project-name",
            "Durable Mastra Runtime Project",
            "--json",
        ],
        cwd=ROOT,
    )
    run_json([sys.executable, str(WATCHER_CLI), "--root", str(root), "init-config"], cwd=ROOT)
    watcher_json = ".cognitive-loop/events/durable-watcher.json"
    watcher = run_json(
        [
            sys.executable,
            str(WATCHER_CLI),
            "--root",
            str(root),
            "ingest",
            "--json",
            "--watcher-id",
            "file-change",
            "--target",
            "docs/cognitive-loop-contracts.md",
            "--summary",
            "Captured durable runtime trigger as metadata only.",
            "--ref",
            "path:docs/cognitive-loop-contracts.md",
            "--ref",
            "git:working-tree",
            "--generated-at",
            "2026-06-18T00:00:00Z",
            "--json-output",
            watcher_json,
        ],
        cwd=ROOT,
    )
    rebuild = run_json(
        [
            sys.executable,
            str(EVENT_STORE_CLI),
            "--root",
            str(root),
            "--db",
            ".cognitive-loop/mastra-runtime-durable-event-store.sqlite",
            "rebuild",
            "--event",
            watcher_json,
        ],
        cwd=ROOT,
    )
    watcher_path = root / watcher_json
    watcher_payload = json.loads(watcher_path.read_text(encoding="utf-8"))
    assert_no_forbidden_text(watcher_payload, label="durable watcher payload")
    event_id = watcher_payload["project_event"]["event_id"]
    return {
        "event_id": event_id,
        "json_ref": watcher_json,
        "sha256": sha256_file(watcher_path),
        "ingest_schema": watcher["schema_version"],
        "artifact_schema": watcher_payload["schema_version"],
        "event_store_schema": rebuild["schema_version"],
        "event_store_event_count": rebuild["event_store"]["event_count"],
    }


def run_durable(
    *,
    mode: str,
    storage_file: Path,
    receipt_file: Path,
    run_id: str,
    watcher: dict[str, Any],
    decision: str = "approved",
) -> dict[str, Any]:
    command = [
        "npm",
        "run",
        "--silent",
        "run-durable",
        "--",
        "--json",
        "--mode",
        mode,
        "--storage-file",
        str(storage_file),
        "--run-id",
        run_id,
        "--watcher-event-id",
        str(watcher["event_id"]),
        "--watcher-ref",
        str(watcher["json_ref"]),
        "--watcher-sha",
        str(watcher["sha256"]),
        "--receipt-file",
        str(receipt_file),
    ]
    if mode == "resume":
        command.extend(["--decision", decision])
    return run_json(command, cwd=PACKAGE_DIR)


def load_receipt(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MastraRuntimeDurableError(f"Durable receipt missing: {path.name}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "cognitive-loop-mastra-runtime-durable-receipt-v1":
        raise MastraRuntimeDurableError("Durable receipt schema drifted.")
    assert_no_forbidden_text(payload, label=f"durable receipt:{path.name}")
    return payload


def verify_start(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "cognitive-loop-mastra-runtime-durable-start-v1":
        raise MastraRuntimeDurableError("Durable start schema drifted.")
    if payload.get("status") != "pass":
        raise MastraRuntimeDurableError("Durable start must pass.")
    if (payload.get("started") or {}).get("status") != "suspended":
        raise MastraRuntimeDurableError("Durable start must suspend before resume.")
    recovered = payload.get("recovered_state") or {}
    if recovered.get("found") is not True or recovered.get("status") != "suspended":
        raise MastraRuntimeDurableError("Durable start must recover suspended state from storage.")


def verify_resume(payload: dict[str, Any], *, expected: str) -> None:
    if payload.get("schema_version") != "cognitive-loop-mastra-runtime-durable-resume-v1":
        raise MastraRuntimeDurableError("Durable resume schema drifted.")
    if payload.get("status") != "pass":
        raise MastraRuntimeDurableError("Durable resume must pass.")
    before = payload.get("recovered_before_resume") or {}
    if before.get("found") is not True or before.get("status") != "suspended":
        raise MastraRuntimeDurableError("Durable resume must load suspended state before resuming.")
    result = ((payload.get("resumed") or {}).get("result") or {})
    if not isinstance(result, dict) or result.get("status") != expected:
        raise MastraRuntimeDurableError(f"Durable resume result must be {expected}.")
    after = payload.get("recovered_after_resume") or {}
    if after.get("found") is not True or after.get("status") != "success":
        raise MastraRuntimeDurableError("Durable resume must persist terminal success state.")


def build_report() -> dict[str, Any]:
    files = verify_package_files()
    ensure_dependencies()
    run_command(["npm", "run", "typecheck"], cwd=PACKAGE_DIR)
    with tempfile.TemporaryDirectory(prefix="study-anything-mastra-durable-") as tmp:
        root = Path(tmp)
        watcher = build_watcher_event(root)
        storage_file = root / ".cognitive-loop" / "mastra-runtime-durable.sqlite"
        approved_start_receipt = root / ".cognitive-loop" / "events" / "durable-approved-start.json"
        approved_resume_receipt = root / ".cognitive-loop" / "events" / "durable-approved-resume.json"
        rejected_start_receipt = root / ".cognitive-loop" / "events" / "durable-rejected-start.json"
        rejected_resume_receipt = root / ".cognitive-loop" / "events" / "durable-rejected-resume.json"
        approved_start = run_durable(
            mode="start",
            storage_file=storage_file,
            receipt_file=approved_start_receipt,
            run_id="run-durable-approved",
            watcher=watcher,
        )
        approved_resume = run_durable(
            mode="resume",
            storage_file=storage_file,
            receipt_file=approved_resume_receipt,
            run_id="run-durable-approved",
            watcher=watcher,
            decision="approved",
        )
        rejected_start = run_durable(
            mode="start",
            storage_file=storage_file,
            receipt_file=rejected_start_receipt,
            run_id="run-durable-rejected",
            watcher=watcher,
        )
        rejected_resume = run_durable(
            mode="resume",
            storage_file=storage_file,
            receipt_file=rejected_resume_receipt,
            run_id="run-durable-rejected",
            watcher=watcher,
            decision="rejected",
        )
        for payload in (approved_start, rejected_start):
            verify_start(payload)
        verify_resume(approved_resume, expected="approved")
        verify_resume(rejected_resume, expected="rejected")
        receipts = [
            load_receipt(approved_start_receipt),
            load_receipt(approved_resume_receipt),
            load_receipt(rejected_start_receipt),
            load_receipt(rejected_resume_receipt),
        ]
        if not storage_file.is_file() or storage_file.stat().st_size <= 0:
            raise MastraRuntimeDurableError("Durable libSQL storage file was not created.")
        storage_bytes = storage_file.stat().st_size
        receipt_records = [
            {
                "phase": receipt["phase"],
                "run_id": receipt["run_id"],
                "status": receipt["status"],
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for receipt, path in zip(
                receipts,
                [
                    approved_start_receipt,
                    approved_resume_receipt,
                    rejected_start_receipt,
                    rejected_resume_receipt,
                ],
            )
        ]

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Prove repo-local Mastra workflow snapshots can persist to a local libSQL file, "
            "then resume or bail in a separate Node process from watcher-generated metadata evidence."
        ),
        "files": files,
        "storage": {
            "adapter": "@mastra/libsql",
            "adapter_version": "1.13.2",
            "kind": "local_libsql_file",
            "file_created": True,
            "bytes": storage_bytes,
            "path_included": False,
        },
        "watcher_event": watcher,
        "process_boundary": {
            "separate_start_and_resume_processes": True,
            "approved_run_cross_process_resume": True,
            "rejected_run_cross_process_bail": True,
        },
        "durable_runs": {
            "approved": {
                "start_schema": approved_start["schema_version"],
                "resume_schema": approved_resume["schema_version"],
                "start_status": approved_start["started"]["status"],
                "result_status": approved_resume["resumed"]["result"]["status"],
            },
            "rejected": {
                "start_schema": rejected_start["schema_version"],
                "resume_schema": rejected_resume["schema_version"],
                "start_status": rejected_start["started"]["status"],
                "result_status": rejected_resume["resumed"]["result"]["status"],
            },
        },
        "receipt_records": receipt_records,
        "acceptance": {
            "watcher_generated_event_used": True,
            "libsql_storage_file_created": True,
            "suspended_state_recovered_before_resume": True,
            "approved_gate_resumes_across_process": True,
            "rejected_gate_bails_across_process": True,
            "receipt_records_created": len(receipt_records) == 4,
            "metadata_only": True,
            "report_path": relative_path(REPORT),
            "verification_command": "python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --check",
        },
        "boundaries": {
            "watcher_daemon_started": False,
            "external_agent_called": False,
            "hosted_service_started": False,
            "realtime_html_console_started": False,
        },
        "privacy": {
            "metadata_only": True,
            "raw_source_text_included": False,
            "diff_bodies_included": False,
            "file_contents_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
            "storage_path_included": False,
        },
    }
    assert_no_forbidden_text(report, label="Mastra durable runtime report")
    return report


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
            raise SystemExit(f"Cognitive Loop Mastra durable runtime report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop Mastra durable runtime report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_mastra_runtime_durable.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
