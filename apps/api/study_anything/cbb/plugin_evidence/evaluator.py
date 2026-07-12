"""Deterministic plugin evidence evaluation for personal-local use only."""

from __future__ import annotations

from typing import Literal

from study_anything.cbb.plugin_evidence.models import (
    PluginCapability,
    PluginCheckStatus,
    PluginEvidenceBundleV1,
    PluginEvidenceDecisionV1,
    PluginEvidenceStatus,
    PluginInputSourceClass,
    PluginRuntimeStatus,
)
from study_anything.cbb.protocol.canonical import canonical_sha256
from study_anything.cbb.protocol.models import ClaimBoundaryV1, DeliveryScope, parse_timestamp


PLUGIN_EVIDENCE_NOT_CLAIMED = [
    "AI or plugin correctness",
    "plugin installation approval",
    "independent review",
    "external delivery authority",
    "customer delivery authority",
    "production approval",
    "future external actions",
    "absence of side effects outside the observed evidence boundary",
]


def _external_inputs_fresh(bundle: PluginEvidenceBundleV1, evaluated_at: str) -> bool:
    evaluated = parse_timestamp(evaluated_at)
    external_inputs = [
        item
        for item in bundle.inputs
        if item.source_class == PluginInputSourceClass.EXTERNAL_MUTABLE
    ]
    return all(
        item.content_digest_sha256 is not None
        and item.valid_until is not None
        and evaluated < parse_timestamp(item.valid_until)
        for item in external_inputs
    )


