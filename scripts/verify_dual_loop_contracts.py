#!/usr/bin/env python3
"""Verify Dual-Loop MVP schemas and metadata-only contract boundaries."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DUAL_LOOP_MODULE_PATH = ROOT / "apps" / "api" / "study_anything" / "core" / "dual_loop.py"


def _load_dual_loop() -> Any:
    spec = importlib.util.spec_from_file_location("study_anything_dual_loop", DUAL_LOOP_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Dual-Loop module: {DUAL_LOOP_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dual_loop = _load_dual_loop()


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-dual-loop-contracts.json"
SCHEMA_DIR = ROOT / "platform" / "schemas" / "dual-loop"
REQUIRED_SCHEMAS = {
    "failure-contract-v1.schema.json": dual_loop.FAILURE_CONTRACT_SCHEMA_VERSION,
    "sandbox-receipt-v1.schema.json": dual_loop.SANDBOX_RECEIPT_SCHEMA_VERSION,
    "attention-reconstruction-trace-v1.schema.json": dual_loop.ATTENTION_TRACE_SCHEMA_VERSION,
    "attention-reconstruction-summary-v1.schema.json": dual_loop.ATTENTION_SUMMARY_SCHEMA_VERSION,
    "dual-loop-gate-receipt-v1.schema.json": dual_loop.DUAL_LOOP_GATE_RECEIPT_SCHEMA_VERSION,
}


def load_schema_report() -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for filename, schema_version in REQUIRED_SCHEMAS.items():
        path = SCHEMA_DIR / filename
        if not path.is_file():
            raise RuntimeError(f"Missing Dual-Loop schema: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("$id") != schema_version:
            raise RuntimeError(f"{path} must use $id {schema_version}")
        if payload.get("properties", {}).get("schema_version", {}).get("const") != schema_version:
            raise RuntimeError(f"{path} must pin schema_version const {schema_version}")
        reports.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "schema_version": schema_version,
                "sha256": dual_loop.sha256_text(path.read_text(encoding="utf-8")),
            }
        )
    return reports


def exercise_failure_modes() -> dict[str, str]:
    failures: dict[str, str] = {}
    bad_contract = dual_loop.failure_contract_demo()
    bad_contract["raw_source_text"] = "raw private source text"
    try:
        dual_loop.validate_failure_contract(bad_contract)
    except dual_loop.DualLoopContractError as exc:
        failures["raw_source_text_rejected"] = str(exc)

    bad_trace = dual_loop.attention_trace_demo()
    bad_trace["active_reconstruction_checkpoints"][0]["note"] = (
        "OPENAI_API_KEY=sk-proj-abcdefghijklmnop"
    )
    try:
        dual_loop.validate_attention_trace(bad_trace)
    except dual_loop.DualLoopContractError as exc:
        failures["secret_like_attention_trace_rejected"] = str(exc)

    bad_summary = dual_loop.attention_summary_demo()
    bad_summary["passive_attention_only"] = True
    try:
        dual_loop.validate_attention_summary(bad_summary)
    except dual_loop.DualLoopContractError as exc:
        failures["passive_attention_only_rejected"] = str(exc)

    bad_receipt = dual_loop.sandbox_receipt_demo()
    bad_receipt["mutation_summary"]["production_mutation"] = True
    try:
        dual_loop.validate_sandbox_receipt(bad_receipt)
    except dual_loop.DualLoopContractError as exc:
        failures["production_mutation_rejected"] = str(exc)

    required = {
        "raw_source_text_rejected",
        "secret_like_attention_trace_rejected",
        "passive_attention_only_rejected",
        "production_mutation_rejected",
    }
    missing = sorted(required - set(failures))
    if missing:
        raise RuntimeError(f"Expected Dual-Loop failure modes missing: {missing}")
    return failures


def build_report() -> dict[str, Any]:
    contract = dual_loop.validate_failure_contract(dual_loop.failure_contract_demo())
    sandbox = dual_loop.validate_sandbox_receipt(dual_loop.sandbox_receipt_demo())
    trace = dual_loop.validate_attention_trace(dual_loop.attention_trace_demo())
    summary = dual_loop.validate_attention_summary(dual_loop.attention_summary_demo())
    gate = dual_loop.evaluate_dual_loop_gate(contract, sandbox, summary)
    return {
        "schema_version": dual_loop.DUAL_LOOP_CONTRACTS_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "schema_files": load_schema_report(),
        "artifact_contracts": {
            "failure_contract": contract["schema_version"],
            "sandbox_receipt": sandbox["schema_version"],
            "attention_reconstruction_trace": trace["schema_version"],
            "attention_reconstruction_summary": summary["schema_version"],
            "dual_loop_gate_receipt": gate["schema_version"],
        },
        "privacy": {
            **dual_loop.PRIVACY_FLAGS,
            "metadata_only_verifier": True,
            "secret_like_values_rejected": True,
        },
        "architecture": {
            **dual_loop.ISOLATION_BOUNDARY,
            "model_calls_in_v0_1": False,
            "daemon_or_hosted_service_in_v0_1": False,
            "deterministic_fixtures_first": True,
        },
        "failure_modes": exercise_failure_modes(),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_dual_loop_contracts.py --check",
            "failure_sandbox_command": "python3 scripts/verify_failure_sandbox_lite.py --check",
            "attention_command": "python3 scripts/verify_attention_reconstruction_lite.py --check",
            "gate_command": "python3 scripts/verify_dual_loop_gate.py --check",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    output = Path(args.output)
    report = build_report()
    serialized = dual_loop.dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Dual-Loop contracts report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Dual-Loop contracts report is out of date. "
                "Run: python3 scripts/verify_dual_loop_contracts.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
