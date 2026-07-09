#!/usr/bin/env python3
"""Verify the repository-started Cognitive Loop Mastra runtime MVP."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "platform" / "mastra-runtime"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-mastra-runtime-service.json"
SCHEMA_VERSION = "cognitive-loop-mastra-runtime-service-verification-v1"

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


class MastraRuntimeServiceError(RuntimeError):
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
        raise MastraRuntimeServiceError(f"{label} leaked private or secret-like text: {leaked}")


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
        raise MastraRuntimeServiceError(
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
        raise MastraRuntimeServiceError(
            f"Command did not emit JSON: {' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        ) from exc
    assert_no_forbidden_text(payload, label=f"json:{' '.join(command)}")
    return payload


def ensure_dependencies() -> None:
    if not (PACKAGE_DIR / "node_modules").is_dir():
        package_lock = PACKAGE_DIR / "package-lock.json"
        command = ["npm", "ci"] if package_lock.is_file() else ["npm", "install"]
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
            raise MastraRuntimeServiceError(f"Required runtime file is missing: {relative_path(path)}")
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
    if package.get("dependencies", {}).get("@mastra/core") != "1.43.0":
        raise MastraRuntimeServiceError("Mastra runtime package must pin @mastra/core 1.43.0.")
    if package.get("dependencies", {}).get("@mastra/libsql") != "1.13.2":
        raise MastraRuntimeServiceError("Mastra runtime package must pin @mastra/libsql 1.13.2.")
    if package.get("scripts", {}).get("run-durable") != "tsx src/durable-run.ts":
        raise MastraRuntimeServiceError("Mastra runtime package must expose the durable run script.")
    if package.get("scripts", {}).get("verify") != "npm run --silent typecheck && npm run --silent run-once -- --json":
        raise MastraRuntimeServiceError("Mastra runtime package must expose a deterministic verify script.")
    runtime_adapter = PACKAGE_DIR / "src" / "workflows" / "cognitive-loop-mastra-adapter.ts"
    public_adapter = ROOT / "platform" / "mastra" / "cognitive-loop-mastra-adapter.ts"
    if runtime_adapter.read_text(encoding="utf-8") != public_adapter.read_text(encoding="utf-8"):
        raise MastraRuntimeServiceError("Mastra runtime workflow source must stay identical to the public adapter pack.")
    return records


def verify_runtime_output(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "cognitive-loop-mastra-runtime-service-v1":
        raise MastraRuntimeServiceError("Mastra runtime output schema drifted.")
    if payload.get("status") != "pass":
        raise MastraRuntimeServiceError("Mastra runtime output must pass.")
    if payload.get("workflow_registration_key") != "cognitiveLoopRuntimeAdapterWorkflow":
        raise MastraRuntimeServiceError("Mastra runtime must use the registered workflow key.")
    boundaries = payload.get("boundaries") or {}
    for key in ("repository_started_mastra_instance", "metadata_only"):
        if boundaries.get(key) is not True:
            raise MastraRuntimeServiceError(f"Mastra runtime boundary {key} must be true.")
    for key in (
        "raw_source_text_included",
        "diff_bodies_included",
        "agent_secrets_included",
        "model_keys_included",
        "external_agent_called",
    ):
        if boundaries.get(key) is not False:
            raise MastraRuntimeServiceError(f"Mastra runtime boundary {key} must be false.")
    paths = payload.get("paths") or {}
    approved = (paths.get("approved") or {}).get("resumed") or {}
    rejected = (paths.get("rejected") or {}).get("resumed") or {}
    not_required = paths.get("not_required") or {}
    if ((paths.get("approved") or {}).get("started") or {}).get("status") != "suspended":
        raise MastraRuntimeServiceError("Approved path must begin with suspended status.")
    if approved.get("status") != "success":
        raise MastraRuntimeServiceError("Approved path must resume to success.")
    if ((paths.get("rejected") or {}).get("started") or {}).get("status") != "suspended":
        raise MastraRuntimeServiceError("Rejected path must begin with suspended status.")
    if rejected.get("status") not in {"failed", "success"}:
        raise MastraRuntimeServiceError("Rejected path must return a terminal Mastra status.")
    rejected_result = rejected.get("result") or {}
    if isinstance(rejected_result, dict) and rejected_result.get("status") != "rejected":
        raise MastraRuntimeServiceError("Rejected path result must preserve rejected status.")
    if not_required.get("status") != "success":
        raise MastraRuntimeServiceError("Low-risk not-required path must succeed.")


def build_report() -> dict[str, Any]:
    file_records = verify_package_files()
    ensure_dependencies()
    run_command(["npm", "run", "typecheck"], cwd=PACKAGE_DIR)
    runtime_payload = run_json(["npm", "run", "--silent", "run-once", "--", "--json"], cwd=PACKAGE_DIR)
    verify_runtime_output(runtime_payload)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Prove this repository can start a minimal Mastra runtime instance for the "
            "Cognitive Loop adapter workflow while keeping all evidence metadata-only."
        ),
        "files": file_records,
        "runtime": runtime_payload,
        "acceptance": {
            "repository_started_mastra_instance": True,
            "workflow_registered": True,
            "high_risk_run_suspends": True,
            "approved_gate_resumes": True,
            "rejected_gate_bails": True,
            "low_risk_run_skips_gate": True,
            "metadata_only": True,
            "report_path": relative_path(REPORT),
            "verification_command": "python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --check",
        },
        "privacy": {
            "raw_source_text_included": False,
            "diff_bodies_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
        },
        "boundaries": {
            "watcher_daemon_started": False,
            "realtime_html_console_started": False,
            "hosted_service_started": False,
            "external_agent_called": False,
        },
    }
    assert_no_forbidden_text(report, label="Mastra runtime service report")
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
            raise SystemExit(f"Cognitive Loop Mastra runtime service report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop Mastra runtime service report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_mastra_runtime_service.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
