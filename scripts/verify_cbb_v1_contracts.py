#!/usr/bin/env python3
"""Verify canonical CBB Protocol v1 contracts, schemas, and negative fixtures."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.protocol.canonical import (  # noqa: E402
    canonical_json_bytes,
    canonical_sha256,
    model_payload,
    schema_outputs,
    validate_payload,
)
from study_anything.cbb.protocol.fixtures import (  # noqa: E402
    FIXTURE_ROOT,
    fixture_outputs,
)
from study_anything.cbb.protocol.models import (  # noqa: E402
    PROTOCOL_MODELS,
    DeliveryScope,
    GateDecisionV1,
)


REPORT_SCHEMA_VERSION = "cbb-v1-contracts-verification-v1"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-v1-contracts.json"

FORBIDDEN_RUNTIME_IMPORTS = {
    "anthropic",
    "httpx",
    "langchain",
    "openai",
    "playwright",
    "requests",
    "selenium",
    "socket",
    "subprocess",
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return payload


def _check_asset_freshness() -> dict[str, int]:
    expected = {**schema_outputs(ROOT), **fixture_outputs(ROOT)}
    missing = [path for path in expected if not path.is_file()]
    stale = [
        path
        for path, content in expected.items()
        if path.is_file() and path.read_text(encoding="utf-8") != content
    ]
    if missing or stale:
        raise RuntimeError(
            "CBB v1 assets are stale; run generate_cbb_v1_contract_assets.py --write: "
            f"missing={[path.name for path in missing]}, stale={[path.name for path in stale]}"
        )
    return {
        "schema_count": len(schema_outputs(ROOT)),
        "fixture_count": len(fixture_outputs(ROOT)),
    }


def _schema_report() -> list[dict[str, str]]:
    reports: list[dict[str, str]] = []
    for path, expected in schema_outputs(ROOT).items():
        payload = _load_json(path)
        schema_version = str(payload.get("$id") or "")
        if schema_version not in PROTOCOL_MODELS:
            raise RuntimeError(f"Unknown canonical schema id: {schema_version}")
        if payload.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise RuntimeError(f"Schema draft drifted: {path}")
        if payload.get("additionalProperties") is not False:
            raise RuntimeError(f"Canonical schema must forbid unknown fields: {path}")
        reports.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "schema_version": schema_version,
                "sha256": canonical_sha256(json.loads(expected)),
            }
        )
    return reports


def _validate_canonical_set(payloads: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for label, payload in payloads.items():
        if not isinstance(payload, dict):
            raise RuntimeError(f"Canonical fixture {label} must be an object")
        schema_version = str(payload.get("schema_version") or "")
        model_type = PROTOCOL_MODELS.get(schema_version)
        if model_type is None:
            raise RuntimeError(f"Canonical fixture {label} has unknown schema: {schema_version}")
        model = validate_payload(model_type, payload)
        if model_payload(model) != payload:
            raise RuntimeError(f"Canonical fixture {label} changed after validation")
        result[label] = schema_version
    return result


def _determinism_report(pass_fixture: dict[str, Any]) -> dict[str, Any]:
    policy_payload = pass_fixture["canonical"]["trust_policy"]
    reversed_payload = dict(reversed(list(policy_payload.items())))
    model_type = PROTOCOL_MODELS[policy_payload["schema_version"]]
    first = validate_payload(model_type, policy_payload)
    second = validate_payload(model_type, reversed_payload)
    first_bytes = canonical_json_bytes(first)
    second_bytes = canonical_json_bytes(second)
    if first_bytes != second_bytes:
        raise RuntimeError("Canonical JSON bytes changed with input object key order")
    if b"\n" in first_bytes:
        raise RuntimeError("Canonical JSON bytes must not include formatting whitespace")
    return {
        "algorithm": "cbb-json-c14n-v1",
        "stable_across_key_order": True,
        "byte_count": len(first_bytes),
        "sha256": canonical_sha256(first),
    }


def _capture_rejection(
    payload: dict[str, Any],
    schema_version: str,
    expected_error: str,
) -> str:
    model_type = PROTOCOL_MODELS[schema_version]
    try:
        validate_payload(model_type, payload)
    except Exception as exc:  # noqa: BLE001 - verifier records a bounded reason.
        message = str(exc)
        if expected_error not in message:
            raise RuntimeError(
                f"Rejection reason drifted for {schema_version}: expected {expected_error!r}"
            ) from exc
        if "uses forbidden field" in message:
            return "forbidden field rejected"
        if "validation error" in message:
            return "strict schema validation rejected malformed payload"
        return type(exc).__name__
    raise RuntimeError(f"Expected canonical payload rejection for {schema_version}")


def _negative_fixture_report() -> dict[str, str]:
    fixture_dir = ROOT / FIXTURE_ROOT
    secret_case = _load_json(fixture_dir / "secret-like.json")
    malformed_case = _load_json(fixture_dir / "malformed.json")
    naive_timestamp_case = _load_json(fixture_dir / "naive-timestamp.json")
    invalid_state_case = _load_json(fixture_dir / "invalid-state.json")
    return {
        "secret_like": _capture_rejection(
            secret_case["payload"],
            secret_case["model_schema_version"],
            secret_case["expected_error"],
        ),
        "malformed": _capture_rejection(
            malformed_case["payload"],
            malformed_case["model_schema_version"],
            malformed_case["expected_error"],
        ),
        "naive_timestamp": _capture_rejection(
            naive_timestamp_case["payload"],
            naive_timestamp_case["model_schema_version"],
            naive_timestamp_case["expected_error"],
        ),
        "invalid_state": _capture_rejection(
            invalid_state_case["payload"],
            invalid_state_case["model_schema_version"],
            invalid_state_case["expected_error"],
        ),
    }


def _state_fixture_report() -> dict[str, Any]:
    fixture_dir = ROOT / FIXTURE_ROOT
    pass_case = _load_json(fixture_dir / "pass.json")
    missing_case = _load_json(fixture_dir / "missing-evidence.json")
    stale_case = _load_json(fixture_dir / "stale.json")
    hard_deny_case = _load_json(fixture_dir / "hard-deny.json")
    pass_contracts = _validate_canonical_set(pass_case["canonical"])
    missing_contracts = _validate_canonical_set(missing_case["canonical"])
    stale_contracts = _validate_canonical_set(stale_case["canonical"])
    hard_deny = validate_payload(GateDecisionV1, hard_deny_case["payload"])
    if hard_deny.status != "block" or hard_deny.approved_scope != DeliveryScope.BLOCKED:
        raise RuntimeError("Hard-deny fixture did not remain blocked")
    if missing_case["canonical"]["gate_decision"]["status"] != "needs_evidence":
        raise RuntimeError("Missing-evidence fixture did not request evidence")
    if stale_case["canonical"]["qualified_reconstruction"]["status"] != "stale":
        raise RuntimeError("Stale fixture did not remain stale")
    return {
        "pass": pass_contracts,
        "missing_evidence": missing_contracts,
        "stale": stale_contracts,
        "hard_deny": {
            "status": hard_deny.status,
            "approved_scope": hard_deny.approved_scope.value,
            "hard_denies_triggered": list(hard_deny.hard_denies_triggered),
        },
    }


def _provenance_binding_report() -> dict[str, bool]:
    pass_case = _load_json(ROOT / FIXTURE_ROOT / "pass.json")
    canonical = pass_case["canonical"]
    policy = canonical["trust_policy"]
    evidence = canonical["evidence_bundle"]
    reconstruction = canonical["qualified_reconstruction"]
    decision = canonical["gate_decision"]
    provenance = canonical["receipt_provenance"]
    receipt = canonical["delivery_trust_receipt"]
    verifier_identity = {
        "verifier_id": provenance["verifier"]["verifier_id"],
        "verifier_version": provenance["verifier"]["verifier_version"],
    }
    checks = {
        "subject_digest_matches": provenance["subject_digest_sha256"]
        == canonical_sha256({"subject_ref": policy["subject_ref"]}),
        "policy_digest_matches": provenance["policy_digest_sha256"]
        == canonical_sha256(policy),
        "evidence_digest_matches": provenance["evidence_digest_sha256"]
        == canonical_sha256(evidence),
        "verifier_digest_matches": provenance["verifier"]["verifier_digest_sha256"]
        == canonical_sha256(verifier_identity),
        "embedded_provenance_matches": receipt["provenance"] == provenance,
        "decision_status_matches": receipt["status"] == decision["status"],
        "decision_scope_matches": receipt["approved_scope"]
        == decision["approved_scope"],
        "policy_ref_matches": receipt["policy_ref"] == policy["policy_id"],
        "evidence_ref_matches": receipt["evidence_bundle_ref"]
        == evidence["bundle_id"],
        "reconstruction_ref_matches": receipt["reconstruction_ref"]
        == reconstruction["reconstruction_id"],
        "decision_ref_matches": receipt["decision_ref"] == decision["decision_id"],
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f"Canonical provenance binding drifted: {failed}")
    return checks


def _runtime_isolation_report() -> dict[str, Any]:
    source_dir = ROOT / "apps" / "api" / "study_anything" / "cbb" / "protocol"
    checked: list[str] = []
    found: list[dict[str, str]] = []
    for path in sorted(source_dir.glob("*.py")):
        checked.append(path.relative_to(ROOT).as_posix())
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported: str | None = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in FORBIDDEN_RUNTIME_IMPORTS:
                        found.append({"path": path.name, "import": alias.name})
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = node.module
            if imported and imported.split(".", 1)[0] in FORBIDDEN_RUNTIME_IMPORTS:
                found.append({"path": path.name, "import": imported})
    if found:
        raise RuntimeError(f"Canonical protocol path imports runtime authority: {found}")
    return {
        "checked_files": checked,
        "forbidden_imports": sorted(FORBIDDEN_RUNTIME_IMPORTS),
        "findings": [],
        "model_calls_performed": False,
        "network_calls_performed": False,
        "production_mutation_performed": False,
        "automatic_customer_send_performed": False,
    }


def build_report() -> dict[str, Any]:
    assets = _check_asset_freshness()
    pass_fixture = _load_json(ROOT / FIXTURE_ROOT / "pass.json")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "canonical_contracts": sorted(PROTOCOL_MODELS),
        "assets": assets,
        "schemas": _schema_report(),
        "states": _state_fixture_report(),
        "negative_fixtures": _negative_fixture_report(),
        "canonicalization": _determinism_report(pass_fixture),
        "provenance_bindings": _provenance_binding_report(),
        "runtime_isolation": _runtime_isolation_report(),
        "claim_boundary": (
            "This verifies local deterministic Protocol v1 contracts, schemas, fixtures, "
            "and canonical JSON bytes. It does not prove production delivery, portable "
            "cryptographic signing, customer outcomes, safe Agentic evolution, or "
            "independent audit completion."
        ),
        "privacy": {
            "metadata_only": True,
            "raw_payloads_included": False,
            "real_secrets_included": False,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "production_mutation_performed": False,
        },
    }


def serialize_report(report: dict[str, Any]) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    if args.check == args.write:
        raise SystemExit("Choose exactly one of --check or --write.")
    serialized = serialize_report(build_report())
    output = Path(args.output)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    elif not output.is_file() or output.read_text(encoding="utf-8") != serialized:
        raise SystemExit(
            "CBB v1 contracts report is stale. Run: "
            "python3 scripts/verify_cbb_v1_contracts.py --write"
        )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
