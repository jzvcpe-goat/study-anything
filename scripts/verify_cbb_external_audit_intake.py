#!/usr/bin/env python3
"""Verify signed audit-report intake while keeping the open audit incomplete."""

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
from study_anything.cbb.audit.fixtures import (  # noqa: E402
    build_audit_intake_cases,
)
from study_anything.cbb.audit.intake import (  # noqa: E402
    evaluate_external_audit_intake,
)
from study_anything.cbb.audit.models import (  # noqa: E402
    AuditExpectedScopeV1,
    ExternalAuditIntakeEnvelopeV1,
    ExternalAuditIntakeReceiptV1,
)
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    CanonicalProtocolError,
    assert_safe_metadata,
)


REPORT_PATH = (
    ROOT / "platform" / "generated" / "study-anything-cbb-external-audit-intake.json"
)
EVALUATED_AT = "2026-07-14T00:00:00Z"


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
    cases = build_audit_intake_cases(ROOT)
    expected_states = {
        "audit-ready": "audit_ready",
        "synthetic-valid": "synthetic_validated",
        "wrong-commit": "rejected",
        "incomplete-scope": "rejected",
        "self-certified": "rejected",
        "open-high": "remediation_pending",
        "invalid-signature": "rejected",
    }
    case_reports: list[dict[str, Any]] = []
    for case_id in sorted(cases):
        payload = cases[case_id]
        expected_scope = AuditExpectedScopeV1.model_validate(payload["expected_scope"])
        receipt = ExternalAuditIntakeReceiptV1.model_validate(payload["receipt"])
        if payload["envelope"] is not None:
            envelope = ExternalAuditIntakeEnvelopeV1.model_validate(payload["envelope"])
            rebuilt = evaluate_external_audit_intake(
                expected_scope,
                envelope,
                evaluated_at=EVALUATED_AT,
            )
            if rebuilt != receipt:
                raise RuntimeError(f"{case_id}: audit intake receipt drifted")
        if receipt.state.value != expected_states[case_id]:
            raise RuntimeError(f"{case_id}: unexpected audit intake state")
        if receipt.audit_closure_accepted or receipt.production_certification_granted:
            raise RuntimeError(f"{case_id}: fixture incorrectly closed or certified audit")
        if receipt.report_execution_completed:
            raise RuntimeError(f"{case_id}: fixture claimed real external execution")
        case_reports.append(
            {
                "case_id": case_id,
                "state": receipt.state.value,
                "signature_verified": receipt.signature_verified,
                "external_identity_attested": receipt.external_identity_attested,
                "open_critical_high_count": receipt.open_critical_high_count,
            }
        )

    real_source_forgery = deepcopy(cases["synthetic-valid"]["envelope"])
    real_source_forgery["source_class"] = "external_report"
    synthetic_to_real_rejected = _rejected(
        lambda: ExternalAuditIntakeEnvelopeV1.model_validate(real_source_forgery),
        "externally attested identity",
    )

    closure_forgery = deepcopy(cases["synthetic-valid"]["receipt"])
    closure_forgery.update(
        {
            "state": "audit_closed",
            "audit_closure_accepted": True,
            "report_execution_completed": True,
            "external_identity_attested": False,
        }
    )
    synthetic_closure_rejected = _rejected(
        lambda: ExternalAuditIntakeReceiptV1.model_validate(closure_forgery),
        "valid independent external evidence",
    )

    forged_fingerprint_payload = deepcopy(cases["synthetic-valid"]["envelope"])
    forged_fingerprint_payload["detached_signature"][
        "public_key_fingerprint_sha256"
    ] = "f" * 64
    forged_fingerprint_payload["auditor_trust"][
        "public_key_fingerprint_sha256"
    ] = "f" * 64
    forged_fingerprint_envelope = ExternalAuditIntakeEnvelopeV1.model_validate(
        forged_fingerprint_payload
    )
    forged_fingerprint_receipt = evaluate_external_audit_intake(
        AuditExpectedScopeV1.model_validate(
            cases["synthetic-valid"]["expected_scope"]
        ),
        forged_fingerprint_envelope,
        evaluated_at=EVALUATED_AT,
    )
    forged_public_key_fingerprint_rejected = (
        forged_fingerprint_receipt.state.value == "rejected"
        and "public_key_fingerprint_valid"
        in forged_fingerprint_receipt.blocking_reasons
    )

    self_asserted_payload = deepcopy(cases["synthetic-valid"]["envelope"])
    self_asserted_payload["source_class"] = "external_report"
    self_asserted_payload["auditor_trust"].update(
        {
            "identity_status": "externally_attested",
            "independence_attestation_ref": "external:self-asserted-only",
            "independent_from_repository": True,
            "fixture_only": False,
        }
    )
    self_asserted_envelope = ExternalAuditIntakeEnvelopeV1.model_validate(
        self_asserted_payload
    )
    self_asserted_receipt = evaluate_external_audit_intake(
        AuditExpectedScopeV1.model_validate(
            cases["synthetic-valid"]["expected_scope"]
        ),
        self_asserted_envelope,
        evaluated_at=EVALUATED_AT,
    )
    self_asserted_external_identity_rejected = (
        self_asserted_receipt.state.value == "rejected"
        and not self_asserted_receipt.external_identity_attested
        and "signer_trusted_for_source_class"
        in self_asserted_receipt.blocking_reasons
    )

    secret_envelope = deepcopy(cases["synthetic-valid"]["envelope"])
    secret_envelope["api_key"] = "synthetic-secret-field"
    secret_like_metadata_rejected = _rejected(
        lambda: assert_safe_metadata(secret_envelope, label="audit intake fixture"),
        "forbidden field",
    )

    report_schema = json.loads(
        (
            ROOT
            / "platform"
            / "schemas"
            / "security"
            / "external-security-audit-report-v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    schema_requires_bindings = (
        "evidence_bindings" in report_schema["required"]
        and report_schema["properties"]["evidence_bindings"]["additionalProperties"]
        is False
    )
    states = {item["case_id"]: item["state"] for item in case_reports}
    checks = {
        "generated_assets_current": generated_current,
        "seven_intake_cases_replayed": len(case_reports) == 7,
        "audit_states_remain_distinct": set(states.values())
        == {"audit_ready", "synthetic_validated", "rejected", "remediation_pending"},
        "wrong_commit_rejected": states["wrong-commit"] == "rejected",
        "invalid_signature_rejected": states["invalid-signature"] == "rejected",
        "incomplete_scope_rejected": states["incomplete-scope"] == "rejected",
        "self_certification_rejected": states["self-certified"] == "rejected",
        "open_high_requires_remediation": states["open-high"] == "remediation_pending",
        "synthetic_fixture_never_closes_audit": states["synthetic-valid"]
        == "synthetic_validated",
        "synthetic_to_real_source_forgery_rejected": synthetic_to_real_rejected,
        "synthetic_closure_forgery_rejected": synthetic_closure_rejected,
        "forged_public_key_fingerprint_rejected": (
            forged_public_key_fingerprint_rejected
        ),
        "self_asserted_external_identity_rejected": (
            self_asserted_external_identity_rejected
        ),
        "secret_like_metadata_rejected": secret_like_metadata_rejected,
        "report_schema_binds_audit_conformance_and_plan": schema_requires_bindings,
        "no_fixture_claims_real_audit_execution": all(
            not item["external_identity_attested"] for item in case_reports
        ),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": "cbb-external-audit-intake-verification-v1",
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_checks": failed,
        "case_reports": case_reports,
        "audit": {
            "audit_issue_ref": "github-issue:414",
            "external_auditor_assigned": False,
            "external_signed_report_received": False,
            "audit_completed": False,
            "audit_closure_accepted": False,
            "synthetic_fixture_count": len(case_reports),
        },
        "claim_boundary": (
            "This verifies the structure, signature, binding, rejection, and state-machine "
            "behavior of external audit intake using synthetic fixtures. It does not invent "
            "an auditor, receive a real report, complete issue #414, certify production, or "
            "grant delivery authority."
        ),
        "privacy": {
            "metadata_only": True,
            "raw_source_text_included": False,
            "private_exploit_details_included": False,
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
                "verify_cbb_external_audit_intake failed: report is stale. "
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
