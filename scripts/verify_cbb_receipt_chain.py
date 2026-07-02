#!/usr/bin/env python3
"""Verify CBB receipt-chain contracts and tamper evidence."""

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


DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-receipt-chain.json"
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

SCHEMA_FILES = [
    (
        ROOT / "platform" / "schemas" / "cbb" / "cbb-receipt-chain-v1.schema.json",
        cbb_receipt_chain.CBB_RECEIPT_CHAIN_SCHEMA_VERSION,
    ),
    (
        ROOT / "platform" / "schemas" / "cbb" / "cbb-self-intake-receipt-v1.schema.json",
        cbb_receipt_chain.CBB_SELF_INTAKE_RECEIPT_SCHEMA_VERSION,
    ),
    (
        ROOT / "platform" / "schemas" / "cbb" / "cbb-delivery-evidence-pack-v1.schema.json",
        cbb_receipt_chain.CBB_DELIVERY_EVIDENCE_PACK_SCHEMA_VERSION,
    ),
]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def _protocol_receipts(artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {filename: artifacts[filename] for filename in PROTOCOL_FILENAMES}


def _schema_report() -> list[dict[str, str]]:
    reports: list[dict[str, str]] = []
    for path, schema_version in SCHEMA_FILES:
        if not path.is_file():
            raise RuntimeError(f"CBB receipt-chain schema missing: {path}")
        payload = _load_json(path)
        if payload.get("$id") != schema_version:
            raise RuntimeError(f"CBB receipt-chain schema id drifted for {path}")
        if payload.get("properties", {}).get("schema_version", {}).get("const") != schema_version:
            raise RuntimeError(f"CBB receipt-chain schema_version const drifted for {path}")
        reports.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "schema_version": schema_version,
                "sha256": dual_loop.sha256_text(path.read_text(encoding="utf-8")),
            }
        )
    return reports


def _capture_rejection(label: str, func: Any, expected: str) -> tuple[str, str]:
    try:
        func()
    except Exception as exc:  # noqa: BLE001 - verifier records deterministic rejection reason.
        message = str(exc)
        if expected not in message:
            raise RuntimeError(f"{label} expected {expected!r}, got {message!r}") from exc
        return label, message
    raise RuntimeError(f"Expected CBB receipt-chain negative check to fail: {label}")


def build_negative_fixtures(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    receipts = _protocol_receipts(artifacts)
    hash_mismatch = cbb_receipt_chain.tamper_receipt_hash_mismatch(artifacts)

    stale_commit = deepcopy(artifacts["receipt-chain.json"])
    stale_commit["source"]["merge_commit"] = "70697083d3c576d758fbd9639df3fe3b582ec72a"
    stale_commit["chain_digest"] = cbb_receipt_chain.compute_receipt_chain_digest(stale_commit)

    return {
        "receipt-hash-mismatch": {
            "receipt-chain.json": hash_mismatch,
            "expected-error.json": {
                "schema_version": "cbb-negative-fixture-v1",
                "case_id": "receipt-hash-mismatch",
                "expected_error": "receipt hash mismatch",
            },
        },
        "receipt-chain-stale-source-commit": {
            "receipt-chain.json": stale_commit,
            "expected-error.json": {
                "schema_version": "cbb-negative-fixture-v1",
                "case_id": "receipt-chain-stale-source-commit",
                "expected_error": "receipt chain source commit is stale",
            },
        },
        "_receipts": {filename: dict(payload) for filename, payload in receipts.items()},
    }


def _exercise_negative_checks(
    artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    negatives = build_negative_fixtures(artifacts)
    receipts = negatives["_receipts"]
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
                "stale_source_commit_rejected",
                lambda: cbb_receipt_chain.validate_receipt_chain(
                    negatives["receipt-chain-stale-source-commit"]["receipt-chain.json"],
                    receipts,
                ),
                "receipt chain source commit is stale",
            ),
        ]
    )
    return checks


