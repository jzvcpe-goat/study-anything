#!/usr/bin/env python3
"""Evaluate a metadata-only Trust Scenario Catalog decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import dual_loop  # noqa: E402


CATALOG = ROOT / "platform" / "generated" / "study-anything-trust-scenario-catalog.json"
SCHEMA_VERSION = "trust-scenario-decision-v1"
VERSION = "v0.3.31-alpha"

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


class TrustScenarioDecisionError(RuntimeError):
    """Readable Trust Scenario Decision Gate failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TrustScenarioDecisionError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TrustScenarioDecisionError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise TrustScenarioDecisionError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def scenario_map(catalog: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if catalog.get("schema_version") != "trust-scenario-catalog-v1" or catalog.get("status") != "pass":
        raise TrustScenarioDecisionError("Trust Scenario Catalog must be current and passing")
    dual_loop.assert_metadata_only(catalog, label="trust-scenario-decision-catalog")
    rows = catalog.get("scenarios")
    if not isinstance(rows, list):
        raise TrustScenarioDecisionError("Trust Scenario Catalog missing scenarios")
    mapped: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or not row.get("id"):
            raise TrustScenarioDecisionError("Trust Scenario Catalog contains malformed scenario")
        mapped[str(row["id"])] = row
    return mapped


def evaluate(
    *,
    catalog: Mapping[str, Any],
    scenario_id: str,
    provided_artifacts: list[str],
    active_checkpoints: list[str],
    requested_shortcuts: list[str],
) -> dict[str, Any]:
    scenarios = scenario_map(catalog)
    if scenario_id not in scenarios:
        raise TrustScenarioDecisionError(f"Unknown trust scenario: {scenario_id}")
    scenario = scenarios[scenario_id]
    dual_loop.assert_metadata_only(scenario, label=f"trust-scenario-decision:{scenario_id}")

    required_artifacts = [str(item) for item in scenario.get("required_artifacts", [])]
    required_checkpoints = [str(item) for item in scenario.get("active_reconstruction_checkpoints", [])]
    forbidden_shortcuts = [str(item) for item in scenario.get("forbidden_shortcuts", [])]
    missing_artifacts = sorted(set(required_artifacts) - set(provided_artifacts))
    missing_checkpoints = sorted(set(required_checkpoints) - set(active_checkpoints))
    blocked_shortcuts = sorted(set(requested_shortcuts) & set(forbidden_shortcuts))

    reasons: list[str] = []
    if scenario.get("disposition") != "supported_controlled_handoff":
        reasons.append("scenario_not_supported")
    if missing_artifacts:
        reasons.append("required_artifacts_missing")
    if missing_checkpoints:
        reasons.append("active_reconstruction_missing")
    if blocked_shortcuts:
        reasons.append("forbidden_shortcut_requested")
    if scenario.get("autonomy_ceiling") in {"blocked", "production_mutation", "external_publication"}:
        reasons.append("autonomy_ceiling_blocks_handoff")

    allowed = not reasons
    catalog_decision = str(scenario.get("decision", ""))
    decision = catalog_decision if allowed or catalog_decision.startswith("block_") else f"block_{scenario_id}"
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": "allowed" if allowed else "blocked",
        "version": VERSION,
        "scenario_id": scenario_id,
        "scenario_disposition": scenario.get("disposition"),
        "recipient_class": scenario.get("recipient_class"),
        "customer_visible": scenario.get("customer_visible"),
        "autonomy_ceiling": scenario.get("autonomy_ceiling"),
        "decision": decision,
        "reasons": reasons,
        "required_artifacts": required_artifacts,
        "provided_artifacts": sorted(provided_artifacts),
        "missing_artifacts": missing_artifacts,
        "required_active_reconstruction_checkpoints": required_checkpoints,
        "provided_active_reconstruction_checkpoints": sorted(active_checkpoints),
        "missing_active_reconstruction_checkpoints": missing_checkpoints,
        "requested_shortcuts": sorted(requested_shortcuts),
        "blocked_shortcuts": blocked_shortcuts,
        "loop_gate": {
            "both_loops_required": True,
            "sandbox_pass_alone_is_insufficient": True,
            "human_reconstruction_alone_is_insufficient": True,
            "passive_attention_is_insufficient": True,
            "loop_dominance_allowed": False,
        },
        "catalog_ref": {
            "path": CATALOG.relative_to(ROOT).as_posix(),
            "sha256": dual_loop.sha256_text(dual_loop.dump_json(dict(catalog))),
            "scenario_count": catalog.get("scenario_count"),
        },
        "claim_boundary": {
            "current_claim": (
                "This receipt records a metadata-only scenario handoff decision. "
                "It does not certify factual truth, approve production mutation, "
                "send customer messages, or replace customer-specific review."
            ),
            "not_claimed": [
                "production approval",
                "automatic customer sending",
                "external publication",
                "truth certification",
                "model quality proof",
            ],
        },
        "privacy": dict(PRIVACY),
    }
    dual_loop.assert_metadata_only(receipt, label=SCHEMA_VERSION)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluate", nargs="?")
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--scenario-id", required=True)
    parser.add_argument("--provided-artifact", action="append", default=[])
    parser.add_argument("--active-checkpoint", action="append", default=[])
    parser.add_argument("--requested-shortcut", action="append", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--html-output", type=Path)
    args = parser.parse_args()

    if args.evaluate not in {None, "evaluate"}:
        raise SystemExit("Only the `evaluate` command is supported.")

    catalog = load_json(args.catalog)
    receipt = evaluate(
        catalog=catalog,
        scenario_id=args.scenario_id,
        provided_artifacts=[str(item) for item in args.provided_artifact],
        active_checkpoints=[str(item) for item in args.active_checkpoint],
        requested_shortcuts=[str(item) for item in args.requested_shortcut],
    )
    text = dual_loop.dump_json(receipt)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    if args.html_output:
        args.html_output.parent.mkdir(parents=True, exist_ok=True)
        args.html_output.write_text(
            dual_loop.render_html_report("Trust Scenario Decision Gate", receipt),
            encoding="utf-8",
        )
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
