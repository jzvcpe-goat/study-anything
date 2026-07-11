#!/usr/bin/env python3
"""Verify CBB Protocol v1 scenario policies and scope-sensitive reruns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.kernel.gate import evaluate_gate  # noqa: E402
from study_anything.cbb.protocol.canonical import canonical_sha256  # noqa: E402
from study_anything.cbb.protocol.models import (  # noqa: E402
    EvidenceBundleV1,
    QualifiedReconstructionV1,
    TrustPolicyV1,
)
from study_anything.cbb.scenarios.fixtures import (  # noqa: E402
    FIXTURE_ROOT,
    SCENARIO_SPECS,
    build_scenario_cases,
    fixture_outputs,
)


REPORT_SCHEMA_VERSION = "cbb-v1-scenario-verification-v1"
DEFAULT_REPORT = Path("platform/generated/study-anything-cbb-v1-scenarios.json")


def _load_inputs(payload: dict[str, Any]) -> tuple[
    TrustPolicyV1,
    EvidenceBundleV1,
    QualifiedReconstructionV1,
]:
    inputs = payload["inputs"]
    return (
        TrustPolicyV1.model_validate(inputs["trust_policy"]),
        EvidenceBundleV1.model_validate(inputs["evidence_bundle"]),
        QualifiedReconstructionV1.model_validate(inputs["qualified_reconstruction"]),
    )


def _freshness() -> list[str]:
    stale: list[str] = []
    for path, expected in fixture_outputs(ROOT).items():
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            stale.append(path.relative_to(ROOT).as_posix())
    return stale


def _decision_report() -> list[dict[str, Any]]:
    expected_cases = build_scenario_cases()
    rows: list[dict[str, Any]] = []
    for case_id in sorted(expected_cases):
        path = ROOT / FIXTURE_ROOT / f"{case_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        policy, evidence, reconstruction = _load_inputs(payload)
        decision = evaluate_gate(policy, evidence, reconstruction)
        expected = payload["expected"]
        checks = {
            "decision_status_matches": decision.status == expected["status"],
            "approved_scope_matches": decision.approved_scope.value
            == expected["approved_scope"],
            "policy_digest_matches": canonical_sha256(policy)
            == payload["policy_digest_sha256"],
            "scenario_ref_bound": policy.scenario_ref == policy.scenario.scenario_ref,
            "model_ref_bound": policy.scenario.model_ref
            == policy.model_capability_profile.model_ref,
            "recipient_has_no_automatic_authority": not policy.scenario.recipient.automatic_execution_authority,
            "no_global_human_label": not reconstruction.human_capability_profile.permanent_global_label,
        }
        failed = sorted(name for name, passed in checks.items() if not passed)
        if failed:
            raise RuntimeError(f"scenario {case_id} failed checks: {failed}")
        rows.append(
            {
                "case_id": case_id,
                "scenario_class": policy.scenario.scenario_class.value,
                "maximum_scope": policy.maximum_scope.value,
                "decision_status": decision.status,
                "approved_scope": decision.approved_scope.value,
                "recipient_external": policy.scenario.recipient.external,
                "affected_party_count": len(policy.scenario.affected_parties),
                "risk_owner_required": policy.scenario.risk_owner.required,
                "required_role_count": len(policy.required_roles),
                "required_mru_count": len(policy.required_mrus),
                "omitted_evidence": expected["omitted_evidence"],
                "checks": checks,
            }
        )
    return rows


def _rerun_report() -> dict[str, bool]:
    base_payload = build_scenario_cases()["limited-beta"]
    policy, evidence, reconstruction = _load_inputs(base_payload)
    base_digest = canonical_sha256(policy)
    base_decision = evaluate_gate(policy, evidence, reconstruction)
    mutations: dict[str, dict[str, Any]] = {}

    recipient = policy.model_dump(mode="json")
    recipient["scenario"]["recipient"]["recipient_ref"] = "recipient:changed"
    mutations["recipient_change"] = recipient

    model = policy.model_dump(mode="json")
    model["scenario"]["model_ref"] = "model:changed"
    model["model_capability_profile"]["model_ref"] = "model:changed"
    mutations["model_change"] = model

    affected_party = policy.model_dump(mode="json")
    affected_party["scenario"]["affected_parties"][0]["party_ref"] = (
        "affected-party:changed"
    )
    mutations["affected_party_change"] = affected_party

    impact = policy.model_dump(mode="json")
    impact["scenario"]["impact_classes"].append("new_material_impact")
    mutations["impact_change"] = impact

    checks: dict[str, bool] = {}
    for name, payload in mutations.items():
        changed_policy = TrustPolicyV1.model_validate(payload)
        changed_decision = evaluate_gate(changed_policy, evidence, reconstruction)
        checks[f"{name}_changes_policy_digest"] = (
            canonical_sha256(changed_policy) != base_digest
        )
        checks[f"{name}_changes_decision_id"] = (
            changed_decision.decision_id != base_decision.decision_id
        )
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f"scenario rerun checks failed: {failed}")
    return checks


def build_report() -> dict[str, Any]:
    stale = _freshness()
    if stale:
        raise RuntimeError(
            "CBB v1 scenario fixtures are stale; run "
            "generate_cbb_v1_scenario_assets.py --write: " + ", ".join(stale)
        )
    rows = _decision_report()
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "scenario_count": len(rows),
        "scenarios": rows,
        "scope_sensitive_reruns": _rerun_report(),
        "required_scenario_classes": [spec.scenario_class.value for spec in SCENARIO_SPECS],
        "claim_boundary": (
            "This verifies deterministic local scenario contracts and rerun sensitivity. "
            "It does not prove production delivery, legal or security certification, "
            "real affected-party consent, customer outcomes, or independent audit completion."
        ),
        "privacy": {
            "metadata_only": True,
            "raw_customer_payloads_included": False,
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
            "CBB v1 scenario report is stale. Run: "
            "python3 scripts/verify_cbb_v1_scenarios.py --write"
        )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
