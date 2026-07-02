#!/usr/bin/env python3
"""Verify the release-stack recursion guard and product runway reset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from verify_release_stack_readiness import MANIFEST, ROOT, load_json, verify_manifest


POLICY_PATH = ROOT / ".cognitive-loop" / "release-stack-policy.yaml"
POLICY_DOC = ROOT / "docs" / "release-stack-policy.md"
RUNWAY_DOC = ROOT / "docs" / "product-runway.md"
EVALS_PATH = ROOT / ".cognitive-loop" / "evals.yaml"
RELEASE_CHECK = ROOT / "scripts" / "release_check.sh"
BUNDLE_GENERATOR = ROOT / "scripts" / "generate_platform_bundle_manifest.py"
ADOPTION_GENERATOR = ROOT / "scripts" / "generate_platform_adoption_pack.py"
REPORT_PATH = ROOT / "platform" / "generated" / "study-anything-release-stack-policy.json"

POLICY_SCHEMA_VERSION = "release-stack-recursion-policy-v1"
REPORT_SCHEMA_VERSION = "release-stack-policy-verification-v1"
REQUIRED_SELF_INTAKE_TRIGGERS = {
    "release_policy_changed",
    "release_stack_verifier_changed",
    "public_evidence_chain_changed",
    "current_group_changed",
}
REQUIRED_NOT_REQUIRED_TRIGGERS = {
    "self_intake_only_pr",
    "generated_hash_refresh_only",
    "ordinary_maintenance_pr",
    "docs_copy_only_without_policy_change",
}
FALSE_PRIVACY_FLAGS = [
    "github_tokens_included",
    "job_logs_included",
    "check_annotations_included",
    "live_check_payloads_included",
    "raw_source_text_included",
    "learner_answers_included",
    "agent_endpoint_secrets_included",
    "real_model_keys_included",
    "production_mutation_allowed_by_default",
]


class ReleaseStackPolicyError(RuntimeError):
    """Readable release-stack policy verification failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseStackPolicyError(message)


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json_subset_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ReleaseStackPolicyError(f"missing policy contract: {path.relative_to(ROOT)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReleaseStackPolicyError(
            f"{path.relative_to(ROOT)} must remain JSON-subset YAML so no PyYAML dependency is required: {exc}"
        ) from exc
    require(isinstance(payload, dict), "policy contract must be an object")
    return payload


def require_string_list(payload: Mapping[str, Any], key: str) -> list[str]:
    value = payload.get(key)
    require(isinstance(value, list) and value, f"{key} must be a non-empty list")
    require(all(isinstance(item, str) and item for item in value), f"{key} must contain strings")
    return list(value)


def validate_policy(payload: Mapping[str, Any]) -> dict[str, Any]:
    require(payload.get("schema_version") == POLICY_SCHEMA_VERSION, "policy schema_version drifted")
    recursion = payload.get("recursion_guard")
    require(isinstance(recursion, Mapping), "recursion_guard missing")
    require(recursion.get("default_self_intake_for_every_merged_pr") is False, "default self-intake must be disabled")
    require(recursion.get("self_intake_pr_requires_next_self_intake") is False, "self-intake PRs must not force another self-intake")
    require(recursion.get("self_intake_only_pr_is_terminal_by_default") is True, "self-intake-only PRs must be terminal by default")
    require(recursion.get("last_self_intake_pr_without_forced_followup") == 282, "PR #282 boundary must be explicit")
    require(recursion.get("next_forced_self_intake_pr") is None, "there must be no forced #283 self-intake")
    require(recursion.get("batch_archive_allowed") is True, "batch archive path must be allowed")
    require(recursion.get("product_runway_redirect_allowed") is True, "product runway redirect must be allowed")

    required = set(require_string_list(payload, "self_intake_required_when"))
    not_required = set(require_string_list(payload, "self_intake_not_required_when"))
    batch = set(require_string_list(payload, "batch_archive_when"))
    require(REQUIRED_SELF_INTAKE_TRIGGERS <= required, "substantive self-intake triggers are incomplete")
    require(REQUIRED_NOT_REQUIRED_TRIGGERS <= not_required, "non-self-intake triggers are incomplete")
    require({"self_intake_only_pr", "generated_hash_refresh_only"} <= batch, "batch archive policy must cover recursion and hash-only work")

    runway = payload.get("product_runway")
    require(isinstance(runway, Mapping), "product_runway missing")
    require(runway.get("default_next_destination") == "dual_loop_trust_protocol", "default runway must be Dual Loop trust protocol")
    require(runway.get("next_harness") == "dual_loop_trust_scenario_harness", "next harness must be the Dual Loop trust scenario harness")
    require(runway.get("standalone_frontend_default") is False, "standalone frontend must not be the default runway")
    require(runway.get("release_stack_recursion_default") is False, "release-stack recursion must not be default")

    privacy = payload.get("privacy")
    require(isinstance(privacy, Mapping), "privacy missing")
    require(privacy.get("metadata_only") is True, "policy evidence must be metadata-only")
    for key in FALSE_PRIVACY_FLAGS:
        require(privacy.get(key) is False, f"privacy.{key} must be false")

    return {
        "recursion_guard": dict(recursion),
        "self_intake_required_when": sorted(required),
        "self_intake_not_required_when": sorted(not_required),
        "batch_archive_when": sorted(batch),
        "product_runway": dict(runway),
        "privacy": dict(privacy),
    }


