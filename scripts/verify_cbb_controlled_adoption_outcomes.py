#!/usr/bin/env python3
"""Verify bounded adoption outcomes without manufacturing real adopter evidence."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_cbb_adoption_audit_assets import expected_outputs  # noqa: E402
from study_anything.cbb.adoption.evaluator import (  # noqa: E402
    evaluate_controlled_adoption,
)
from study_anything.cbb.adoption.fixtures import (  # noqa: E402
    RELEASE_SCOPE_COMMIT,
    build_adoption_cases,
)
from study_anything.cbb.adoption.models import (  # noqa: E402
    AdoptionEvidenceClass,
    ControlledAdoptionCaseV1,
    ControlledAdoptionReceiptV1,
)
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    CanonicalProtocolError,
    assert_safe_metadata,
)
from study_anything.cbb.protocol.models import DeliveryScope  # noqa: E402
from study_anything.cbb.provenance.fixtures import signed_package  # noqa: E402


REPORT_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cbb-controlled-adoption-outcomes.json"
)


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _rejected(fn: Callable[[], object], expected: str) -> bool:
    try:
        fn()
    except (CanonicalProtocolError, ValueError) as exc:
        return expected in str(exc)
    return False


def build_report() -> dict[str, Any]:
    generated_current = all(
        path.exists() and path.read_text(encoding="utf-8") == content
        for path, content in expected_outputs().items()
    )
    conformance = json.loads(
        (
            ROOT
            / "platform"
            / "generated"
            / "study-anything-cbb-v1-conformance-pack.json"
        ).read_text(encoding="utf-8")
    )
    conformance_digest = str(conformance["archive_sha256"])
    package = signed_package()
    cases = build_adoption_cases(ROOT)
    expected_states = {
        "shadow-pass": ("observed", "sandbox_only"),
        "dogfood-pass": ("observed", "internal_handoff"),
        "canary-scope-expansion-blocked": ("blocked", "blocked"),
        "incident-freezes": ("incident_recorded", "blocked"),
        "rollback-narrows": ("rolled_back", "sandbox_only"),
        "claim-violation-revokes": ("revoked", "blocked"),
        "reopen-requires-fresh-clearance": ("reopen_required", "blocked"),
    }
    case_reports: list[dict[str, Any]] = []
    for case_id in sorted(cases):
        payload = cases[case_id]
        case = ControlledAdoptionCaseV1.model_validate(payload["case"])
        receipt = ControlledAdoptionReceiptV1.model_validate(payload["receipt"])
        rebuilt = evaluate_controlled_adoption(
            package,
            case,
            expected_release_scope_commit=RELEASE_SCOPE_COMMIT,
            expected_conformance_pack_sha256=conformance_digest,
            revoked_source_handles=(
                {case.binding.source_clearance_revocation_handle}
                if case.source_revoked_before_observation
                else set()
            ),
        )
        if rebuilt != receipt:
            raise RuntimeError(f"{case_id}: controlled adoption receipt drifted")
        expected_status, expected_scope = expected_states[case_id]
        if receipt.status.value != expected_status or receipt.resulting_scope.value != expected_scope:
            raise RuntimeError(f"{case_id}: unexpected adoption state")
        if receipt.real_adopter_evidence or receipt.audit_completed:
            raise RuntimeError(f"{case_id}: synthetic fixture claimed external evidence")
        if receipt.customer_delivery_authorized or receipt.production_authorized:
            raise RuntimeError(f"{case_id}: adoption receipt granted release authority")
        case_reports.append(
            {
                "case_id": case_id,
                "status": receipt.status.value,
                "requested_scope": receipt.requested_scope.value,
                "resulting_scope": receipt.resulting_scope.value,
                "authorization_delta": receipt.authorization_delta,
            }
        )

    shadow = deepcopy(cases["shadow-pass"]["case"])
    shadow["effect_boundary"]["requested_scope"] = "production_candidate"
    inflated_case = ControlledAdoptionCaseV1.model_validate(shadow)
    inflated = evaluate_controlled_adoption(
        package,
        inflated_case,
        expected_release_scope_commit=RELEASE_SCOPE_COMMIT,
        expected_conformance_pack_sha256=conformance_digest,
    )
    scope_inflation_blocked = (
        inflated.status.value == "blocked"
        and inflated.resulting_scope == DeliveryScope.BLOCKED
        and not inflated.customer_delivery_authorized
    )

    wrong_digest_case = ControlledAdoptionCaseV1.model_validate(
        cases["dogfood-pass"]["case"]
    )
    wrong_digest = evaluate_controlled_adoption(
        package,
        wrong_digest_case,
        expected_release_scope_commit=RELEASE_SCOPE_COMMIT,
        expected_conformance_pack_sha256="0" * 64,
    )
    conformance_mismatch_blocked = (
        wrong_digest.status.value == "blocked"
        and "conformance_pack_digest_bound" in wrong_digest.reasons
    )

    wrong_commit_case = ControlledAdoptionCaseV1.model_validate(
        cases["dogfood-pass"]["case"]
    )
    wrong_commit = evaluate_controlled_adoption(
        package,
        wrong_commit_case,
        expected_release_scope_commit="0" * 40,
        expected_conformance_pack_sha256=conformance_digest,
    )
    release_commit_mismatch_blocked = (
        wrong_commit.status.value == "blocked"
        and "release_scope_commit_bound" in wrong_commit.reasons
    )

    external_claim = deepcopy(cases["shadow-pass"]["case"])
    external_claim["evidence_class"] = AdoptionEvidenceClass.EXTERNAL_ADOPTER.value
    external_claim["adoption_mode"] = "canary"
    external_claim["real_adopter_evidence_claimed"] = True
    external_claim["risk_owner_reacceptance_present"] = True
    external_case = ControlledAdoptionCaseV1.model_validate(external_claim)
    external_receipt = evaluate_controlled_adoption(
        package,
        external_case,
        expected_release_scope_commit=RELEASE_SCOPE_COMMIT,
        expected_conformance_pack_sha256=conformance_digest,
    )
    unattested_external_adopter_blocked = (
        external_receipt.status.value == "blocked"
        and not external_receipt.real_adopter_evidence
        and "external_adopter_attestation_supported" in external_receipt.reasons
    )

    real_claim = deepcopy(cases["shadow-pass"]["case"])
    real_claim["real_adopter_evidence_claimed"] = True
    synthetic_real_claim_rejected = _rejected(
        lambda: ControlledAdoptionCaseV1.model_validate(real_claim),
        "real adopter evidence",
    )

    production_mutation = deepcopy(cases["shadow-pass"]["case"])
    production_mutation["effect_boundary"]["production_mutation_performed"] = True
    production_mutation_rejected = _rejected(
        lambda: ControlledAdoptionCaseV1.model_validate(production_mutation),
        "Input should be False",
    )

    receipt_inflation = deepcopy(cases["shadow-pass"]["receipt"])
    receipt_inflation["resulting_scope"] = "production_candidate"
    receipt_inflation["claim_boundary"]["maximum_scope"] = "production_candidate"
    receipt_scope_inflation_rejected = _rejected(
        lambda: ControlledAdoptionReceiptV1.model_validate(receipt_inflation),
        "cannot expand source clearance scope",
    )

    secret_case = deepcopy(cases["shadow-pass"]["case"])
    secret_case["api_key"] = "synthetic-secret-field"
    secret_like_metadata_rejected = _rejected(
        lambda: assert_safe_metadata(secret_case, label="controlled adoption fixture"),
        "forbidden field",
    )

    checks = {
        "generated_assets_current": generated_current,
        "seven_state_cases_replayed": len(case_reports) == 7,
        "shadow_and_dogfood_pass_without_new_authority": all(
            item["status"] == "observed"
            for item in case_reports
            if item["case_id"] in {"shadow-pass", "dogfood-pass"}
        ),
        "canary_scope_inflation_blocked": scope_inflation_blocked,
        "conformance_digest_mismatch_blocked": conformance_mismatch_blocked,
        "release_commit_mismatch_blocked": release_commit_mismatch_blocked,
        "unattested_external_adopter_blocked": unattested_external_adopter_blocked,
        "synthetic_real_adopter_claim_rejected": synthetic_real_claim_rejected,
        "production_mutation_rejected": production_mutation_rejected,
        "receipt_scope_inflation_rejected": receipt_scope_inflation_rejected,
        "secret_like_metadata_rejected": secret_like_metadata_rejected,
        "incident_rollback_revocation_reopen_distinct": {
            item["status"]
            for item in case_reports
            if item["case_id"]
            in {
                "incident-freezes",
                "rollback-narrows",
                "claim-violation-revokes",
                "reopen-requires-fresh-clearance",
            }
        }
        == {"incident_recorded", "rolled_back", "revoked", "reopen_required"},
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": "cbb-controlled-adoption-verification-v1",
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_checks": failed,
        "case_reports": case_reports,
        "evidence": {
            "fixture_count": len(case_reports),
            "real_adopter_evidence_count": 0,
            "source_scope_commit": cases["shadow-pass"]["case"]["binding"][
                "release_scope_commit"
            ],
            "conformance_pack_sha256": conformance_digest,
        },
        "claim_boundary": (
            "This proves deterministic local shadow, dogfood, canary, incident, rollback, "
            "revocation, and reopen behavior against synthetic metadata fixtures. It does "
            "not prove external adoption, customer outcomes, production safety, or audit completion."
        ),
        "privacy": {
            "metadata_only": True,
            "raw_source_text_included": False,
            "raw_customer_payload_included": False,
            "real_secrets_included": False,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "production_mutation_performed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    data = _json_bytes(report)
    if args.check:
        if not REPORT_PATH.exists() or REPORT_PATH.read_bytes() != data:
            print(
                "verify_cbb_controlled_adoption_outcomes failed: report is stale. "
                "Run without --check.",
                file=sys.stderr,
            )
            return 1
        print(data.decode("utf-8"), end="")
        return 0 if report["status"] == "pass" else 1
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_bytes(data)
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
