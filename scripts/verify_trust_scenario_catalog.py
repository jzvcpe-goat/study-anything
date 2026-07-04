#!/usr/bin/env python3
"""Verify the metadata-only Trust Scenario Catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import dual_loop  # noqa: E402


REPORT = ROOT / "platform" / "generated" / "study-anything-trust-scenario-catalog.json"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-trust-scenario-catalog.html"
REGISTRY_REPORT = ROOT / "platform" / "generated" / "study-anything-delivery-class-registry.json"
RELEASE_CHECK = ROOT / "scripts" / "release_check.sh"

SCHEMA_VERSION = "trust-scenario-catalog-v1"
VERSION = "v0.3.31-alpha"

REQUIRED_LOOP_KEYS = (
    "agentic_coding_loop",
    "developer_feedback_loop",
    "external_feedback_loop",
)
REQUIRED_BASE_ARTIFACTS = {
    "failure-contract-v1",
    "sandbox-receipt-v1",
    "attention-reconstruction-summary-v1",
    "dual-loop-gate-receipt-v1",
}
REQUIRED_RECONSTRUCTION_CHECKPOINTS = {
    "failure_boundary_reconstruction",
    "risk_budget_reconstruction",
    "recipient_scope_reconstruction",
}

PRIVACY = {
    "metadata_only": True,
    "raw_source_text_included": False,
    "raw_report_text_included": False,
    "raw_review_text_included": False,
    "raw_customer_payload_included": False,
    "screenshots_included": False,
    "keystrokes_included": False,
    "mouse_coordinates_included": False,
    "eye_tracking_included": False,
    "biometrics_included": False,
    "real_secrets_included": False,
    "cookies_included": False,
    "bearer_tokens_included": False,
    "signed_urls_included": False,
    "model_calls_performed": False,
    "user_owned_agent_credentials_included": False,
    "production_mutation_performed": False,
    "external_publication_performed": False,
}

TRUST_SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": "controlled_code_review_handoff",
        "display_name": "Controlled Code Review Handoff",
        "disposition": "supported_controlled_handoff",
        "delivery_class_id": "code_review_handoff",
        "recipient_class": "maintainer_or_developer",
        "customer_visible": False,
        "autonomy_ceiling": "advisory_handoff_only",
        "decision": "allow_controlled_code_review_handoff",
        "required_artifacts": [
            "failure-contract-v1",
            "sandbox-receipt-v1",
            "attention-reconstruction-trace-v1",
            "attention-reconstruction-summary-v1",
            "dual-loop-gate-receipt-v1",
            "delivery-trust-case-v1",
            "code-review-handoff-case-v1",
        ],
        "active_reconstruction_checkpoints": [
            "failure_boundary_reconstruction",
            "risk_budget_reconstruction",
            "recipient_scope_reconstruction",
        ],
        "loop_requirements": {
            "agentic_coding_loop": "bounded sandbox evidence; no production mutation",
            "developer_feedback_loop": "developer reconstructs failure boundary and review scope",
            "external_feedback_loop": "recipient scope is bounded before handoff",
            "loop_dominance_allowed": False,
        },
        "forbidden_shortcuts": [
            "automatic_pr_comment",
            "merge_approval",
            "deployment_approval",
            "security_certification_claim",
            "ai_review_only_basis",
        ],
    },
    {
        "id": "controlled_client_report_handoff",
        "display_name": "Controlled Client Report Handoff",
        "disposition": "supported_controlled_handoff",
        "delivery_class_id": "client_report_handoff",
        "recipient_class": "bounded_client_or_internal_stakeholder",
        "customer_visible": True,
        "autonomy_ceiling": "controlled_customer_handoff_package",
        "decision": "allow_controlled_client_report_handoff",
        "required_artifacts": [
            "failure-contract-v1",
            "sandbox-receipt-v1",
            "attention-reconstruction-trace-v1",
            "attention-reconstruction-summary-v1",
            "dual-loop-gate-receipt-v1",
            "delivery-trust-case-v1",
            "customer-handoff-package-v1",
            "client-report-handoff-case-v1",
        ],
        "active_reconstruction_checkpoints": [
            "failure_boundary_reconstruction",
            "risk_budget_reconstruction",
            "recipient_scope_reconstruction",
            "claim_boundary_reconstruction",
        ],
        "loop_requirements": {
            "agentic_coding_loop": "sandbox evidence and rollback controls are present",
            "developer_feedback_loop": "operator reconstructs claim boundary and unsupported claims",
            "external_feedback_loop": "recipient and customer-visible scope are bounded",
            "loop_dominance_allowed": False,
        },
        "forbidden_shortcuts": [
            "automatic_customer_send",
            "external_publication",
            "legal_or_financial_certification",
            "raw_customer_payload",
            "ai_summary_only_basis",
        ],
    },
    {
        "id": "blocked_direct_production_mutation",
        "display_name": "Blocked Direct Production Mutation",
        "disposition": "blocked_unsafe_claim",
        "delivery_class_id": None,
        "recipient_class": "real_user_or_production_system",
        "customer_visible": True,
        "autonomy_ceiling": "blocked",
        "decision": "block_direct_production_mutation",
        "required_artifacts": [],
        "active_reconstruction_checkpoints": [
            "failure_boundary_reconstruction",
            "risk_budget_reconstruction",
        ],
        "loop_requirements": {
            "agentic_coding_loop": "sandbox may not mutate production",
            "developer_feedback_loop": "developer must define a reversible lower-risk scenario first",
            "external_feedback_loop": "external feedback cannot expand scope into production effects",
            "loop_dominance_allowed": False,
        },
        "required_remediation": [
            "define a reversible sandbox contract",
            "add rollback receipt evidence",
            "convert production action into a controlled handoff package",
        ],
        "forbidden_shortcuts": [
            "production_mutation",
            "irreversible_effect",
            "real_user_exposure",
        ],
    },
    {
        "id": "blocked_certified_truth_claim",
        "display_name": "Blocked Certified Truth Claim",
        "disposition": "blocked_unsafe_claim",
        "delivery_class_id": None,
        "recipient_class": "customer_or_regulated_recipient",
        "customer_visible": True,
        "autonomy_ceiling": "blocked",
        "decision": "block_certified_truth_claim",
        "required_artifacts": [],
        "active_reconstruction_checkpoints": [
            "claim_boundary_reconstruction",
            "recipient_scope_reconstruction",
        ],
        "loop_requirements": {
            "agentic_coding_loop": "deterministic receipts do not certify factual truth",
            "developer_feedback_loop": "developer must separate supported evidence from unsupported claims",
            "external_feedback_loop": "customer context may require domain-specific review outside v0.1",
            "loop_dominance_allowed": False,
        },
        "required_remediation": [
            "downgrade claim to controlled handoff evidence",
            "add domain-specific owner review outside this v0.1 protocol",
            "keep customer-facing language inside the claim boundary",
        ],
        "forbidden_shortcuts": [
            "legal_certification",
            "financial_certification",
            "truth_certification",
            "eval_sufficient_alone",
            "ai_review_only_basis",
        ],
    },
)


class TrustScenarioCatalogError(RuntimeError):
    """Readable Trust Scenario Catalog verification failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TrustScenarioCatalogError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TrustScenarioCatalogError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TrustScenarioCatalogError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def delivery_class_map() -> dict[str, Mapping[str, Any]]:
    registry = load_json(REGISTRY_REPORT)
    dual_loop.assert_metadata_only(registry, label="delivery-class-registry-ref")
    if registry.get("status") != "pass":
        raise TrustScenarioCatalogError("Delivery Class Registry must pass before catalog verification")
    classes = registry.get("delivery_classes")
    if not isinstance(classes, list):
        raise TrustScenarioCatalogError("Delivery Class Registry missing delivery_classes")
    mapped: dict[str, Mapping[str, Any]] = {}
    for entry in classes:
        if not isinstance(entry, Mapping) or not entry.get("id"):
            raise TrustScenarioCatalogError("Delivery Class Registry contains malformed entry")
        mapped[str(entry["id"])] = entry
    return mapped


