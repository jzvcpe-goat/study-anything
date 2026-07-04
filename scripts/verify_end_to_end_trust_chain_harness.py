#!/usr/bin/env python3
"""Verify the metadata-only end-to-end trust-chain harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from study_anything.core import dual_loop  # noqa: E402
import end_to_end_trust_chain_harness as harness  # noqa: E402


FIXTURE = ROOT / "fixtures" / "end-to-end-trust-chain-harness" / "pass" / "end-to-end-trust-chain-report.json"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "end-to-end-trust-chain-harness-v1.schema.json"

EXPECTED_CASE_IDS = {
    "pass",
    "blocked-product-loop-run",
    "blocked-automatic-customer-send",
    "blocked-missing-human-scope",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def verify_schema() -> dict[str, str]:
    schema = load_json(SCHEMA_FILE)
    if schema.get("$id") != harness.REPORT_SCHEMA_VERSION:
        raise RuntimeError("End-to-End Trust Chain schema id drifted")
    if (
        schema.get("properties", {})
        .get("schema_version", {})
        .get("const")
        != harness.REPORT_SCHEMA_VERSION
    ):
        raise RuntimeError("End-to-End Trust Chain schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": harness.REPORT_SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def verify_cli(expected_core_report: Mapping[str, Any]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-end-to-end-trust-chain-") as tmp:
        tmpdir = Path(tmp)
        report = tmpdir / "report.json"
        markdown = tmpdir / "report.md"
        html = tmpdir / "report.html"
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "end_to_end_trust_chain_harness.py"),
                "--output",
                str(report),
                "--markdown-output",
                str(markdown),
                "--html-output",
                str(html),
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        stdout = json.loads(proc.stdout)
        dual_loop.assert_metadata_only(stdout, label="end-to-end-trust-chain-cli")
        if stdout.get("schema_version") != harness.CLI_SCHEMA_VERSION:
            raise RuntimeError("End-to-End Trust Chain CLI schema drifted")
        if load_json(report) != expected_core_report:
            raise RuntimeError("End-to-End Trust Chain CLI report drifted")
        if not markdown.is_file() or not html.is_file():
            raise RuntimeError("End-to-End Trust Chain CLI did not write markdown/html reports")
        dual_loop.assert_metadata_only(html.read_text(encoding="utf-8"), label="end-to-end-trust-chain-html")


def negative_checks(report: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(case_id: str, payload: Mapping[str, Any]) -> None:
        try:
            harness.validate_report(payload)
        except Exception as exc:  # noqa: BLE001
            failures[case_id] = str(exc)
            return
        raise RuntimeError(f"End-to-End Trust Chain negative case unexpectedly passed: {case_id}")

    raw_body = json.loads(dual_loop.dump_json(report))
    raw_body["chain_steps"][0]["raw_body_included"] = True
    expect_rejected("raw_body_ref_rejected", raw_body)

    failed_continuity = json.loads(dual_loop.dump_json(report))
    failed_continuity["continuity_checks"][0]["status"] = "fail"
    expect_rejected("failed_continuity_rejected", failed_continuity)

    automatic_send = json.loads(dual_loop.dump_json(report))
    automatic_send["runtime"]["automatic_customer_send_performed"] = True
    expect_rejected("automatic_customer_send_rejected", automatic_send)

    raw_customer_payload = json.loads(dual_loop.dump_json(report))
    raw_customer_payload["privacy"]["raw_customer_payload_included"] = True
    expect_rejected("raw_customer_payload_rejected", raw_customer_payload)

    missing_blocked_case = json.loads(dual_loop.dump_json(report))
    missing_blocked_case["case_reports"] = [
        case
        for case in missing_blocked_case["case_reports"]
        if case["case_id"] != "blocked-product-loop-run"
    ]
    expect_rejected("missing_blocked_case_rejected", missing_blocked_case)

    return failures


def build_report() -> dict[str, Any]:
    core_report = harness.build_report()
    verify_cli(core_report)
    report = json.loads(dual_loop.dump_json(core_report))
    report["schema_files"] = [verify_schema()]
    report["negative_checks"] = negative_checks(report)
    case_ids = {case["case_id"] for case in report["case_reports"]}
    if case_ids != EXPECTED_CASE_IDS:
        raise RuntimeError("End-to-End Trust Chain case coverage drifted")
    dual_loop.assert_metadata_only(report, label=harness.REPORT_SCHEMA_VERSION)
    return harness.validate_report(report)


def render_markdown(report: Mapping[str, Any]) -> str:
    return harness.render_markdown(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    report = build_report()
    serialized = dual_loop.dump_json(report)
    markdown = render_markdown(report)
    html = dual_loop.render_html_report("End-to-End Trust Chain Harness", report)

    if args.write:
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(serialized, encoding="utf-8")
        harness.REPORT.parent.mkdir(parents=True, exist_ok=True)
        harness.REPORT.write_text(serialized, encoding="utf-8")
        harness.MARKDOWN_REPORT.write_text(markdown, encoding="utf-8")
        harness.HTML_REPORT.write_text(html, encoding="utf-8")

    if args.check:
        if not FIXTURE.is_file() or FIXTURE.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "End-to-End Trust Chain fixture is missing or out of date. "
                "Run: python3 scripts/verify_end_to_end_trust_chain_harness.py --write"
            )
        if not harness.REPORT.is_file() or harness.REPORT.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "End-to-End Trust Chain report is missing or out of date. "
                "Run: python3 scripts/verify_end_to_end_trust_chain_harness.py --write"
            )
        if not harness.MARKDOWN_REPORT.is_file() or harness.MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
            raise SystemExit(
                "End-to-End Trust Chain markdown report is missing or out of date. "
                "Run: python3 scripts/verify_end_to_end_trust_chain_harness.py --write"
            )
        if not harness.HTML_REPORT.is_file() or harness.HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "End-to-End Trust Chain HTML report is missing or out of date. "
                "Run: python3 scripts/verify_end_to_end_trust_chain_harness.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