def _verify_receipt_chain_cli(artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-cbb-chain-") as tmp:
        root = Path(tmp)
        cbb_receipt_chain.write_artifact_set(root / "input", artifacts)
        build_output = root / "built-receipt-chain.json"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "cbb_receipt_chain.py"),
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
            "--output",
            str(build_output),
        ]
        proc = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
        stdout = json.loads(proc.stdout)
        dual_loop.assert_metadata_only(stdout, label="cbb-receipt-chain-build-cli")
        if _load_json(build_output) != artifacts["receipt-chain.json"]:
            raise RuntimeError("cbb_receipt_chain.py build output drifted")

        demo_dir = root / "demo"
        demo_proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "cbb_receipt_chain.py"),
                "demo",
                "--output-dir",
                str(demo_dir),
            ],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        demo_stdout = json.loads(demo_proc.stdout)
        dual_loop.assert_metadata_only(demo_stdout, label="cbb-receipt-chain-demo-cli")
        if _load_json(demo_dir / "receipt-chain.json") != artifacts["receipt-chain.json"]:
            raise RuntimeError("cbb_receipt_chain.py demo output drifted")


def build_report() -> dict[str, Any]:
    artifacts = cbb_receipt_chain.build_pr_285_self_intake_artifacts()
    receipts = _protocol_receipts(artifacts)
    chain = cbb_receipt_chain.validate_receipt_chain(artifacts["receipt-chain.json"], receipts)
    cbb_receipt_chain.validate_delivery_evidence_pack(
        artifacts["delivery-evidence-pack.json"],
        receipt_chain=chain,
        self_intake=artifacts["self-intake-receipt.json"],
    )
    _verify_receipt_chain_cli(artifacts)
    negative_checks = _exercise_negative_checks(artifacts)
    report = {
        "schema_version": cbb_receipt_chain.CBB_RECEIPT_CHAIN_REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "source": cbb_receipt_chain.default_pr_285_source(),
        "artifact_contracts": {
            "receipt_chain": cbb_receipt_chain.CBB_RECEIPT_CHAIN_SCHEMA_VERSION,
            "self_intake": cbb_receipt_chain.CBB_SELF_INTAKE_RECEIPT_SCHEMA_VERSION,
            "delivery_evidence_pack": (
                cbb_receipt_chain.CBB_DELIVERY_EVIDENCE_PACK_SCHEMA_VERSION
            ),
        },
        "schema_files": _schema_report(),
        "receipt_chain": {
            "chain_id": chain["chain_id"],
            "chain_digest": chain["chain_digest"],
            "receipt_count": len(chain["receipts"]),
            "hash_algorithm": chain["hash_algorithm"],
            "canonicalization": chain["canonicalization"],
        },
        "negative_checks": negative_checks,
        "trust_rules": {
            "receipt_hashes_bound": True,
            "source_commit_bound": True,
            "chain_digest_bound": True,
            "metadata_only": True,
            "model_calls_forbidden": True,
            "production_mutation_blocked": True,
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
                "PR 285 CBB receipt chain is tamper-evident for metadata-only "
                "reference implementation evidence."
            ),
            "not_claimed": [
                "production customer trust",
                "legal certification",
                "security certification",
                "general model correctness",
            ],
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cbb_receipt_chain.py --check",
            "fixture_dir": "fixtures/cbb-self-intake",
        },
    }
    dual_loop.assert_metadata_only(report, label="cbb-receipt-chain-report")
    return report


def _write_fixtures(artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    cbb_receipt_chain.write_artifact_set(POSITIVE_DIR, artifacts)
    negatives = build_negative_fixtures(artifacts)
    for case_id, files in negatives.items():
        if case_id == "_receipts":
            continue
        cbb_receipt_chain.write_artifact_set(NEGATIVE_DIR / case_id, files)


def _check_fixture_dir(expected: Mapping[str, Mapping[str, Any]], root: Path) -> None:
    for filename, payload in expected.items():
        path = root / filename
        if not path.is_file():
            raise SystemExit(f"Missing CBB receipt-chain fixture: {path}")
        if _load_json(path) != payload:
            raise SystemExit(
                f"CBB receipt-chain fixture is out of date: {path}. "
                "Run: python3 scripts/verify_cbb_receipt_chain.py --write"
            )


def check_fixtures(artifacts: Mapping[str, Mapping[str, Any]]) -> None:
    _check_fixture_dir(artifacts, POSITIVE_DIR)
    negatives = build_negative_fixtures(artifacts)
    for case_id, files in negatives.items():
        if case_id == "_receipts":
            continue
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
            raise SystemExit(f"CBB receipt-chain report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "CBB receipt-chain report is out of date. "
                "Run: python3 scripts/verify_cbb_receipt_chain.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
