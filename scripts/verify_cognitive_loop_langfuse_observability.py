#!/usr/bin/env python3
"""Verify Cognitive Loop Mastra receipts map to redacted Langfuse DTOs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "platform" / "mastra-runtime"
SERVICE_REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-mastra-runtime-service.json"
DURABLE_REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-mastra-runtime-durable.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-langfuse-observability.json"
SCHEMA_VERSION = "cognitive-loop-langfuse-observability-verification-v1"

FORBIDDEN_TEXT = (
    "sk-proj-",
    "bearer ",
    "raw private source text",
    "learner answer:",
    "diff --git",
    "agent endpoint:",
    "http://127.0.0.1",
    "OPENAI_API_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_HOST=",
)
ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"/Users/[^\"'\s]+"),
    re.compile(r"/private/[^\"'\s]+"),
    re.compile(r"/var/folders/[^\"'\s]+"),
    re.compile(r"/tmp/[^\"'\s]+"),
)


class LangfuseObservabilityError(RuntimeError):
    """Readable Langfuse observability verifier failure."""


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
        raise LangfuseObservabilityError(f"{label} leaked private or secret-like text: {leaked}")
    path_leaks = [pattern.pattern for pattern in ABSOLUTE_PATH_PATTERNS if pattern.search(text)]
    if path_leaks:
        raise LangfuseObservabilityError(f"{label} leaked absolute local paths: {path_leaks}")


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
        raise LangfuseObservabilityError(
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
        raise LangfuseObservabilityError(
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
        PACKAGE_DIR / "src" / "observability.ts",
        PACKAGE_DIR / "src" / "observability-run.ts",
        SERVICE_REPORT,
        DURABLE_REPORT,
    ]
    records: list[dict[str, Any]] = []
    for path in required:
        if not path.is_file():
            raise LangfuseObservabilityError(f"Required observability file is missing: {relative_path(path)}")
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
    if package.get("scripts", {}).get("run-observability") != "tsx src/observability-run.ts":
        raise LangfuseObservabilityError("Mastra runtime package must expose run-observability.")
    return records


def verify_observability_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "cognitive-loop-langfuse-observability-v1":
        raise LangfuseObservabilityError("Langfuse observability DTO schema drifted.")
    if payload.get("status") != "pass":
        raise LangfuseObservabilityError("Langfuse observability DTO must pass.")
    evidence = payload.get("evidence") or {}
    if evidence.get("service_schema") != "cognitive-loop-mastra-runtime-service-verification-v1":
        raise LangfuseObservabilityError("Langfuse observability DTO must bind to the service runtime report.")
    if evidence.get("durable_schema") != "cognitive-loop-mastra-runtime-durable-verification-v1":
        raise LangfuseObservabilityError("Langfuse observability DTO must bind to the durable runtime report.")
    traces = payload.get("traces")
    spans = payload.get("spans")
    generations = payload.get("generations")
    scores = payload.get("scores")
    if not isinstance(traces, list) or len(traces) != 5:
        raise LangfuseObservabilityError("Langfuse observability DTO must emit exactly five traces.")
    if not isinstance(spans, list) or len(spans) < 17:
        raise LangfuseObservabilityError("Langfuse observability DTO must emit workflow step spans.")
    if not isinstance(generations, list) or len(generations) != 5:
        raise LangfuseObservabilityError("Langfuse observability DTO must emit one generation DTO per run.")
    if not isinstance(scores, list) or len(scores) < 35:
        raise LangfuseObservabilityError("Langfuse observability DTO must emit score DTOs for risk, gates, privacy, cost, and latency.")

    trace_ids = {str(trace.get("id")) for trace in traces if isinstance(trace, dict)}
    expected_kinds = {
        "service_approved",
        "service_rejected",
        "service_not_required",
        "durable_approved",
        "durable_rejected",
    }
    found_kinds = {
        str((trace.get("metadata") or {}).get("run_kind"))
        for trace in traces
        if isinstance(trace, dict) and isinstance(trace.get("metadata"), dict)
    }
    if found_kinds != expected_kinds:
        raise LangfuseObservabilityError(f"Langfuse traces missed run kinds: {sorted(expected_kinds - found_kinds)}")
    for collection_name, collection in (("spans", spans), ("generations", generations), ("scores", scores)):
        for item in collection:
            if not isinstance(item, dict) or item.get("trace_id") not in trace_ids:
                raise LangfuseObservabilityError(f"Langfuse {collection_name} item references an unknown trace.")
    span_names = {str(span.get("name")) for span in spans if isinstance(span, dict)}
    for required_span in (
        "validate-cognitive-loop-evidence",
        "human-mastery-gate",
        "event-store-projection",
        "durable-state-recovered",
        "durable-receipt-written",
    ):
        if required_span not in span_names:
            raise LangfuseObservabilityError(f"Langfuse span mapping is missing {required_span}.")
    score_names = {str(score.get("name")) for score in scores if isinstance(score, dict)}
    for required_score in (
        "risk_score",
        "human_gate_required",
        "human_gate_resolution",
        "privacy_metadata_only",
        "latency_ms",
        "token_count",
        "cost_usd",
    ):
        if required_score not in score_names:
            raise LangfuseObservabilityError(f"Langfuse score mapping is missing {required_score}.")
    for generation in generations:
        if not isinstance(generation, dict):
            raise LangfuseObservabilityError("Langfuse generation item must be an object.")
        if generation.get("input_omitted") is not True or generation.get("output_omitted") is not True:
            raise LangfuseObservabilityError("Langfuse generation DTO must omit raw input and output.")
        metadata = generation.get("metadata") or {}
        if not isinstance(metadata, dict) or metadata.get("external_agent_called") is not False:
            raise LangfuseObservabilityError("Langfuse generation DTO must not claim external Agent execution.")

    receipt = payload.get("receipt") or {}
    if receipt.get("schema_version") != "cognitive-loop-langfuse-receipt-v1":
        raise LangfuseObservabilityError("Langfuse local receipt schema drifted.")
    if receipt.get("local_only") is not True or receipt.get("calls_real_langfuse") is not False:
        raise LangfuseObservabilityError("Langfuse receipt must remain local-only.")
    counts = receipt.get("dto_counts") or {}
    if counts != {
        "traces": len(traces),
        "spans": len(spans),
        "generations": len(generations),
        "scores": len(scores),
    }:
        raise LangfuseObservabilityError("Langfuse receipt DTO counts drifted.")
    boundaries = payload.get("boundaries") or {}
    for key in (
        "dto_only",
        "metadata_only",
    ):
        if boundaries.get(key) is not True:
            raise LangfuseObservabilityError(f"Langfuse boundary {key} must be true.")
    for key in (
        "calls_real_langfuse",
        "imports_langfuse_sdk",
        "network_calls",
        "external_agent_called",
        "hosted_service_started",
    ):
        if boundaries.get(key) is not False:
            raise LangfuseObservabilityError(f"Langfuse boundary {key} must be false.")
    privacy = payload.get("privacy") or {}
    if privacy.get("metadata_only") is not True:
        raise LangfuseObservabilityError("Langfuse privacy.metadata_only must be true.")
    for key in (
        "raw_source_text_included",
        "source_bodies_included",
        "diff_bodies_included",
        "learner_answers_included",
        "agent_endpoints_included",
        "agent_metadata_included",
        "prompt_text_included",
        "real_model_keys_stored",
        "langfuse_secret_included",
        "storage_path_included",
        "absolute_paths_included",
    ):
        if privacy.get(key) is not False:
            raise LangfuseObservabilityError(f"Langfuse privacy.{key} must be false.")


def build_report() -> dict[str, Any]:
    files = verify_package_files()
    ensure_dependencies()
    run_command(["npm", "run", "typecheck"], cwd=PACKAGE_DIR)
    with tempfile.TemporaryDirectory(prefix="study-anything-langfuse-observability-") as tmp:
        receipt_file = Path(tmp) / "langfuse-observability-receipt.json"
        payload = run_json(
            [
                "npm",
                "run",
                "--silent",
                "run-observability",
                "--",
                "--json",
                "--service-report",
                str(SERVICE_REPORT),
                "--durable-report",
                str(DURABLE_REPORT),
                "--receipt-file",
                str(receipt_file),
            ],
            cwd=PACKAGE_DIR,
        )
        if not receipt_file.is_file():
            raise LangfuseObservabilityError("Langfuse local receipt file was not written.")
        receipt_payload = json.loads(receipt_file.read_text(encoding="utf-8"))
        if receipt_payload != payload:
            raise LangfuseObservabilityError("Langfuse local receipt file does not match stdout payload.")
        verify_observability_payload(payload)
        receipt_record = {
            "bytes": receipt_file.stat().st_size,
            "sha256": sha256_file(receipt_file),
        }

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": (
            "Prove repo-local Cognitive Loop Mastra service and durable receipts map to "
            "Langfuse trace/span/generation/score DTOs without calling Langfuse or leaking "
            "source text, diffs, learner answers, Agent endpoints, Agent metadata, prompts, keys, or local paths."
        ),
        "files": files,
        "observability": payload,
        "receipt_record": receipt_record,
        "acceptance": {
            "service_report_mapped": True,
            "durable_report_mapped": True,
            "trace_dtos_created": True,
            "span_dtos_created": True,
            "generation_dtos_created": True,
            "score_dtos_created": True,
            "risk_human_gate_eval_scores_created": True,
            "local_receipt_created": True,
            "metadata_only": True,
            "report_path": relative_path(REPORT),
            "verification_command": "python3 scripts/verify_cognitive_loop_langfuse_observability.py --check",
        },
        "boundaries": {
            "calls_real_langfuse": False,
            "imports_langfuse_sdk": False,
            "network_calls": False,
            "external_agent_called": False,
            "hosted_service_started": False,
        },
        "privacy": payload["privacy"],
    }
    assert_no_forbidden_text(report, label="Langfuse observability report")
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
            raise SystemExit(f"Cognitive Loop Langfuse observability report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Cognitive Loop Langfuse observability report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_langfuse_observability.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
