#!/usr/bin/env python3
"""Verify CBB self-intake evidence for PR #285."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import cbb_protocol, cbb_receipt_chain, dual_loop  # noqa: E402


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-self-intake.json"
FIXTURE_ROOT = ROOT / "fixtures" / "cbb-self-intake"
POSITIVE_DIR = FIXTURE_ROOT / "pr-285"
NEGATIVE_DIR = FIXTURE_ROOT / "negative"

PROTOCOL_FILENAMES = (
    "claim-boundary.json",
    "trust-root.json",
    "reviewer-reconstruction-receipt.json",
    "risk-owner-scope.json",
    "delivery-decision-receipt.json",
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def _protocol_receipts(artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {filename: artifacts[filename] for filename in PROTOCOL_FILENAMES}


def _capture_rejection(label: str, func: Any, expected: str) -> tuple[str, str]:
    try:
        func()
    except Exception as exc:  # noqa: BLE001 - verifier records deterministic rejection reason.
        message = str(exc)
        if expected not in message:
            raise RuntimeError(f"{label} expected {expected!r}, got {message!r}") from exc
        return label, message
    raise RuntimeError(f"Expected CBB self-intake negative check to fail: {label}")


def build_negative_fixtures(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    cases: dict[str, dict[str, dict[str, Any]]] = {}

    receipt_hash = cbb_receipt_chain.tamper_receipt_hash_mismatch(artifacts)
    cases["receipt-hash-mismatch"] = {
        "receipt-chain.json": receipt_hash,
        "expected-error.json": {
            "schema_version": "cbb-negative-fixture-v1",
            "case_id": "receipt-hash-mismatch",
            "expected_error": "receipt hash mismatch",
        },
    }

    missing_reviewer = deepcopy(artifacts["self-intake-receipt.json"])
    missing_reviewer["reviewer_reconstruction_summary"]["present"] = False
    missing_reviewer["reviewer_reconstruction_summary"]["receipt_ref"] = None
    missing_reviewer["checks"]["reviewer_reconstruction_present"] = False
    cases["missing-reviewer-reconstruction"] = {
        "self-intake-receipt.json": missing_reviewer,
        "expected-error.json": {
            "schema_version": "cbb-negative-fixture-v1",
            "case_id": "missing-reviewer-reconstruction",
            "expected_error": "missing reviewer reconstruction",
        },
    }

    stale_commit = deepcopy(artifacts["self-intake-receipt.json"])
    stale_commit["source"]["merge_commit"] = "70697083d3c576d758fbd9639df3fe3b582ec72a"
    stale_commit["checks"]["source_commit_matches"] = False
    cases["stale-source-commit"] = {
        "self-intake-receipt.json": stale_commit,
        "expected-error.json": {
            "schema_version": "cbb-negative-fixture-v1",
            "case_id": "stale-source-commit",
            "expected_error": "stale source commit",
        },
    }

    scope_expansion = deepcopy(artifacts["self-intake-receipt.json"])
    scope_expansion["checks"]["no_scope_expansion"] = False
    cases["scope-expansion"] = {
        "self-intake-receipt.json": scope_expansion,
        "expected-error.json": {
            "schema_version": "cbb-negative-fixture-v1",
            "case_id": "scope-expansion",
            "expected_error": "scope expansion",
        },
    }

    ci_missing = deepcopy(artifacts["self-intake-receipt.json"])
    ci_missing["ci_checks"] = [
        check for check in ci_missing["ci_checks"] if check["name"] != "compose-smoke"
    ]
    ci_missing["checks"]["ci_required_checks_passed"] = False
    cases["ci-evidence-missing"] = {
        "self-intake-receipt.json": ci_missing,
        "expected-error.json": {
            "schema_version": "cbb-negative-fixture-v1",
            "case_id": "ci-evidence-missing",
            "expected_error": "CI evidence missing",
        },
    }

    ai_review_only = deepcopy(artifacts["self-intake-receipt.json"])
    ai_review_only["checks"]["ai_review_only_rejected"] = False
    cases["ai-review-only-evidence-rejected"] = {
        "self-intake-receipt.json": ai_review_only,
        "expected-error.json": {
            "schema_version": "cbb-negative-fixture-v1",
            "case_id": "ai-review-only-evidence-rejected",
            "expected_error": "AI-review-only evidence rejected",
        },
    }

    return cases


def _exercise_negative_checks(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    negatives = build_negative_fixtures(artifacts)
    receipts = _protocol_receipts(artifacts)
    chain = artifacts["receipt-chain.json"]
    checks = dict(
        [
            _capture_rejection(
                "receipt_hash_mismatch_rejected",
                lambda: cbb_receipt_chain.validate_receipt_chain(
                    negatives["receipt-hash-mismatch"]["receipt-chain.json"],
                    receipts,
                ),
                "receipt hash mismatch",
            ),
            _capture_rejection(
                "missing_reviewer_reconstruction_rejected",
                lambda: cbb_receipt_chain.validate_self_intake_receipt(
                    negatives["missing-reviewer-reconstruction"]["self-intake-receipt.json"],
                    receipt_chain=chain,
                ),
                "missing reviewer reconstruction",
            ),
            _capture_rejection(
                "stale_source_commit_rejected",
                lambda: cbb_receipt_chain.validate_self_intake_receipt(
                    negatives["stale-source-commit"]["self-intake-receipt.json"],
                    receipt_chain=chain,
                ),
                "stale source commit",
            ),
            _capture_rejection(
                "scope_expansion_rejected",
                lambda: cbb_receipt_chain.validate_self_intake_receipt(
                    negatives["scope-expansion"]["self-intake-receipt.json"],
                    receipt_chain=chain,
                ),
                "scope expansion",
            ),
            _capture_rejection(
                "ci_evidence_missing_rejected",
                lambda: cbb_receipt_chain.validate_self_intake_receipt(
                    negatives["ci-evidence-missing"]["self-intake-receipt.json"],
                    receipt_chain=chain,
                ),
                "CI evidence missing",
            ),
            _capture_rejection(
                "ai_review_only_evidence_rejected",
                lambda: cbb_receipt_chain.validate_self_intake_receipt(
                    negatives["ai-review-only-evidence-rejected"]["self-intake-receipt.json"],
                    receipt_chain=chain,
                ),
                "AI-review-only evidence rejected",
            ),
        ]
    )
    return checks


def _verify_self_intake_cli(artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-cbb-self-intake-") as tmp:
        root = Path(tmp)
        cbb_receipt_chain.write_artifact_set(root / "input", artifacts)
        output = root / "self-intake-receipt.json"
        pack_output = root / "delivery-evidence-pack.json"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "cbb_self_intake.py"),
            "build",
            "--claim-boundary",
            str(root / "input" / "claim-boundary.json"),
            "--trust-root",
            str(root / "input" / "trust-root.json"),
            "--reviewer-reconstruction",
            str(root / "input" / "reviewer-reconstruction-receipt.json"),
            "--risk-owner-scope",
            str(root / "input" / "risk-owner-scope.json"),
            "--delivery-decision",
            str(root / "input" / "delivery-decision-receipt.json"),
            "--receipt-chain",
            str(root / "input" / "receipt-chain.json"),
            "--output",
            str(output),
            "--pack-output",
            str(pack_output),
            "--html-output",
            str(root / "self-intake-receipt.html"),
        ]
        proc = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
        stdout = json.loads(proc.stdout)
        dual_loop.assert_metadata_only(stdout, label="cbb-self-intake-build-cli")
        if _load_json(output) != artifacts["self-intake-receipt.json"]:
            raise RuntimeError("cbb_self_intake.py build output drifted")
        if _load_json(pack_output) != artifacts["delivery-evidence-pack.json"]:
            raise RuntimeError("cbb_self_intake.py pack output drifted")

        demo_dir = root / "demo"
        demo_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "cbb_self_intake.py"),
                "demo",
                "--output-dir",
                str(demo_dir),
                "--html",
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        demo_stdout = json.loads(demo_proc.stdout)
        dual_loop.assert_metadata_only(demo_stdout, label="cbb-self-intake-demo-cli")
        if _load_json(demo_dir / "self-intake-receipt.json") != artifacts["self-intake-receipt.json"]:
            raise RuntimeError("cbb_self_intake.py demo self-intake output drifted")


def build_report() -> dict[str, Any]:
    artifacts = cbb_receipt_chain.build_pr_285_self_intake_artifacts()
    receipts = _protocol_receipts(artifacts)
    chain = cbb_receipt_chain.validate_receipt_chain(artifacts["receipt-chain.json"], receipts)
    self_intake = cbb_receipt_chain.validate_self_intake_receipt(
        artifacts["self-intake-receipt.json"],
        receipt_chain=chain,
    )
    pack = cbb_receipt_chain.validate_delivery_evidence_pack(
        artifacts["delivery-evidence-pack.json"],
        receipt_chain=chain,
        self_intake=self_intake,
    )
    _verify_self_intake_cli(artifacts)
    negative_checks = _exercise_negative_checks(artifacts)
    report = {
        "schema_version": cbb_receipt_chain.CBB_SELF_INTAKE_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "source": cbb_receipt_chain.default_pr_285_source(),
        "self_intake": {
            "self_intake_id": self_intake["self_intake_id"],
            "status": self_intake["status"],
            "decision": self_intake["decision"],
            "chain_digest": self_intake["receipt_chain"]["chain_digest"],
            "required_ci_checks": list(cbb_receipt_chain.REQUIRED_CI_CHECKS),
        },
        "delivery_evidence_pack": {
            "pack_id": pack["pack_id"],
            "status": pack["status"],
            "pack_digest": pack["pack_digest"],
            "included_artifact_count": len(pack["included_artifacts"]),
        },
        "negative_checks": negative_checks,
        "trust_rules": {
            "receipt_hash_mismatch_blocks": True,
            "reviewer_reconstruction_required": True,
            "source_commit_must_match": True,
            "scope_expansion_blocks": True,
            "required_ci_evidence_must_pass": True,
            "ai_review_only_blocks": True,
            "metadata_only": True,
        },
        "privacy": {
            **cbb_protocol.CBB_PRIVACY_FLAGS,
            "metadata_only_fixtures": True,
            "raw_diff_included": False,
            "raw_customer_payload_included": False,
            "real_customer_data_included": False,
        },
        "isolation": dict(dual_loop.ISOLATION_BOUNDARY),
        "claim_boundary": {
            "current_claim": (
                "PR 285 has CBB self-intake evidence that can be replayed from "
                "metadata-only receipts and GitHub check metadata."
            ),
            "not_claimed": [
                "production customer trust",
                "legal certification",
                "security certification",
                "general model correctness",
                "full release validation",
            ],
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cbb_self_intake.py --check",
            "fixture_dir": "fixtures/cbb-self-intake",
        },
    }
    dual_loop.assert_metadata_only(report, label="cbb-self-intake-report")
    return report


def _write_fixtures(artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    cbb_receipt_chain.write_artifact_set(POSITIVE_DIR, artifacts)
    for case_id, files in build_negative_fixtures(artifacts).items():
        cbb_receipt_chain.write_artifact_set(NEGATIVE_DIR / case_id, files)


def _check_fixture_dir(expected: Mapping[str, Mapping[str, Any]], root: Path) -> None:
    for filename, payload in expected.items():
        path = root / filename
        if not path.is_file():
            raise SystemExit(f"Missing CBB self-intake fixture: {path}")
        if _load_json(path) != payload:
            raise SystemExit(
                f"CBB self-intake fixture is out of date: {path}. "
                "Run: python3 scripts/verify_cbb_self_intake.py --write"
            )


def check_fixtures(artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    _check_fixture_dir(artifacts, POSITIVE_DIR)
    for case_id, files in build_negative_fixtures(artifacts).items():
        _check_fixture_dir(files, NEGATIVE_DIR / case_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    artifacts = cbb_receipt_chain.build_pr_285_self_intake_artifacts()
    report = build_report()
    serialized = cbb_protocol.dump_json(report)
    output = Path(args.output)
    if args.write:
        _write_fixtures(artifacts)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        check_fixtures(artifacts)
        if not output.is_file():
            raise SystemExit(f"CBB self-intake report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "CBB self-intake report is out of date. "
                "Run: python3 scripts/verify_cbb_self_intake.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
