"""Deterministic plugin-evidence fixtures for boundary verification."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from study_anything.cbb.plugin_evidence.models import PluginEvidenceBundleV1


OBSERVED_AT = "2026-07-11T12:00:00Z"
EVALUATED_AT = "2026-07-11T12:30:00Z"
VALID_UNTIL = "2026-07-12T12:00:00Z"


def _privacy() -> dict[str, Any]:
    return {
        "protocol_boundary": {
            "metadata_only": True,
            "raw_source_text_included": False,
            "raw_report_text_included": False,
            "raw_customer_payload_included": False,
            "attention_stream_included": False,
            "model_prompts_included": False,
            "model_credentials_included": False,
            "cookies_or_bearer_tokens_included": False,
            "signed_urls_included": False,
            "production_mutation_performed": False,
            "automatic_customer_send_performed": False,
        },
        "plugin_source_included": False,
        "raw_check_output_included": False,
        "external_input_content_included": False,
        "local_absolute_paths_included": False,
    }


def _base_payload() -> dict[str, Any]:
    return {
        "schema_version": "delivery-clearance.plugin-evidence.v1",
        "evidence_id": "plugin-evidence:readonly-local",
        "requested_scope": "personal_local",
        "plugin": {
            "plugin_id": "example-readonly",
            "plugin_version": "0.1.0",
            "package_digest_sha256": "a" * 64,
            "manifest_digest_sha256": "b" * 64,
        },
        "capabilities": ["local_read"],
        "runtime": {
            "status": "ready",
            "dependency_check": "passed",
            "execution_digest_sha256": "c" * 64,
            "observed_at": OBSERVED_AT,
        },
        "inputs": [
            {
                "input_id": "input:git-snapshot",
                "source_class": "git_bound",
                "content_digest_sha256": "d" * 64,
                "observed_at": OBSERVED_AT,
                "valid_until": None,
            }
        ],
        "effects": {
            "project_git_mutation_observed": False,
            "project_mutation_bound_to_subject_digest": False,
            "post_run_subject_digest_sha256": None,
            "network_access_observed": False,
            "external_mutation_observed": False,
            "credentials_used": False,
        },
        "checks": [
            {
                "check_id": "check:native-plugin-suite",
                "status": "passed",
                "required": True,
                "result_digest_sha256": "e" * 64,
                "observed_at": OBSERVED_AT,
            }
        ],
        "native_verification": {
            "status": "not_applicable",
            "verifier_kind": None,
            "verification_digest_sha256": None,
            "observed_at": None,
        },
        "domain_evidence": {
            "status": "not_applicable",
            "domain_profile_ref": None,
            "domain_profile_digest_sha256": None,
            "evaluator_digest_sha256": None,
            "qualified_reconstruction": "not_applicable",
        },
        "observed_at": OBSERVED_AT,
        "valid_until": VALID_UNTIL,
        "privacy": _privacy(),
    }


def fixture_payloads() -> dict[str, dict[str, Any]]:
    fixtures: dict[str, dict[str, Any]] = {}

    fixtures["pass-local-read"] = _base_payload()

    external_read = deepcopy(_base_payload())
    external_read["evidence_id"] = "plugin-evidence:bound-external-read"
    external_read["plugin"]["plugin_id"] = "example-external-reader"
    external_read["capabilities"] = ["local_read", "external_read"]
    external_read["inputs"] = [
        {
            "input_id": "input:external-snapshot",
            "source_class": "external_mutable",
            "content_digest_sha256": "f" * 64,
            "observed_at": OBSERVED_AT,
            "valid_until": "2026-07-11T18:00:00Z",
        }
    ]
    external_read["effects"]["network_access_observed"] = True
    fixtures["pass-bound-external-read"] = external_read

    local_write = deepcopy(_base_payload())
    local_write["evidence_id"] = "plugin-evidence:bound-local-write"
    local_write["plugin"]["plugin_id"] = "example-local-writer"
    local_write["capabilities"] = ["local_read", "local_write"]
    local_write["effects"].update(
        {
            "project_git_mutation_observed": True,
            "project_mutation_bound_to_subject_digest": True,
            "post_run_subject_digest_sha256": "1" * 64,
        }
    )
    fixtures["pass-bound-local-write"] = local_write

    manifest_only = deepcopy(_base_payload())
    manifest_only["evidence_id"] = "plugin-evidence:manifest-only"
    manifest_only["plugin"]["package_digest_sha256"] = None
    manifest_only["runtime"] = {
        "status": "not_run",
        "dependency_check": "missing",
        "execution_digest_sha256": None,
        "observed_at": None,
    }
    manifest_only["inputs"][0].update(
        {
            "source_class": "local_unbound",
            "content_digest_sha256": None,
        }
    )
    manifest_only["checks"][0] = {
        "check_id": "check:native-plugin-suite",
        "status": "not_run",
        "required": True,
        "result_digest_sha256": None,
        "observed_at": None,
    }
    fixtures["needs-manifest-only"] = manifest_only

    unbound_input = deepcopy(_base_payload())
    unbound_input["evidence_id"] = "plugin-evidence:unbound-local-input"
    unbound_input["inputs"][0].update(
        {
            "source_class": "local_unbound",
            "content_digest_sha256": None,
        }
    )
    fixtures["needs-unbound-input"] = unbound_input

    native_missing = deepcopy(_base_payload())
    native_missing["evidence_id"] = "plugin-evidence:ui-without-native-check"
    native_missing["capabilities"] = ["local_read", "interactive_ui"]
    native_missing["native_verification"]["status"] = "missing"
    fixtures["needs-native-verification"] = native_missing

    domain_missing = deepcopy(_base_payload())
    domain_missing["evidence_id"] = "plugin-evidence:professional-without-domain-check"
    domain_missing["capabilities"] = ["local_read", "professional_judgment"]
    domain_missing["domain_evidence"].update(
        {
            "status": "missing",
            "qualified_reconstruction": "missing",
        }
    )
    fixtures["needs-domain-evidence"] = domain_missing

    expired_external = deepcopy(external_read)
    expired_external["evidence_id"] = "plugin-evidence:expired-external-snapshot"
    expired_external["inputs"][0]["valid_until"] = "2026-07-11T12:15:00Z"
    fixtures["needs-fresh-external-input"] = expired_external

    external_write = deepcopy(_base_payload())
    external_write["evidence_id"] = "plugin-evidence:external-write"
    external_write["capabilities"] = ["local_read", "external_write"]
    fixtures["block-external-write"] = external_write

    external_mutation = deepcopy(external_read)
    external_mutation["evidence_id"] = "plugin-evidence:external-mutation"
    external_mutation["effects"]["external_mutation_observed"] = True
    fixtures["block-external-mutation"] = external_mutation

    runtime_failure = deepcopy(_base_payload())
    runtime_failure["evidence_id"] = "plugin-evidence:runtime-failure"
    runtime_failure["runtime"]["status"] = "failed"
    runtime_failure["checks"][0]["status"] = "failed"
    fixtures["block-runtime-failure"] = runtime_failure

    credential_use = deepcopy(_base_payload())
    credential_use["evidence_id"] = "plugin-evidence:credential-use"
    credential_use["effects"]["credentials_used"] = True
    fixtures["block-credential-use"] = credential_use

    return fixtures


def fixture_bundles() -> dict[str, PluginEvidenceBundleV1]:
    return {
        name: PluginEvidenceBundleV1.model_validate(payload)
        for name, payload in fixture_payloads().items()
    }
