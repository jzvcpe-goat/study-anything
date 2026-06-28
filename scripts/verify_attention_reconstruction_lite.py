#!/usr/bin/env python3
"""Verify Attention Reconstruction Lite CLI output and privacy boundaries."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
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


DEFAULT_REPORT = (
    ROOT / "platform" / "generated" / "study-anything-attention-reconstruction-lite.json"
)


def run_failure_cli(output_dir: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "failure_sandbox_lite.py"),
            "demo",
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(proc.stdout)


def run_attention_cli(output_dir: Path, contract_path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "attention_reconstruction_lite.py"),
            "demo",
            "--failure-contract",
            str(contract_path),
            "--output-dir",
            str(output_dir),
            "--html",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(proc.stdout)
    dual_loop.assert_metadata_only(payload, label="attention-reconstruction-lite-cli-stdout")
    return payload


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-anything-dual-loop-") as tmp:
        root = Path(tmp)
        failure_dir = root / "failure"
        attention_dir = root / "attention"
        run_failure_cli(failure_dir)
        result = run_attention_cli(attention_dir, failure_dir / "failure-contract.json")
        trace = dual_loop.validate_attention_trace(
            dual_loop.load_json(attention_dir / "attention-reconstruction-trace.json")
        )
        summary = dual_loop.validate_attention_summary(
            dual_loop.load_json(attention_dir / "attention-reconstruction-summary.json")
        )
        html_path = attention_dir / "attention-reconstruction-report.html"
        if not html_path.is_file():
            raise RuntimeError("Attention Reconstruction Lite HTML report was not generated")
        dual_loop.assert_metadata_only(
            html_path.read_text(encoding="utf-8"),
            label="attention-reconstruction-lite-html",
        )
    return {
        "schema_version": dual_loop.ATTENTION_RECONSTRUCTION_LITE_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "cli_result_schema": result["schema_version"],
        "artifact_contracts": [trace["schema_version"], summary["schema_version"]],
        "attention": {
            "status": summary["status"],
            "passive_attention_evidence": trace["passive_attention"]["evidence_strength"],
            "active_checkpoint_count": len(trace["active_reconstruction_checkpoints"]),
            "strong_evidence_count": summary["strong_evidence_count"],
            "passive_attention_only": summary["passive_attention_only"],
        },
        "privacy": {
            **dual_loop.PRIVACY_FLAGS,
            "metadata_only_html": True,
            "fine_grained_attention_streams_included": False,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_attention_reconstruction_lite.py --check",
            "demo_command": "python3 scripts/attention_reconstruction_lite.py demo --html",
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
            raise SystemExit(f"Attention Reconstruction Lite report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Attention Reconstruction Lite report is out of date. "
                "Run: python3 scripts/verify_attention_reconstruction_lite.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
