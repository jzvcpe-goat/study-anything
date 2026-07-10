#!/usr/bin/env python3
"""Verify CBB Protocol v1 local signing, expiry, revocation, and replay controls."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.protocol.canonical import model_payload  # noqa: E402
from study_anything.cbb.protocol.models import DeliveryScope  # noqa: E402
from study_anything.cbb.provenance.fixtures import (  # noqa: E402
    build_provenance_cases,
    fixture_outputs,
    signed_package,
    unsigned_package,
)
from study_anything.cbb.provenance.signing import (  # noqa: E402
    OfflineProvenancePackageV1,
    sign_provenance,
    verify_offline_package,
)


REPORT_SCHEMA_VERSION = "cbb-v1-provenance-verification-v1"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-v1-provenance.json"


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _verify_case(case_id: str, case: dict[str, Any]) -> dict[str, Any]:
    package = OfflineProvenancePackageV1.model_validate(case["package"])
    context = case["verification_context"]
    seen_nonces: set[str] = set()
    first = verify_offline_package(
        package,
        now=context["now"],
        revoked_handles=context.get("revoked_handles", []),
        seen_nonces=seen_nonces if context.get("consume_nonce") else None,
        consume_nonce=bool(context.get("consume_nonce")),
    )
    if case_id == "replay":
        if first.status != case["expected_first_status"]:
            raise RuntimeError("replay: first nonce consumption did not pass")
        second = verify_offline_package(
            package,
            now=context["now"],
            seen_nonces=seen_nonces,
            consume_nonce=True,
        )
        if second.status != case["expected_second_status"]:
            raise RuntimeError("replay: second nonce consumption was not rejected")
        if not set(case["expected_second_reasons"]).issubset(second.reasons):
            raise RuntimeError("replay: rejection reason drifted")
        return {
            "case_id": case_id,
            "first_status": first.status,
            "second_status": second.status,
            "second_reasons": list(second.reasons),
        }

    if first.status != case["expected_status"]:
        raise RuntimeError(
            f"{case_id}: expected {case['expected_status']}, got {first.status}"
        )
    expected_reasons = set(case.get("expected_reasons", []))
    if not expected_reasons.issubset(first.reasons):
        raise RuntimeError(
            f"{case_id}: expected reasons {sorted(expected_reasons)}, got {first.reasons}"
        )
    return {
        "case_id": case_id,
        "status": first.status,
        "reasons": list(first.reasons),
        "checks": dict(first.checks),
    }


def _scope_escalation_is_rejected() -> bool:
    package = signed_package()
    try:
        sign_provenance(
            unsigned_package().receipt_provenance,
            package.trust_policy,
            package.evidence_bundle,
            package.qualified_reconstruction,
            package.gate_decision,
            package.delivery_trust_receipt,
            object(),
            signer_id="fixture",
            key_id="fixture",
            maximum_scope=DeliveryScope.PRODUCTION_CANDIDATE,
        )
    except ValueError as exc:
        return "cannot expand" in str(exc)
    return False


def _secret_like_metadata_is_rejected() -> bool:
    payload = model_payload(signed_package())
    provenance = deepcopy(payload["receipt_provenance"])
    provenance["signer"]["signer_id"] = "sk-0123456789abcdefghijkl"
    payload["receipt_provenance"] = provenance
    payload["delivery_trust_receipt"]["provenance"] = deepcopy(provenance)
    package = OfflineProvenancePackageV1.model_validate(payload)
    result = verify_offline_package(package, now="2026-07-10T00:00:00Z")
    return result.reasons == ("safe_metadata",) and "0123456789" not in repr(result)


def build_report() -> dict[str, Any]:
    cases = build_provenance_cases()
    results = [_verify_case(case_id, cases[case_id]) for case_id in sorted(cases)]
    passing = signed_package()
    package_payload = model_payload(passing)
    serialized = _json_text(package_payload)
    if package_payload["private_key_material_included"] is not False:
        raise RuntimeError("offline package did not assert private-key exclusion")
    if "BEGIN PRIVATE KEY" in serialized:
        raise RuntimeError("offline package exposed private key material")
    if not _scope_escalation_is_rejected():
        raise RuntimeError("local signing did not reject scope escalation")
    if not _secret_like_metadata_is_rejected():
        raise RuntimeError("secret-like metadata did not fail closed without echo")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "case_count": len(results),
        "cases": results,
        "properties": {
            "algorithm": "Ed25519",
            "canonicalization": "cbb-json-c14n-v1",
            "policy_evidence_reconstruction_decision_bound": True,
            "deterministic_gate_replayed_offline": True,
            "unsigned_is_development_only": True,
            "expiry_enforced": True,
            "local_revocation_registry_enforced": True,
            "optional_nonce_consumption_enforced": True,
            "scope_escalation_rejected": True,
            "private_key_material_in_package": False,
            "secret_like_metadata_rejected_without_echo": True,
        },
        "claim_boundary": (
            "A passing result proves local Ed25519 key possession and canonical object "
            "integrity for this package. It does not prove third-party signer identity, "
            "global revocation status, production approval, customer outcomes, or "
            "independent security audit completion."
        ),
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "production_mutation_performed": False,
            "private_key_material_exported": False,
        },
    }


def _outputs(report_path: Path) -> dict[Path, str]:
    return {**fixture_outputs(ROOT), report_path: _json_text(build_report())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("choose exactly one of --check or --write")
    outputs = _outputs(Path(args.report))
    if args.write:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    else:
        stale = [
            path.relative_to(ROOT).as_posix()
            for path, content in outputs.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            raise SystemExit(
                "CBB v1 provenance assets are stale; run "
                f"verify_cbb_v1_provenance.py --write: {stale}"
            )
    print(_json_text(build_report()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
