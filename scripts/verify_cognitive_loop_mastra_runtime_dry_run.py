#!/usr/bin/env python3
"""Verify a metadata-only Cognitive Loop Mastra runtime dry-run harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-mastra-runtime-dry-run.json"
CLI = ROOT / "scripts" / "cognitive_loop_cli.py"
EVENT_STORE = ROOT / "scripts" / "cognitive_loop_event_store.py"
WATCHER_CLI = ROOT / "scripts" / "cognitive_loop_watcher_ingest.py"
ADAPTER_REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-mastra-adapter.json"
ADAPTER_MANIFEST = ROOT / "platform" / "mastra" / "manifest.json"
ADAPTER_TEMPLATE = ROOT / "platform" / "mastra" / "cognitive-loop-mastra-adapter.ts"
SCHEMA_VERSION = "cognitive-loop-mastra-runtime-dry-run-verification-v1"

FORBIDDEN_TEXT = (
    "sk-proj-",
    "bearer ",
    "raw private source text",
    "learner answer:",
    "diff --git",
    "agent endpoint:",
    "http://127.0.0.1:8787",
    "prompt text:",
)


class MastraRuntimeDryRunError(RuntimeError):
    """Readable verifier failure."""


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
        raise MastraRuntimeDryRunError(f"{label} leaked private or secret-like text: {leaked}")


def run_json(command: list[str], *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MastraRuntimeDryRunError(
            f"Command did not emit JSON: {' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        ) from exc
    assert_no_forbidden_text(payload, label=f"command output:{command[1] if len(command) > 1 else command[0]}")
    return payload


def run_cli(args: list[str], *, root: Path) -> dict[str, Any]:
    return run_json([sys.executable, str(CLI), "--root", str(root), *args], cwd=ROOT)


def run_store(args: list[str], *, root: Path) -> dict[str, Any]:
    return run_json([sys.executable, str(EVENT_STORE), "--root", str(root), *args], cwd=ROOT)


def run_watcher(args: list[str], *, root: Path) -> dict[str, Any]:
    return run_json([sys.executable, str(WATCHER_CLI), "--root", str(root), *args], cwd=ROOT)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise MastraRuntimeDryRunError(f"Required file is missing: {relative_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MastraRuntimeDryRunError(f"Required file is invalid JSON: {relative_path(path)}") from exc
    assert_no_forbidden_text(payload, label=relative_path(path))
    return payload


def require_adapter_pack() -> dict[str, Any]:
    manifest = load_json(ADAPTER_MANIFEST)
    adapter_report = load_json(ADAPTER_REPORT)
    if manifest.get("status") != "contract_pack":
        raise MastraRuntimeDryRunError("Mastra adapter manifest must remain a contract_pack.")
    if manifest.get("claim_boundaries", {}).get("mastra_runtime_integrated") is not False:
        raise MastraRuntimeDryRunError("Adapter manifest must not claim Mastra runtime integration.")
    if adapter_report.get("schema_version") != "cognitive-loop-mastra-adapter-verification-v1":
        raise MastraRuntimeDryRunError("Mastra adapter report schema drifted.")
    if adapter_report.get("status") != "pass":
        raise MastraRuntimeDryRunError("Mastra adapter report must pass before runtime dry-run.")
    if not ADAPTER_TEMPLATE.is_file():
        raise MastraRuntimeDryRunError(f"Required adapter template is missing: {relative_path(ADAPTER_TEMPLATE)}")
    template_text = ADAPTER_TEMPLATE.read_text(encoding="utf-8")
    for marker in ("createWorkflow", "createStep", "suspendSchema", "resumeSchema", "suspend(", "bail("):
        if marker not in template_text:
            raise MastraRuntimeDryRunError(f"Mastra adapter template is missing marker: {marker}")
    assert_no_forbidden_text(template_text, label=relative_path(ADAPTER_TEMPLATE))
    return {
        "manifest_schema": manifest["schema_version"],
        "adapter_report_schema": adapter_report["schema_version"],
        "adapter_id": manifest["adapter_id"],
        "adapter_version": manifest["adapter_version"],
        "template_sha256": sha256_file(ADAPTER_TEMPLATE),
    }


def build_event_artifacts(root: Path) -> dict[str, Any]:
    run_cli(
        [
            "init",
            "--project-id",
            "external-mastra-adopter-project",
            "--project-name",
            "External Mastra Adopter Project",
            "--json",
        ],
        root=root,
    )
    run_once = run_cli(
        [
            "run-once",
            "--html",
            "--json",
            "--risk-level",
            "high",
            "--objective",
            "Dry-run a repository-started Cognitive Loop Mastra runtime boundary.",
            "--change-summary",
            "Validate redacted runtime inputs, suspend on Human Mastery Gate, and project Event Store metadata.",
            "--output",
            ".cognitive-loop/artifacts/mastra-runtime-run-once.html",
            "--json-output",
            ".cognitive-loop/events/mastra-runtime-run-once.json",
        ],
        root=root,
    )
    snapshot = run_cli(
        [
            "snapshot",
            "--html",
            "--json",
            "--path",
            "platform/mastra/cognitive-loop-mastra-adapter.ts",
            "--path",
            "platform/generated/study-anything-cognitive-loop-mastra-adapter.json",
            "--output",
            ".cognitive-loop/artifacts/mastra-runtime-snapshot.html",
            "--json-output",
            ".cognitive-loop/events/mastra-runtime-snapshot.json",
        ],
        root=root,
    )
    approved = run_cli(
        [
            "gate",
            "--approve",
            "--html",
            "--json",
            "--decision-id",
            "dec-cognitive-loop-run-once",
            "--rationale",
            "Operator verified the dry-run evidence, risk, rollback, and resume boundary.",
            "--evidence-ref",
            "artifact:.cognitive-loop/artifacts/mastra-runtime-run-once.html",
            "--evidence-ref",
            "artifact:.cognitive-loop/artifacts/mastra-runtime-snapshot.html",
            "--output",
            ".cognitive-loop/artifacts/mastra-runtime-human-gate-approved.html",
            "--json-output",
            ".cognitive-loop/events/mastra-runtime-human-gate-approved.json",
        ],
        root=root,
    )
    rejected = run_cli(
        [
            "gate",
            "--reject",
            "--json",
            "--decision-id",
            "dec-cognitive-loop-run-once",
            "--rationale",
            "Operator rejected the dry-run until runtime evidence improves.",
            "--json-output",
            ".cognitive-loop/events/mastra-runtime-human-gate-rejected.json",
        ],
        root=root,
    )
    run_watcher(["init-config"], root=root)
    watcher = run_watcher(
        [
            "ingest",
            "--json",
            "--watcher-id",
            "file-change",
            "--target",
            "docs/cognitive-loop-contracts.md",
            "--summary",
            "Captured Mastra runtime dry-run trigger as metadata only.",
            "--ref",
            "path:docs/cognitive-loop-contracts.md",
            "--ref",
            "git:working-tree",
            "--generated-at",
            "2026-06-18T00:00:00Z",
            "--json-output",
            ".cognitive-loop/events/mastra-runtime-watcher.json",
        ],
        root=root,
    )
    event_paths = [
        ".cognitive-loop/events/mastra-runtime-run-once.json",
        ".cognitive-loop/events/mastra-runtime-snapshot.json",
        ".cognitive-loop/events/mastra-runtime-human-gate-approved.json",
        ".cognitive-loop/events/mastra-runtime-human-gate-rejected.json",
        ".cognitive-loop/events/mastra-runtime-watcher.json",
    ]
    db_path = ".cognitive-loop/mastra-runtime-dry-run.sqlite"
    store_args: list[str] = ["--db", db_path, "rebuild"]
    for event_path in event_paths:
        store_args.extend(["--event", event_path])
    rebuild = run_store(store_args, root=root)
    event_store_export = run_store(
        [
            "--db",
            db_path,
            "export",
            "--json",
            "--html",
            "--output",
            ".cognitive-loop/artifacts/mastra-runtime-event-store.html",
            "--json-output",
            ".cognitive-loop/events/mastra-runtime-event-store.json",
        ],
        root=root,
    )
    assert_no_forbidden_text(event_store_export, label="Mastra runtime Event Store export")
    return {
        "run_once": run_once,
        "snapshot": snapshot,
        "approved_gate": approved,
        "rejected_gate": rejected,
        "watcher": watcher,
        "event_paths": event_paths,
        "event_store_rebuild": rebuild,
        "event_store_export": event_store_export,
    }


def artifact_digest(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise MastraRuntimeDryRunError(f"Expected dry-run artifact is missing: {relative}")
    data = path.read_bytes()
    assert_no_forbidden_text(data.decode("utf-8", errors="replace"), label=relative)
    return {
        "path": relative,
        "bytes": len(data),
        "privacy_scan_passed": True,
        "content_hash_omitted": "temporary artifacts include generated timestamps",
    }


def build_runtime_transcript(artifacts: dict[str, Any]) -> dict[str, Any]:
    run_once = artifacts["run_once"]
    approved = artifacts["approved_gate"]
    rejected = artifacts["rejected_gate"]
    event_store = artifacts["event_store_export"]["event_store"]
    decision = run_once["decision_card"]
    loop = run_once["loop_run"]
    if loop["status"] != "suspended":
        raise MastraRuntimeDryRunError("High-risk runtime dry-run must suspend before Human Mastery Gate.")
    if decision["human_mastery_gate"]["status"] != "pending":
        raise MastraRuntimeDryRunError("High-risk runtime dry-run must produce a pending gate.")
    if approved["decision_card"]["human_mastery_gate"]["status"] != "approved":
        raise MastraRuntimeDryRunError("Approved gate artifact did not approve the Human Mastery Gate.")
    if rejected["decision_card"]["human_mastery_gate"]["status"] != "rejected":
        raise MastraRuntimeDryRunError("Rejected gate artifact did not reject the Human Mastery Gate.")
    if event_store["event_count"] < 4 or event_store["artifact_count"] != 5:
        raise MastraRuntimeDryRunError(
            "Event Store projection must contain the dry-run artifacts and watcher event."
        )
    return {
        "input_contract": {
            "projectId": loop["project_id"],
            "loopRunId": loop["run_id"],
            "decisionCardId": decision["decision_id"],
            "eventStorePath": ".cognitive-loop/mastra-runtime-dry-run.sqlite",
            "artifactRefs": artifacts["event_paths"],
            "risk": {
                "level": decision["risk"]["level"],
                "requiresHumanGate": decision["human_mastery_gate"]["required"],
            },
            "constraints": {
                "metadataOnly": True,
                "rawSourceTextIncluded": False,
                "diffBodiesIncluded": False,
                "modelKeysIncluded": False,
            },
        },
        "steps": [
            {
                "id": "validate-cognitive-loop-evidence",
                "status": "succeeded",
                "evidence_count": len(artifacts["event_paths"]),
                "source": "scripts/cognitive_loop_cli.py",
            },
            {
                "id": "human-mastery-gate",
                "status": "suspended",
                "reason": "high risk requires Human Mastery Gate",
                "mastra_semantic": "suspend",
            },
            {
                "id": "resume-approved-run",
                "status": "succeeded",
                "gate_status": "approved",
                "mastra_semantic": "resume",
            },
            {
                "id": "bail-rejected-run",
                "status": "rejected",
                "gate_status": "rejected",
                "mastra_semantic": "bail",
            },
            {
                "id": "project-event-store-metadata",
                "status": "succeeded",
                "event_count": event_store["event_count"],
                "artifact_count": event_store["artifact_count"],
            },
        ],
        "output_contract": {
            "status": "dry_run_passed",
            "loopRunId": loop["run_id"],
            "decisionCardId": decision["decision_id"],
            "humanGate": {
                "suspended": True,
                "approvedResumeCovered": True,
                "rejectedBailCovered": True,
            },
            "eventStoreProjection": {
                "engine": "sqlite",
                "event_count": event_store["event_count"],
                "artifact_count": event_store["artifact_count"],
                "unique_event_count_expected_minimum": 3,
                "content_included": False,
            },
        },
    }


def build_file_records(paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            raise MastraRuntimeDryRunError(f"Required file is missing: {relative_path(path)}")
        records.append(
            {
                "path": relative_path(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return records


def build_report() -> dict[str, Any]:
    adapter = require_adapter_pack()
    with tempfile.TemporaryDirectory(prefix="study-anything-mastra-runtime-dry-run-") as tmp:
        root = Path(tmp)
        artifacts = build_event_artifacts(root)
        transcript = build_runtime_transcript(artifacts)
        artifact_records = [
            artifact_digest(root, path)
            for path in [
                ".cognitive-loop/events/mastra-runtime-run-once.json",
                ".cognitive-loop/events/mastra-runtime-snapshot.json",
                ".cognitive-loop/events/mastra-runtime-human-gate-approved.json",
                ".cognitive-loop/events/mastra-runtime-human-gate-rejected.json",
                ".cognitive-loop/events/mastra-runtime-watcher.json",
                ".cognitive-loop/events/mastra-runtime-event-store.json",
                ".cognitive-loop/artifacts/mastra-runtime-event-store.html",
            ]
        ]

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Prove a repository-started Cognitive Loop Mastra runtime can be rehearsed with "
            "metadata-only local evidence before production Mastra daemon/storage operations ship."
        ),
        "goal_status": {
            "runtime_dry_run_harness": "implemented",
            "repo_local_mastra_runtime_mvp": "implemented",
            "production_mastra_runtime_operations": "planned",
            "watcher_daemon": "planned",
            "realtime_html_console": "planned",
        },
        "adapter_source": adapter,
        "files": build_file_records(
            [
                ADAPTER_MANIFEST,
                ADAPTER_TEMPLATE,
                ADAPTER_REPORT,
                Path(__file__).resolve(),
            ]
        ),
        "artifact_records": artifact_records,
        "runtime_transcript": transcript,
        "acceptance": {
            "high_risk_run_suspends": True,
            "approved_gate_maps_to_resume": True,
            "rejected_gate_maps_to_bail": True,
            "event_store_projection_rebuilt": True,
            "adapter_contract_used_as_source": True,
            "report_path": relative_path(REPORT),
            "verification_command": "python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check",
        },
        "runtime_boundaries": {
            "mastra_runtime_started": False,
            "typescript_compiled_in_this_repo": False,
            "watcher_daemon_started": False,
            "realtime_html_console_started": False,
            "external_agent_called": False,
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
        },
        "commands": {
            "adapter_check": "python3 scripts/verify_cognitive_loop_mastra_adapter.py --check",
            "runtime_dry_run_check": "python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --check",
            "event_store_rebuild": "python3 scripts/cognitive_loop_event_store.py rebuild",
        },
    }
    assert_no_forbidden_text(report, label="Mastra runtime dry-run report")
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
            raise SystemExit(f"Cognitive Loop Mastra runtime dry-run report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop Mastra runtime dry-run report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_mastra_runtime_dry_run.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