def validate_doc(path: Path, markers: list[str]) -> dict[str, Any]:
    require(path.is_file(), f"missing doc: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    require(not missing, f"{path.relative_to(ROOT)} missing markers: {missing}")
    return {"path": str(path.relative_to(ROOT)), "required_markers_present": True}


def validate_integration() -> dict[str, bool]:
    checks = {
        "evals": "python3 scripts/verify_release_stack_policy.py --check" in EVALS_PATH.read_text(encoding="utf-8"),
        "release_check": "scripts/verify_release_stack_policy.py --check" in RELEASE_CHECK.read_text(encoding="utf-8"),
        "bundle_policy_doc": "docs/release-stack-policy.md" in BUNDLE_GENERATOR.read_text(encoding="utf-8"),
        "bundle_runway_doc": "docs/product-runway.md" in BUNDLE_GENERATOR.read_text(encoding="utf-8"),
        "bundle_policy_contract": ".cognitive-loop/release-stack-policy.yaml" in BUNDLE_GENERATOR.read_text(encoding="utf-8"),
        "bundle_policy_report": "platform/generated/study-anything-release-stack-policy.json" in BUNDLE_GENERATOR.read_text(encoding="utf-8"),
        "bundle_policy_verifier": "scripts/verify_release_stack_policy.py" in BUNDLE_GENERATOR.read_text(encoding="utf-8"),
        "adoption_policy_doc": "docs/release-stack-policy.md" in ADOPTION_GENERATOR.read_text(encoding="utf-8"),
        "adoption_runway_doc": "docs/product-runway.md" in ADOPTION_GENERATOR.read_text(encoding="utf-8"),
        "adoption_policy_contract": ".cognitive-loop/release-stack-policy.yaml" in ADOPTION_GENERATOR.read_text(encoding="utf-8"),
        "adoption_policy_report": "platform/generated/study-anything-release-stack-policy.json" in ADOPTION_GENERATOR.read_text(encoding="utf-8"),
        "adoption_policy_verifier": "scripts/verify_release_stack_policy.py" in ADOPTION_GENERATOR.read_text(encoding="utf-8"),
    }
    missing = [key for key, ok in checks.items() if not ok]
    require(not missing, f"release-stack policy integration missing: {missing}")
    return checks


def validate_release_stack_state() -> dict[str, Any]:
    manifest = load_json(MANIFEST)
    readiness = verify_manifest(manifest)
    current_stack = manifest.get("stack")
    require(isinstance(current_stack, list) and current_stack, "release-stack top-level stack must be non-empty")
    current_prs = [row.get("pr") for row in current_stack if isinstance(row, Mapping)]
    require(282 not in current_prs, "PR #282 must not be auto-promoted into the current release stack")
    require(not (ROOT / "fixtures" / "release-stack" / "pr-282-intake-candidate.json").exists(), "PR #282 fixture must not exist")
    require(not (ROOT / "fixtures" / "release-stack" / "pr-283-intake-candidate.json").exists(), "PR #283 forced self-intake fixture must not exist")
    return {
        "current_group": readiness["current_group"],
        "current_group_status": readiness["current_group_status"],
        "stack_prs": readiness["stack_prs"],
        "pr_282_auto_promoted": False,
        "pr_282_fixture_exists": False,
        "forced_pr_283_fixture_exists": False,
    }


def build_report() -> dict[str, Any]:
    payload = load_json_subset_yaml(POLICY_PATH)
    policy = validate_policy(payload)
    policy_doc = validate_doc(
        POLICY_DOC,
        [
            "Do not self-intake every merged PR by default",
            "PR #282 is the terminal self-intake recursion boundary",
            "batch archive",
            "product runway",
            "python3 scripts/verify_release_stack_policy.py --check",
        ],
    )
    runway_doc = validate_doc(
        RUNWAY_DOC,
        [
            "Dual Loop Trust Scenario Harness",
            "controlled failure environment",
            "attention reconstruction",
            "delivery trust receipt",
            "Do not restart standalone frontend work as the default path",
        ],
    )
    integration = validate_integration()
    release_stack = validate_release_stack_state()
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "source_contract": ".cognitive-loop/release-stack-policy.yaml",
        "docs": {
            "release_stack_policy": policy_doc,
            "product_runway": runway_doc,
        },
        "policy": {
            "recursion_guard": policy["recursion_guard"],
            "self_intake_required_when": policy["self_intake_required_when"],
            "self_intake_not_required_when": policy["self_intake_not_required_when"],
            "batch_archive_when": policy["batch_archive_when"],
            "product_runway": policy["product_runway"],
        },
        "release_stack": release_stack,
        "integration": integration,
        "privacy": policy["privacy"],
        "claim_boundary": (
            "This proves the release-stack recursion guard, product-runway reset, "
            "and metadata-only integration are present. It does not prove a full clean-clone release check."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    output = Path(args.output)
    report = build_report()
    serialized = dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Release-stack policy report is missing: {output.relative_to(ROOT)}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Release-stack policy report is out of date. "
                "Run: python3 scripts/verify_release_stack_policy.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"verify_release_stack_policy failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