def validate_loop_requirements(scenario_id: str, requirements: Any) -> None:
    if not isinstance(requirements, Mapping):
        raise TrustScenarioCatalogError(f"{scenario_id} missing loop_requirements")
    for key in REQUIRED_LOOP_KEYS:
        value = requirements.get(key)
        if not isinstance(value, str) or not value:
            raise TrustScenarioCatalogError(f"{scenario_id}.loop_requirements.{key} missing")
    if requirements.get("loop_dominance_allowed") is not False:
        raise TrustScenarioCatalogError(f"{scenario_id} must reject loop dominance")


def validate_supported_scenario(
    scenario: Mapping[str, Any],
    delivery_classes: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    scenario_id = str(scenario["id"])
    delivery_class_id = scenario.get("delivery_class_id")
    if not isinstance(delivery_class_id, str) or delivery_class_id not in delivery_classes:
        raise TrustScenarioCatalogError(f"{scenario_id} references unsupported delivery class")
    delivery_class = delivery_classes[delivery_class_id]
    if scenario.get("decision") not in {
        delivery_class.get("allowed_decision"),
        "allow_controlled_code_review_handoff",
        "allow_controlled_client_report_handoff",
    }:
        raise TrustScenarioCatalogError(f"{scenario_id} decision is not aligned with its delivery class")

    artifacts = scenario.get("required_artifacts")
    if not isinstance(artifacts, list):
        raise TrustScenarioCatalogError(f"{scenario_id} missing required_artifacts")
    missing = sorted(REQUIRED_BASE_ARTIFACTS - set(artifacts))
    if missing:
        raise TrustScenarioCatalogError(f"{scenario_id} missing base Dual Loop artifacts: {missing}")
    if scenario.get("customer_visible") is True and "customer-handoff-package-v1" not in artifacts:
        raise TrustScenarioCatalogError(f"{scenario_id} customer-visible scenario needs CustomerHandoffPackage")
    if scenario.get("autonomy_ceiling") in {"production_mutation", "external_publication"}:
        raise TrustScenarioCatalogError(f"{scenario_id} autonomy ceiling is too high")

    checkpoints = scenario.get("active_reconstruction_checkpoints")
    if not isinstance(checkpoints, list):
        raise TrustScenarioCatalogError(f"{scenario_id} missing active reconstruction checkpoints")
    missing_checkpoints = sorted(REQUIRED_RECONSTRUCTION_CHECKPOINTS - set(checkpoints))
    if missing_checkpoints:
        raise TrustScenarioCatalogError(
            f"{scenario_id} missing reconstruction checkpoints: {missing_checkpoints}"
        )

    return {
        "id": scenario_id,
        "display_name": scenario["display_name"],
        "disposition": scenario["disposition"],
        "delivery_class_id": delivery_class_id,
        "delivery_class_report": delivery_class["assets"]["report"]["path"],
        "verifier_command": delivery_class["verifier_command"],
        "recipient_class": scenario["recipient_class"],
        "customer_visible": scenario["customer_visible"],
        "autonomy_ceiling": scenario["autonomy_ceiling"],
        "decision": scenario["decision"],
        "required_artifacts": artifacts,
        "active_reconstruction_checkpoints": checkpoints,
        "loop_requirements": scenario["loop_requirements"],
        "forbidden_shortcuts": scenario["forbidden_shortcuts"],
    }


def validate_blocked_scenario(scenario: Mapping[str, Any]) -> dict[str, Any]:
    scenario_id = str(scenario["id"])
    if scenario.get("delivery_class_id") is not None:
        raise TrustScenarioCatalogError(f"{scenario_id} blocked scenario cannot map to a delivery class")
    if not str(scenario.get("decision", "")).startswith("block_"):
        raise TrustScenarioCatalogError(f"{scenario_id} blocked scenario decision must start with block_")
    remediation = scenario.get("required_remediation")
    if not isinstance(remediation, list) or not remediation:
        raise TrustScenarioCatalogError(f"{scenario_id} blocked scenario needs remediation guidance")
    if scenario.get("autonomy_ceiling") != "blocked":
        raise TrustScenarioCatalogError(f"{scenario_id} blocked scenario must have blocked ceiling")
    return {
        "id": scenario_id,
        "display_name": scenario["display_name"],
        "disposition": scenario["disposition"],
        "delivery_class_id": None,
        "recipient_class": scenario["recipient_class"],
        "customer_visible": scenario["customer_visible"],
        "autonomy_ceiling": scenario["autonomy_ceiling"],
        "decision": scenario["decision"],
        "required_remediation": remediation,
        "active_reconstruction_checkpoints": scenario["active_reconstruction_checkpoints"],
        "loop_requirements": scenario["loop_requirements"],
        "forbidden_shortcuts": scenario["forbidden_shortcuts"],
    }


def validate_scenario(
    scenario: Mapping[str, Any],
    delivery_classes: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    scenario_id = str(scenario.get("id", ""))
    if not scenario_id:
        raise TrustScenarioCatalogError("Scenario missing id")
    if not scenario.get("display_name"):
        raise TrustScenarioCatalogError(f"{scenario_id} missing display_name")
    validate_loop_requirements(scenario_id, scenario.get("loop_requirements"))
    dual_loop.assert_metadata_only(scenario, label=f"trust-scenario:{scenario_id}")
    disposition = scenario.get("disposition")
    if disposition == "supported_controlled_handoff":
        return validate_supported_scenario(scenario, delivery_classes)
    if disposition == "blocked_unsafe_claim":
        return validate_blocked_scenario(scenario)
    raise TrustScenarioCatalogError(f"{scenario_id} has unknown disposition: {disposition}")


def build_report() -> dict[str, Any]:
    release_check_text = RELEASE_CHECK.read_text(encoding="utf-8")
    if "scripts/verify_trust_scenario_catalog.py --check" not in release_check_text:
        raise TrustScenarioCatalogError("Trust Scenario Catalog verifier is not wired into release_check.sh")

    delivery_classes = delivery_class_map()
    seen: set[str] = set()
    scenarios: list[dict[str, Any]] = []
    for scenario in TRUST_SCENARIOS:
        scenario_id = str(scenario["id"])
        if scenario_id in seen:
            raise TrustScenarioCatalogError(f"Duplicate scenario id: {scenario_id}")
        seen.add(scenario_id)
        scenarios.append(validate_scenario(scenario, delivery_classes))

    supported = [row for row in scenarios if row["disposition"] == "supported_controlled_handoff"]
    blocked = [row for row in scenarios if row["disposition"] == "blocked_unsafe_claim"]
    if len(supported) < 2 or len(blocked) < 2:
        raise TrustScenarioCatalogError("Catalog must include at least two supported and two blocked scenarios")

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": VERSION,
        "scenario_count": len(scenarios),
        "supported_scenario_count": len(supported),
        "blocked_scenario_count": len(blocked),
        "delivery_class_registry_ref": {
            "path": REGISTRY_REPORT.relative_to(ROOT).as_posix(),
            "sha256": dual_loop.sha256_text(REGISTRY_REPORT.read_text(encoding="utf-8")),
            "registered_delivery_class_ids": sorted(delivery_classes),
        },
        "catalog_rule": {
            "both_loops_required": True,
            "active_reconstruction_is_strong_evidence": True,
            "passive_attention_is_insufficient": True,
            "sandbox_pass_alone_is_insufficient": True,
            "human_reconstruction_alone_is_insufficient": True,
            "ai_review_only_basis_rejected": True,
            "production_mutation_allowed": False,
        },
        "scenarios": scenarios,
        "claim_boundary": {
            "current_claim": (
                "The catalog shows which delivery scenarios can currently be mapped to "
                "metadata-only Dual Loop / Delivery Trust evidence and which shortcuts "
                "must be blocked. It does not prove customer adoption, production "
                "permission, legal certification, or general factual correctness."
            ),
            "not_claimed": [
                "automatic production delivery",
                "automatic customer sending",
                "legal or financial certification",
                "truth certification",
                "replacement for customer-specific review",
                "model quality proof",
            ],
        },
        "privacy": dict(PRIVACY),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_trust_scenario_catalog.py --check",
            "catalog_report": REPORT.relative_to(ROOT).as_posix(),
            "registry_report": REGISTRY_REPORT.relative_to(ROOT).as_posix(),
        },
    }
    dual_loop.assert_metadata_only(report, label=SCHEMA_VERSION)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    try:
        report = build_report()
    except TrustScenarioCatalogError as exc:
        raise SystemExit(str(exc)) from exc

    serialized = dual_loop.dump_json(report)
    html = dual_loop.render_html_report("Trust Scenario Catalog", report)

    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")

    if args.check:
        if not REPORT.is_file():
            raise SystemExit(f"Trust Scenario Catalog report is missing: {REPORT.relative_to(ROOT)}")
        if REPORT.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Trust Scenario Catalog report is out of date. "
                "Run: python3 scripts/verify_trust_scenario_catalog.py --write"
            )
        if not HTML_REPORT.is_file():
            raise SystemExit(f"Trust Scenario Catalog HTML report is missing: {HTML_REPORT.relative_to(ROOT)}")
        if HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Trust Scenario Catalog HTML report is out of date. "
                "Run: python3 scripts/verify_trust_scenario_catalog.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
