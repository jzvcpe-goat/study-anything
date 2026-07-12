#!/usr/bin/env python3
"""Verify Plugin Evidence Adapter v0.1 contracts and fail-closed boundaries."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import Any

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.plugin_evidence.evaluator import (  # noqa: E402
    evaluate_plugin_evidence,
)
from study_anything.cbb.plugin_evidence.fixtures import (  # noqa: E402
    EVALUATED_AT,
    fixture_bundles,
    fixture_payloads,
)
from study_anything.cbb.plugin_evidence.models import (  # noqa: E402
    PLUGIN_EVIDENCE_MODELS,
    PluginEvidenceBundleV1,
)
from study_anything.cbb.protocol.canonical import (  # noqa: E402
    CanonicalProtocolError,
    assert_safe_metadata,
    pretty_json,
    schema_text,
)
from study_anything.cbb.protocol.models import DeliveryScope  # noqa: E402


SCHEMA_ROOT = Path("platform/schemas/cbb")
FIXTURE_ROOT = Path("fixtures/plugin-evidence")
REPORT_PATH = Path("platform/generated/delivery-clearance-plugin-evidence-adapter-v0.1.json")

EXPECTED_STATUSES = {
    "pass-local-read": "allow_personal_local",
    "pass-bound-external-read": "allow_personal_local",
    "pass-bound-local-write": "allow_personal_local",
    "needs-manifest-only": "needs_evidence",
    "needs-unbound-input": "needs_evidence",
    "needs-native-verification": "needs_evidence",
    "needs-domain-evidence": "needs_evidence",
    "needs-fresh-external-input": "needs_evidence",
    "block-external-write": "block",
    "block-external-mutation": "block",
    "block-runtime-failure": "block",
    "block-credential-use": "block",
}


def _rejects(action: Any, expected: str) -> bool:
    try:
        action()
    except (CanonicalProtocolError, ValidationError, ValueError) as exc:
        return expected in str(exc)
    return False


def build_report() -> dict[str, Any]:
    bundles = fixture_bundles()
    decisions = {
        name: evaluate_plugin_evidence(bundle, evaluated_at=EVALUATED_AT)
        for name, bundle in bundles.items()
    }
    cases: dict[str, bool] = {
        "fixture_statuses_match": all(
            decisions[name].status == expected for name, expected in EXPECTED_STATUSES.items()
        ),
        "allowed_cases_stop_at_personal_local": all(
            decision.approved_scope == DeliveryScope.PERSONAL_LOCAL
            for decision in decisions.values()
            if decision.status == "allow_personal_local"
        ),
        "non_allowed_cases_grant_no_scope": all(
            decision.approved_scope == DeliveryScope.BLOCKED
            for decision in decisions.values()
            if decision.status != "allow_personal_local"
        ),
        "manifest_only_is_not_runtime_evidence": (
            decisions["needs-manifest-only"].status == "needs_evidence"
            and not decisions["needs-manifest-only"].manifest_or_install_state_sufficient
            and "runtime_execution" in decisions["needs-manifest-only"].missing_evidence
        ),
        "external_write_capability_hard_blocks": (
            "hard_deny:external_write_capability" in decisions["block-external-write"].reasons
        ),
        "observed_external_mutation_hard_blocks": (
            "hard_deny:external_mutation_observed" in decisions["block-external-mutation"].reasons
        ),
        "credentials_hard_block": (
            "hard_deny:credentials_used" in decisions["block-credential-use"].reasons
        ),
        "bound_external_read_can_support_personal_use": (
            decisions["pass-bound-external-read"].status == "allow_personal_local"
            and not decisions["pass-bound-external-read"].external_action_authorized
        ),
        "bound_local_write_can_support_resulting_git_state": (
            decisions["pass-bound-local-write"].status == "allow_personal_local"
        ),
        "interactive_ui_requires_native_verification": (
            "native_verification" in decisions["needs-native-verification"].missing_evidence
        ),
        "professional_judgment_requires_domain_evidence": (
            "domain_evidence_and_qualified_reconstruction"
            in decisions["needs-domain-evidence"].missing_evidence
        ),
        "mutable_external_input_expires": (
            "external_input_freshness" in decisions["needs-fresh-external-input"].missing_evidence
        ),
        "runtime_failure_is_not_relabelled_as_missing": (
            decisions["block-runtime-failure"].status == "block"
            and "hard_deny:runtime_failed" in decisions["block-runtime-failure"].reasons
        ),
        "all_decisions_disclaim_customer_and_production_authority": all(
            not decision.customer_delivery_authorized and not decision.production_authorized
            for decision in decisions.values()
        ),
    }

    expanded_scope = deepcopy(fixture_payloads()["pass-local-read"])
    expanded_scope["requested_scope"] = "controlled_customer_handoff"
    cases["scope_expansion_is_schema_rejected"] = _rejects(
        lambda: PluginEvidenceBundleV1.model_validate(expanded_scope),
        "personal_local",
    )

    secret_like = deepcopy(fixture_payloads()["pass-local-read"])
    secret_like["plugin"]["plugin_version"] = "sk-" + ("x" * 24)
    cases["secret_like_metadata_is_rejected"] = _rejects(
        lambda: assert_safe_metadata(secret_like, label="plugin fixture"),
        "secret-like",
    )

    local_path = deepcopy(fixture_payloads()["pass-local-read"])
    local_path["plugin"]["plugin_version"] = "/Users/example/private/plugin"
    cases["local_absolute_paths_are_rejected"] = _rejects(
        lambda: assert_safe_metadata(local_path, label="plugin fixture"),
        "secret-like",
    )

    cli_help = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "plugin_evidence_adapter.py"), "--help"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    cases["cli_help_succeeds"] = cli_help.returncode == 0 and "personal-local" in cli_help.stdout
    project_metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    cases["installed_cli_entrypoint_declared"] = (
        project_metadata.get("project", {})
        .get("scripts", {})
        .get("delivery-clearance-plugin-evidence")
        == "study_anything.cbb.plugin_evidence.cli:main"
    )

    failed = sorted(name for name, passed in cases.items() if not passed)
    if failed:
        raise RuntimeError(f"plugin evidence verifier cases failed: {failed}")

    return {
        "schema_version": "plugin-evidence-adapter-verification-v1",
        "status": "pass",
        "case_results": cases,
        "fixture_decisions": {
            name: {
                "status": decision.status,
                "approved_scope": decision.approved_scope.value,
                "reasons": decision.reasons,
                "missing_evidence": decision.missing_evidence,
            }
            for name, decision in sorted(decisions.items())
        },
        "maximum_allowed_scope": "personal_local",
        "claim_boundary": (
            "Plugin Evidence Adapter v0.1 does not run or approve plugins. It converts "
            "bounded runtime, input, effect, native-verification, and domain evidence into "
            "supporting evidence for one personal-local candidate only."
        ),
        "privacy": {
            "metadata_only": True,
            "plugin_source_included": False,
            "raw_check_output_included": False,
            "external_input_content_included": False,
            "local_absolute_paths_included": False,
            "model_calls_performed": False,
            "plugin_execution_performed_by_verifier": False,
            "external_actions_performed": False,
        },
    }


def expected_outputs() -> dict[Path, str]:
    outputs = {
        ROOT / SCHEMA_ROOT / f"{schema_version}.schema.json": schema_text(model_type)
        for schema_version, model_type in PLUGIN_EVIDENCE_MODELS.items()
    }
    for name, payload in fixture_payloads().items():
        outputs[ROOT / FIXTURE_ROOT / f"{name}.json"] = pretty_json(payload)
    outputs[ROOT / REPORT_PATH] = (
        json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check == args.write:
        raise SystemExit("Choose exactly one of --check or --write.")

    outputs = expected_outputs()
    if args.write:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    else:
        stale = [
            path.relative_to(ROOT).as_posix()
            for path, expected in outputs.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != expected
        ]
        if stale:
            raise SystemExit(
                "Plugin Evidence Adapter artifacts are stale. Run: "
                "python3 scripts/verify_plugin_evidence_adapter.py --write\n" + "\n".join(stale)
            )
    print(json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
