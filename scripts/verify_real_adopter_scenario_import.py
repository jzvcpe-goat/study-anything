#!/usr/bin/env python3
"""Verify the metadata-only real-adopter scenario import harness."""

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
import real_adopter_scenario_import as importer  # noqa: E402


FIXTURE_ROOT = ROOT / "fixtures" / "real-adopter-scenario-import" / "pass"
REPORT_FIXTURE = FIXTURE_ROOT / "real-adopter-scenario-import-report.json"
SCHEMA_FILE = ROOT / "platform" / "schemas" / "cbb" / "real-adopter-scenario-import-v1.schema.json"

CHAIN_FILES = {
    "summary": "real-adopter-issue-summary.json",
    "external_feedback_receipt": "external-feedback-receipt.json",
    "external_feedback_backlog_bridge": "external-feedback-backlog-bridge.json",
    "product_loop_backlog_item": "product-loop-backlog-item.json",
    "product_owner_prioritization_receipt": "product-owner-prioritization-receipt.json",
    "product_spec_eval_candidate": "product-spec-eval-candidate.json",
    "product_spec_eval_authoring_receipt": "product-spec-eval-authoring-receipt.json",
    "product_spec_eval_brief": "product-spec-eval-brief.json",
    "product_loop_brief_intake_receipt": "product-loop-brief-intake-receipt.json",
    "product_loop_scenario": "product-loop-scenario.json",
    "product_loop_run": "product-loop-run.json",
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def verify_schema() -> dict[str, str]:
    schema = load_json(SCHEMA_FILE)
    if schema.get("$id") != importer.REPORT_SCHEMA_VERSION:
        raise RuntimeError("Real-Adopter Scenario Import schema id drifted")
    if (
        schema.get("properties", {})
        .get("schema_version", {})
        .get("const")
        != importer.REPORT_SCHEMA_VERSION
    ):
        raise RuntimeError("Real-Adopter Scenario Import schema_version const drifted")
    return {
        "path": SCHEMA_FILE.relative_to(ROOT).as_posix(),
        "schema_version": importer.REPORT_SCHEMA_VERSION,
        "sha256": dual_loop.sha256_text(SCHEMA_FILE.read_text(encoding="utf-8")),
    }


def verify_cli(expected_report: Mapping[str, Any]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-real-adopter-import-") as tmp:
        tmpdir = Path(tmp)
        summary = tmpdir / "summary.json"
        output_dir = tmpdir / "out"
        report = tmpdir / "report.json"
        markdown = tmpdir / "report.md"
        html = tmpdir / "report.html"
        summary.write_text(importer.dump_json(importer.default_summary()), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "real_adopter_scenario_import.py"),
                "--summary",
                str(summary),
                "--output-dir",
                str(output_dir),
                "--report",
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
        dual_loop.assert_metadata_only(stdout, label="real-adopter-import-cli")
        if stdout.get("schema_version") != importer.CLI_SCHEMA_VERSION:
            raise RuntimeError("Real-Adopter Scenario Import CLI schema drifted")
        actual_report = load_json(report)
        if actual_report != expected_report:
            raise RuntimeError("Real-Adopter Scenario Import CLI report drifted")
        for filename in CHAIN_FILES.values():
            if not (output_dir / filename).is_file():
                raise RuntimeError(f"Real-Adopter Scenario Import CLI missing artifact: {filename}")
        if not markdown.is_file() or not html.is_file():
            raise RuntimeError("Real-Adopter Scenario Import CLI missing markdown/html outputs")
        dual_loop.assert_metadata_only(html.read_text(encoding="utf-8"), label="real-adopter-import-html")


def verify_chain_continuity(chain: Mapping[str, Mapping[str, Any]], report: Mapping[str, Any]) -> list[dict[str, Any]]:
    expected = {
        name: importer.artifact_hash(payload)
        for name, payload in chain.items()
    }
    pass_case = next(case for case in report["case_reports"] if case["case_id"] == "pass")
    observed = {
        ref["name"]: ref["artifact_hash"]
        for ref in pass_case["artifact_refs"]
    }
    if expected != observed:
        raise RuntimeError("Real-Adopter Scenario Import artifact refs drifted")
    checks = [
        {
            "check_id": "summary_to_external_feedback",
            "status": "pass"
            if chain["external_feedback_receipt"]["feedback_ref"]["feedback_hash"]
            == chain["summary"]["issue_ref"]["issue_ref_hash"]
            else "fail",
        },
        {
            "check_id": "backlog_to_product_owner",
            "status": "pass"
            if chain["product_owner_prioritization_receipt"]["source_backlog_item_hash"]
            == importer.artifact_hash(chain["product_loop_backlog_item"])
            else "fail",
        },
        {
            "check_id": "candidate_to_spec_eval_authoring",
            "status": "pass"
            if chain["product_spec_eval_authoring_receipt"]["source_candidate_hash"]
            == importer.artifact_hash(chain["product_spec_eval_candidate"])
            else "fail",
        },
        {
            "check_id": "brief_to_product_loop_intake",
            "status": "pass"
            if chain["product_loop_brief_intake_receipt"]["source_brief_hash"]
            == importer.artifact_hash(chain["product_spec_eval_brief"])
            else "fail",
        },
    ]
    failed = [check["check_id"] for check in checks if check["status"] != "pass"]
    if failed:
        raise RuntimeError(f"Real-Adopter Scenario Import continuity failed: {failed}")
    return checks


def negative_checks(report: Mapping[str, Any]) -> dict[str, str]:
    failures: dict[str, str] = {}

    def expect_rejected(case_id: str, payload: Mapping[str, Any]) -> None:
        try:
            importer.validate_report(payload)
        except Exception as exc:  # noqa: BLE001
            failures[case_id] = importer.diagnostic_code(exc)
            return
        raise RuntimeError(f"Real-Adopter Scenario Import negative case passed: {case_id}")

    raw_issue = json.loads(dual_loop.dump_json(report))
    raw_issue["case_reports"][0]["raw_issue_text"] = "raw private source text"
    expect_rejected("raw_issue_text_rejected", raw_issue)

    failed_rule = json.loads(dual_loop.dump_json(report))
    failed_rule["chain_rules"]["product_owner_reconstruction_required"] = False
    expect_rejected("missing_product_owner_reconstruction_rule_rejected", failed_rule)

    production = json.loads(dual_loop.dump_json(report))
    production["runtime"]["production_mutation_performed"] = True
    expect_rejected("production_mutation_rejected", production)

    missing_blocked_case = json.loads(dual_loop.dump_json(report))
    missing_blocked_case["case_reports"] = [
        case
        for case in missing_blocked_case["case_reports"]
        if case["case_id"] != "blocked-ai-review-only"
    ]
    expect_rejected("missing_ai_review_only_case_rejected", missing_blocked_case)

    return failures


def build_report() -> dict[str, Any]:
    summary = importer.default_summary()
    chain = importer.build_chain(summary)
    report = importer.build_report(summary)
    verify_cli(report)
    enriched = json.loads(dual_loop.dump_json(report))
    enriched["schema_files"] = [verify_schema()]
    enriched["continuity_checks"] = verify_chain_continuity(chain, report)
    enriched["negative_checks"] = negative_checks(enriched)
    dual_loop.assert_metadata_only(enriched, label=importer.REPORT_SCHEMA_VERSION)
    return importer.validate_report(enriched)


def expected_fixture_payloads(report: Mapping[str, Any]) -> dict[str, str]:
    chain = importer.build_chain(importer.default_summary())
    payloads = {
        CHAIN_FILES[name]: importer.dump_json(payload)
        for name, payload in chain.items()
    }
    payloads["real-adopter-scenario-import-report.json"] = importer.dump_json(report)
    return payloads


def write_outputs(report: Mapping[str, Any]) -> None:
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    for filename, serialized in expected_fixture_payloads(report).items():
        (FIXTURE_ROOT / filename).write_text(serialized, encoding="utf-8")
    importer.REPORT.parent.mkdir(parents=True, exist_ok=True)
    serialized = importer.dump_json(report)
    importer.REPORT.write_text(serialized, encoding="utf-8")
    importer.MARKDOWN_REPORT.write_text(importer.render_markdown(report), encoding="utf-8")
    importer.HTML_REPORT.write_text(
        dual_loop.render_html_report("Real-Adopter Scenario Import", report),
        encoding="utf-8",
    )


def check_outputs(report: Mapping[str, Any]) -> None:
    for filename, serialized in expected_fixture_payloads(report).items():
        path = FIXTURE_ROOT / filename
        if not path.is_file() or path.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                f"Real-Adopter Scenario Import fixture is stale: {path}. "
                "Run: python3 scripts/verify_real_adopter_scenario_import.py --write"
            )
    serialized = importer.dump_json(report)
    if not importer.REPORT.is_file() or importer.REPORT.read_text(encoding="utf-8") != serialized:
        raise SystemExit(
            "Real-Adopter Scenario Import report is stale. "
            "Run: python3 scripts/verify_real_adopter_scenario_import.py --write"
        )
    markdown = importer.render_markdown(report)
    if not importer.MARKDOWN_REPORT.is_file() or importer.MARKDOWN_REPORT.read_text(encoding="utf-8") != markdown:
        raise SystemExit(
            "Real-Adopter Scenario Import markdown report is stale. "
            "Run: python3 scripts/verify_real_adopter_scenario_import.py --write"
        )
    html = dual_loop.render_html_report("Real-Adopter Scenario Import", report)
    if not importer.HTML_REPORT.is_file() or importer.HTML_REPORT.read_text(encoding="utf-8") != html:
        raise SystemExit(
            "Real-Adopter Scenario Import HTML report is stale. "
            "Run: python3 scripts/verify_real_adopter_scenario_import.py --write"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    report = build_report()
    if args.write:
        write_outputs(report)
    if args.check:
        check_outputs(report)
    print(importer.dump_json(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
