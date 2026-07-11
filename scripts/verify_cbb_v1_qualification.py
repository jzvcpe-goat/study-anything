#!/usr/bin/env python3
"""Verify scoped, expiring CBB Protocol v1 human and model qualification."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.kernel.gate import evaluate_gate  # noqa: E402
from study_anything.cbb.protocol.models import (  # noqa: E402
    QualifiedReconstructionV1,
    ReconstructionBoundaryType,
    TrustPolicyV1,
)
from study_anything.cbb.scenarios.fixtures import build_scenario_cases  # noqa: E402


REPORT_SCHEMA_VERSION = "cbb-v1-qualification-verification-v1"
DEFAULT_REPORT = Path("platform/generated/study-anything-cbb-v1-qualification.json")


def _base() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    inputs = deepcopy(build_scenario_cases()["paid-customer-candidate"]["inputs"])
    return (
        inputs["trust_policy"],
        inputs["evidence_bundle"],
        inputs["qualified_reconstruction"],
    )


def _validation_rejected(
    validator: Callable[[dict[str, Any]], object],
    payload: dict[str, Any],
) -> bool:
    try:
        validator(payload)
    except ValidationError:
        return True
    return False


def _blocked_or_needs(
    policy_payload: dict[str, Any],
    evidence_payload: dict[str, Any],
    reconstruction_payload: dict[str, Any],
    expected_status: str,
    expected_marker: str,
) -> bool:
    from study_anything.cbb.protocol.models import EvidenceBundleV1

    policy = TrustPolicyV1.model_validate(policy_payload)
    evidence = EvidenceBundleV1.model_validate(evidence_payload)
    reconstruction = QualifiedReconstructionV1.model_validate(
        reconstruction_payload
    )
    decision = evaluate_gate(policy, evidence, reconstruction)
    searchable = decision.reasons + decision.missing_evidence_types
    return decision.status == expected_status and any(
        expected_marker in item for item in searchable
    )


def _stale_reconstruction(payload: dict[str, Any]) -> dict[str, Any]:
    stale = deepcopy(payload)
    stale.update(
        {
            "status": "stale",
            "qualified_scope": "blocked",
            "active_reconstruction": False,
            "required_mrus_passed": 0,
            "valid_until": "2026-06-27T00:00:00Z",
        }
    )
    stale["missing_mru_refs"] = sorted(
        result["mru_ref"] for result in stale["mru_results"]
    )
    for result in stale["mru_results"]:
        result.update({"status": "stale", "evidence_refs": []})
    stale["human_capability_profile"].update(
        {
            "status": "stale",
            "maximum_scope": "blocked",
            "valid_until": "2026-06-27T00:00:00Z",
        }
    )
    stale["claim_boundary"].update(
        {
            "maximum_scope": "blocked",
            "current_claim": "The reconstruction and human capability are stale.",
        }
    )
    return stale


def _missing_mru_reconstruction(payload: dict[str, Any]) -> dict[str, Any]:
    missing = deepcopy(payload)
    first = missing["mru_results"][0]
    first.update({"status": "missing", "evidence_refs": []})
    missing.update(
        {
            "status": "missing",
            "qualified_scope": "blocked",
            "active_reconstruction": False,
            "required_mrus_passed": len(missing["mru_results"]) - 1,
            "missing_mru_refs": [first["mru_ref"]],
        }
    )
    missing["claim_boundary"].update(
        {
            "maximum_scope": "blocked",
            "current_claim": "A required Minimum Reconstructable Unit is missing.",
        }
    )
    return missing


def build_report() -> dict[str, Any]:
    policy, evidence, reconstruction = _base()
    checks: dict[str, bool] = {}

    passive = deepcopy(reconstruction)
    passive["passive_attention_only"] = True
    checks["passive_attention_cannot_qualify"] = _validation_rejected(
        QualifiedReconstructionV1.model_validate,
        passive,
    )

    global_profile = deepcopy(reconstruction)
    global_profile["human_capability_profile"]["project_ref"] = "global"
    global_profile["project_ref"] = "global"
    checks["global_human_label_rejected"] = _validation_rejected(
        QualifiedReconstructionV1.model_validate,
        global_profile,
    )

    permanent_label = deepcopy(reconstruction)
    permanent_label["human_capability_profile"]["permanent_global_label"] = True
    checks["permanent_human_label_rejected"] = _validation_rejected(
        QualifiedReconstructionV1.model_validate,
        permanent_label,
    )

    counter_evidence = deepcopy(reconstruction)
    counter_evidence["human_capability_profile"]["counter_evidence_refs"] = [
        "counter-evidence:incident-001"
    ]
    checks["active_human_profile_with_counter_evidence_rejected"] = (
        _validation_rejected(
            QualifiedReconstructionV1.model_validate,
            counter_evidence,
        )
    )

    vendor_only = deepcopy(policy)
    vendor_only["model_capability_profile"]["vendor_claims_sufficient"] = True
    checks["vendor_claims_cannot_authorize_model_scope"] = _validation_rejected(
        TrustPolicyV1.model_validate,
        vendor_only,
    )

    challenged_model = deepcopy(policy)
    challenged_model["model_capability_profile"].update(
        {
            "status": "challenged",
            "maximum_autonomy_scope": "blocked",
            "counter_evidence_refs": ["counter-evidence:model-regression-001"],
        }
    )
    checks["challenged_model_narrows_policy"] = _validation_rejected(
        TrustPolicyV1.model_validate,
        challenged_model,
    )

    missing_mru = _missing_mru_reconstruction(reconstruction)
    checks["missing_mru_needs_evidence"] = _blocked_or_needs(
        policy,
        evidence,
        missing_mru,
        "needs_evidence",
        "qualified_reconstruction",
    )

    stale = _stale_reconstruction(reconstruction)
    checks["stale_human_profile_needs_evidence"] = _blocked_or_needs(
        policy,
        evidence,
        stale,
        "needs_evidence",
        "qualified_reconstruction",
    )

    missing_role = deepcopy(reconstruction)
    missing_role["reviewer_roles"].remove("operational_reviewer")
    missing_role["human_capability_profile"]["qualified_roles"].remove(
        "operational_reviewer"
    )
    checks["missing_scoped_reviewer_role_needs_evidence"] = _blocked_or_needs(
        policy,
        evidence,
        missing_role,
        "needs_evidence",
        "role:operational_reviewer",
    )

    scenario_mismatch = deepcopy(reconstruction)
    scenario_mismatch["scenario_ref"] = "scenario:different"
    scenario_mismatch["human_capability_profile"]["scenario_refs"] = [
        "scenario:different"
    ]
    checks["scenario_mismatch_blocks"] = _blocked_or_needs(
        policy,
        evidence,
        scenario_mismatch,
        "block",
        "reconstruction_scenario_ref_mismatch",
    )

    boundary_mismatch = deepcopy(reconstruction)
    original_boundary = boundary_mismatch["mru_results"][0]["boundary_type"]
    replacement_boundary = ReconstructionBoundaryType.RESIDUAL_RISK.value
    if original_boundary == replacement_boundary:
        replacement_boundary = ReconstructionBoundaryType.CRITICAL_FAILURE_PATH.value
    boundary_mismatch["mru_results"][0]["boundary_type"] = replacement_boundary
    boundary_types = boundary_mismatch["human_capability_profile"]["boundary_types"]
    if replacement_boundary not in boundary_types:
        boundary_types.append(replacement_boundary)
    checks["mru_boundary_mismatch_blocks"] = _blocked_or_needs(
        policy,
        evidence,
        boundary_mismatch,
        "block",
        "mru_boundary_mismatch",
    )

    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f"qualification checks failed: {failed}")

    matrix = []
    for case_id, case in sorted(build_scenario_cases().items()):
        scenario_reconstruction = case["inputs"]["qualified_reconstruction"]
        profile = scenario_reconstruction["human_capability_profile"]
        matrix.append(
            {
                "case_id": case_id,
                "project_ref": profile["project_ref"],
                "scenario_refs": profile["scenario_refs"],
                "qualified_roles": profile["qualified_roles"],
                "boundary_types": profile["boundary_types"],
                "maximum_scope": profile["maximum_scope"],
                "valid_until": profile["valid_until"],
                "permanent_global_label": profile["permanent_global_label"],
            }
        )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "checks": checks,
        "reviewer_qualification_matrix": matrix,
        "invariants": [
            "qualification is project, scenario, boundary, role, scope, and time bound",
            "passive attention is never qualified reconstruction",
            "counter-evidence, expiry, missing MRUs, and missing roles narrow trust",
            "vendor model claims do not authorize delivery scope",
            "qualification is not a permanent global label",
        ],
        "claim_boundary": (
            "This verifies deterministic local qualification contracts and negative cases. "
            "It does not certify a real reviewer, model, organization, customer outcome, "
            "production deployment, or independent audit completion."
        ),
        "privacy": {
            "metadata_only": True,
            "raw_reconstruction_answers_included": False,
            "attention_streams_included": False,
            "personal_identity_included": False,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "production_mutation_performed": False,
        },
    }


def _serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    if args.check == args.write:
        raise SystemExit("Choose exactly one of --check or --write.")
    serialized = _serialize(build_report())
    output = ROOT / args.output
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    elif not output.is_file() or output.read_text(encoding="utf-8") != serialized:
        raise SystemExit(
            "CBB v1 qualification report is stale. Run: "
            "python3 scripts/verify_cbb_v1_qualification.py --write"
        )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
