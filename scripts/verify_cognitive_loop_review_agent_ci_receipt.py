#!/usr/bin/env python3
"""Verify Cognitive Loop Review Agent CI/PR receipt assets."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
REPORT_FIXTURE_DIR = ROOT / "fixtures" / "review-agent"
RECEIPT_FIXTURE_DIR = ROOT / "fixtures" / "review-agent-receipts"
RECEIPT_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_receipt.py"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review-agent-ci-receipt.json"

SCHEMA_VERSION = "cognitive-loop-review-agent-ci-receipt-verification-v1"
RECEIPT_SCHEMA_VERSION = "cognitive-loop-review-agent-ci-receipt-v1"
REPORT_FIXTURES = ("approved.json", "needs-review.json", "needs-fix.json")
BAD_RECEIPTS = ("raw-diff-leak.json",)
FIXED_GENERATED_AT = "2026-06-18T00:00:00+00:00"


class ReviewAgentReceiptVerificationError(RuntimeError):
    """Readable Review Agent CI receipt verification failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewAgentReceiptVerificationError(f"Cannot read JSON {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewAgentReceiptVerificationError(f"JSON object expected: {path.relative_to(ROOT)}")
    return value


def load_receipt_cli() -> Any:
    spec = importlib.util.spec_from_file_location(
        "study_anything_review_agent_receipt",
        RECEIPT_CLI_PATH,
    )
    if spec is None or spec.loader is None:
        raise ReviewAgentReceiptVerificationError(f"Cannot load receipt CLI: {RECEIPT_CLI_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentReceiptVerificationError(message)


def report_sha(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def build_receipt_for_fixture(module: Any, fixture_name: str) -> dict[str, Any]:
    report_path = REPORT_FIXTURE_DIR / fixture_name
    report = read_json(report_path)
    fixture_id = fixture_name.removesuffix(".json")
    receipt = module.build_receipt_payload(
        report,
        report_sha256=report_sha(report_path),
        source_report_name=fixture_name,
        provider_id=f"fixture-{fixture_id}-review-agent",
        provider_label=f"Fixture {fixture_id} Review Agent",
        execution_surface="ci",
        pr_ref=f"PR-fixture-{fixture_id}",
        commit_sha=f"sha-fixture-{fixture_id}",
        base_ref="main",
        head_ref=f"codex/fixture-{fixture_id}",
        generated_at=FIXED_GENERATED_AT,
    )
    summary = module.validate_receipt_payload(receipt)
    require(receipt["schema_version"] == RECEIPT_SCHEMA_VERSION, f"{fixture_name} receipt schema drifted.")
    serialized = dump_json(receipt)
    validated_report = receipt.get("validated_report", {})
    require(isinstance(validated_report, Mapping), f"{fixture_name} validated_report must be an object.")
    for forbidden_key in ("summary", "findings", "evidence", "recommendation"):
        require(forbidden_key not in validated_report, f"{fixture_name} receipt leaked report body field: {forbidden_key}")
    for forbidden_text in ("diff --git", "@@ ", "subprocess.run(user_command"):
        require(forbidden_text not in serialized, f"{fixture_name} receipt leaked raw report text: {forbidden_text}")
    return {
        "receipt": receipt,
        "summary": summary,
    }


def validate_bad_receipt(module: Any, fixture_name: str) -> str:
    path = RECEIPT_FIXTURE_DIR / fixture_name
    payload = read_json(path)
    try:
        module.validate_receipt_payload(payload)
    except Exception as exc:
        return str(exc)
    raise ReviewAgentReceiptVerificationError(f"Bad receipt unexpectedly passed: {path.relative_to(ROOT)}")


def validate_docs() -> dict[str, str]:
    docs = {
        "docs/cognitive-loop-code-review.md": [
            "cognitive_loop_review_agent_receipt.py build",
            "verify_cognitive_loop_review_agent_ci_receipt.py --check",
        ],
        "docs/eval-frameworks.md": [
            "cognitive-loop-review-agent-ci-receipt-v1",
            "verify_cognitive_loop_review_agent_ci_receipt.py --check",
        ],
        ".cognitive-loop/evals.yaml": [
            "cognitive-loop.review-agent-ci-receipt",
            "python3 scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check",
        ],
        "scripts/release_check.sh": [
            "scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check",
        ],
        "platform/packs/kimi/README.md": [
            "cognitive_loop_review_agent_receipt.py build",
            "verify_cognitive_loop_review_agent_ci_receipt.py --check",
        ],
        "platform/packs/codex/README.md": [
            "cognitive_loop_review_agent_receipt.py build",
            "verify_cognitive_loop_review_agent_ci_receipt.py --check",
        ],
        "platform/packs/workbuddy/README.md": [
            "cognitive_loop_review_agent_receipt.py build",
            "verify_cognitive_loop_review_agent_ci_receipt.py --check",
        ],
    }
    checked: dict[str, str] = {}
    for relative, needles in docs.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        require(not missing, f"{relative} missing Review Agent CI receipt references: {missing}")
        checked[relative] = "pass"
    return checked


def build_report() -> dict[str, Any]:
    module = load_receipt_cli()
    built = {fixture: build_receipt_for_fixture(module, fixture) for fixture in REPORT_FIXTURES}
    summaries = {fixture: value["summary"] for fixture, value in built.items()}
    decisions = {summary["decision"] for summary in summaries.values()}
    require(decisions == {"approved", "needs-review", "needs-fix"}, f"Receipt decision coverage drifted: {sorted(decisions)}")
    negative = {fixture: validate_bad_receipt(module, fixture) for fixture in BAD_RECEIPTS}
    docs = validate_docs()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
        "cli": "scripts/cognitive_loop_review_agent_receipt.py",
        "receipt_count": len(summaries),
        "receipts": summaries,
        "negative_receipts": negative,
        "docs": docs,
        "quality_gates": {
            "decision_path_coverage": sorted(decisions),
            "report_hash_required": "pass",
            "metadata_only_receipts": "pass",
            "privacy_leak_rejection": "pass",
        },
        "privacy": {
            "raw_diff_included": False,
            "file_bodies_included": False,
            "finding_evidence_included": False,
            "report_summary_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "hidden_chain_of_thought_included": False,
            "safe_to_attach_to_pr": True,
        },
        "acceptance": {
            "build_command": (
                "python3 scripts/cognitive_loop_review_agent_receipt.py build "
                "--report REVIEW_AGENT_REPORT.json --provider-id PROVIDER --pr-ref PR --commit-sha SHA"
            ),
            "validate_command": "python3 scripts/cognitive_loop_review_agent_receipt.py validate --receipt RECEIPT.json",
            "minimum_command": "python3 scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check",
            "generated_report": "platform/generated/study-anything-cognitive-loop-review-agent-ci-receipt.json",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
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
            raise SystemExit(f"Cognitive Loop Review Agent CI receipt report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Review Agent CI receipt report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_review_agent_ci_receipt.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentReceiptVerificationError as exc:
        raise SystemExit(f"error: {exc}") from exc