def evaluate_plugin_evidence(
    bundle: PluginEvidenceBundleV1,
    *,
    evaluated_at: str,
) -> PluginEvidenceDecisionV1:
    """Evaluate bounded plugin evidence without running or authorizing the plugin."""

    evaluated = parse_timestamp(evaluated_at)
    capabilities = set(bundle.capabilities)
    required_check_statuses = {item.status for item in bundle.checks if item.required}
    has_external_input = any(
        item.source_class == PluginInputSourceClass.EXTERNAL_MUTABLE for item in bundle.inputs
    )

    native_sufficient = (
        bundle.native_verification.status == PluginEvidenceStatus.PASSED
        if PluginCapability.INTERACTIVE_UI in capabilities
        else bundle.native_verification.status != PluginEvidenceStatus.FAILED
    )
    domain_sufficient = (
        bundle.domain_evidence.status == PluginEvidenceStatus.PASSED
        and bundle.domain_evidence.qualified_reconstruction == PluginEvidenceStatus.PASSED
        if PluginCapability.PROFESSIONAL_JUDGMENT in capabilities
        else bundle.domain_evidence.status != PluginEvidenceStatus.FAILED
    )
    inputs_bound = all(
        item.source_class != PluginInputSourceClass.LOCAL_UNBOUND
        and item.content_digest_sha256 is not None
        for item in bundle.inputs
    )
    project_mutation_bound = not bundle.effects.project_git_mutation_observed or (
        PluginCapability.LOCAL_WRITE in capabilities
        and bundle.effects.project_mutation_bound_to_subject_digest
        and bundle.effects.post_run_subject_digest_sha256 is not None
    )
    network_usage_declared = not bundle.effects.network_access_observed or (
        PluginCapability.EXTERNAL_READ in capabilities and has_external_input
    )
    checks = {
        "bundle_not_expired": evaluated < parse_timestamp(bundle.valid_until),
        "package_digest_bound": bundle.plugin.package_digest_sha256 is not None,
        "manifest_digest_bound": bundle.plugin.manifest_digest_sha256 is not None,
        "runtime_ready": bundle.runtime.status == PluginRuntimeStatus.READY,
        "runtime_dependencies_verified": (
            bundle.runtime.dependency_check == PluginEvidenceStatus.PASSED
        ),
        "required_checks_passed": required_check_statuses == {PluginCheckStatus.PASSED},
        "inputs_bound": inputs_bound,
        "external_inputs_fresh": _external_inputs_fresh(bundle, evaluated_at),
        "no_external_write_capability": (PluginCapability.EXTERNAL_WRITE not in capabilities),
        "no_external_mutation": not bundle.effects.external_mutation_observed,
        "no_credentials_used": not bundle.effects.credentials_used,
        "network_usage_declared": network_usage_declared,
        "project_mutation_bound": project_mutation_bound,
        "native_verification_sufficient": native_sufficient,
        "domain_evidence_sufficient": domain_sufficient,
    }

    hard_failures: list[str] = []
    missing: list[str] = []

    if PluginCapability.EXTERNAL_WRITE in capabilities:
        hard_failures.append("external_write_capability")
    if bundle.effects.external_mutation_observed:
        hard_failures.append("external_mutation_observed")
    if bundle.effects.credentials_used:
        hard_failures.append("credentials_used")
    if not network_usage_declared:
        hard_failures.append("undeclared_network_access")
    if not project_mutation_bound:
        hard_failures.append("unbound_project_mutation")
    if bundle.runtime.status in {PluginRuntimeStatus.FAILED, PluginRuntimeStatus.TIMEOUT}:
        hard_failures.append(f"runtime_{bundle.runtime.status.value}")
    if bundle.runtime.dependency_check == PluginEvidenceStatus.FAILED:
        hard_failures.append("runtime_dependency_check_failed")
    if required_check_statuses & {
        PluginCheckStatus.FAILED,
        PluginCheckStatus.ERROR,
        PluginCheckStatus.TIMEOUT,
    }:
        hard_failures.append("required_check_failure")
    if bundle.native_verification.status == PluginEvidenceStatus.FAILED:
        hard_failures.append("native_verification_failed")
    if bundle.domain_evidence.status == PluginEvidenceStatus.FAILED:
        hard_failures.append("domain_evidence_failed")
    if bundle.domain_evidence.qualified_reconstruction == PluginEvidenceStatus.FAILED:
        hard_failures.append("qualified_reconstruction_failed")

    if bundle.plugin.package_digest_sha256 is None:
        missing.append("package_digest")
    if bundle.plugin.manifest_digest_sha256 is None:
        missing.append("manifest_digest")
    if bundle.runtime.status == PluginRuntimeStatus.NOT_RUN:
        missing.append("runtime_execution")
    if bundle.runtime.dependency_check in {
        PluginEvidenceStatus.MISSING,
        PluginEvidenceStatus.NOT_APPLICABLE,
    }:
        missing.append("runtime_dependency_check")
    if PluginCheckStatus.NOT_RUN in required_check_statuses:
        missing.append("required_check_execution")
    if not inputs_bound:
        missing.append("input_binding")
    if not checks["external_inputs_fresh"]:
        missing.append("external_input_freshness")
    if not checks["bundle_not_expired"]:
        missing.append("fresh_plugin_evidence")
    if PluginCapability.INTERACTIVE_UI in capabilities and not native_sufficient:
        missing.append("native_verification")
    if PluginCapability.PROFESSIONAL_JUDGMENT in capabilities and not domain_sufficient:
        missing.append("domain_evidence_and_qualified_reconstruction")

    hard_failures = sorted(set(hard_failures))
    missing = sorted(set(missing))
    status: Literal["allow_personal_local", "needs_evidence", "block"]
    if hard_failures:
        status = "block"
        approved_scope = DeliveryScope.BLOCKED
        reasons = [f"hard_deny:{item}" for item in hard_failures]
    elif missing:
        status = "needs_evidence"
        approved_scope = DeliveryScope.BLOCKED
        reasons = [f"missing:{item}" for item in missing]
    else:
        status = "allow_personal_local"
        approved_scope = DeliveryScope.PERSONAL_LOCAL
        reasons = []

    bundle_digest = canonical_sha256(bundle)
    decision_seed = {
        "evidence_digest_sha256": bundle_digest,
        "evaluated_at": evaluated_at,
        "status": status,
    }
    current_claim = (
        "This evidence supports one plugin-assisted personal-local candidate only."
        if approved_scope == DeliveryScope.PERSONAL_LOCAL
        else "This plugin evidence grants no delivery scope."
    )
    return PluginEvidenceDecisionV1(
        schema_version="delivery-clearance.plugin-evidence-decision.v1",
        decision_id=f"plugin-evidence:{canonical_sha256(decision_seed)[:32]}",
        evidence_ref=bundle.evidence_id,
        evidence_digest_sha256=bundle_digest,
        plugin_id=bundle.plugin.plugin_id,
        status=status,
        approved_scope=approved_scope,
        checks=checks,
        reasons=reasons,
        missing_evidence=missing,
        evaluated_at=evaluated_at,
        valid_until=bundle.valid_until,
        manifest_or_install_state_sufficient=False,
        customer_delivery_authorized=False,
        production_authorized=False,
        external_action_authorized=False,
        claim_boundary=ClaimBoundaryV1(
            current_claim=current_claim,
            maximum_scope=approved_scope,
            not_claimed=PLUGIN_EVIDENCE_NOT_CLAIMED,
        ),
        privacy=bundle.privacy,
    )
