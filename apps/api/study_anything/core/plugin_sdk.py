"""Public Plugin SDK contracts and read-only validation helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .plugin_manifest import (
    ALLOWED_HOOKS,
    ALLOWED_PERMISSIONS,
    ALLOWED_PLUGIN_CAPABILITIES,
    PLUGIN_MANIFEST_SCHEMA_VERSION,
    PluginManifest,
    describe_permissions,
)
from .plugin_registry import PluginRegistry, PluginStatus


PLUGIN_SDK_SCHEMA_VERSION = "plugin-sdk-v1"
PLUGIN_CAPABILITY_INDEX_SCHEMA_VERSION = "plugin-capability-index-v1"
PLUGIN_PACKAGE_VALIDATION_SCHEMA_VERSION = "plugin-package-validation-v1"


@dataclass(frozen=True)
class PluginHookContract:
    hook: str
    lifecycle: str
    entrypoint_symbols: list[str]
    required_permissions: list[str]
    optional_permissions: list[str]
    input_contract: str
    output_contract: str
    alpha_runtime: str
    privacy_notes: list[str]

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


HOOK_CONTRACTS: dict[str, PluginHookContract] = {
    "importer": PluginHookContract(
        hook="importer",
        lifecycle="backend_runtime",
        entrypoint_symbols=["build_context_package"],
        required_permissions=["write:context"],
        optional_permissions=["read:context", "network:http"],
        input_contract="Plugin-specific JSON object supplied by a platform Agent or user.",
        output_contract="learning-context-package-v1",
        alpha_runtime="POST /v1/importers/{plugin_id}/run",
        privacy_notes=[
            "The platform Agent gathers external data first and passes bounded excerpts.",
            "Importer output is validated before it can become session state.",
        ],
    ),
    "exporter": PluginHookContract(
        hook="exporter",
        lifecycle="metadata_contract",
        entrypoint_symbols=["export_session", "export_second_brain_handoff"],
        required_permissions=["read:sessions"],
        optional_permissions=["read:context"],
        input_contract="Redacted session, package, or second-brain handoff DTO.",
        output_contract="Plugin-defined export artifact, preferably Markdown or JSON.",
        alpha_runtime="metadata-only; core exports are provided through /v1/sessions/{id}/exports/*",
        privacy_notes=[
            "Exporters must not include raw source text, learner answers, grading feedback, agent endpoints, or secrets unless a future explicit consent flow adds them.",
        ],
    ),
    "enrichment": PluginHookContract(
        hook="enrichment",
        lifecycle="metadata_contract",
        entrypoint_symbols=["build_enrichment_artifact"],
        required_permissions=["read:context"],
        optional_permissions=["write:context", "network:http"],
        input_contract="Redacted Learning Context Package or source-bound enrichment request.",
        output_contract="learning-enrichment-artifact-v1 or redacted micro-lesson HTML/Markdown.",
        alpha_runtime="metadata-only; platform Agents should call core enrichment APIs first",
        privacy_notes=[
            "Enrichment plugins should emit references, locators, and redacted teaching aids rather than raw external data dumps.",
        ],
    ),
    "source_verifier": PluginHookContract(
        hook="source_verifier",
        lifecycle="metadata_contract",
        entrypoint_symbols=["verify_source_reference"],
        required_permissions=["read:context"],
        optional_permissions=["network:http"],
        input_contract="Reference, source_type, locator, and bounded metadata.",
        output_contract="source verification DTO with status, reference, confidence, and citations.",
        alpha_runtime="metadata-only",
        privacy_notes=[
            "Source verifiers should return reference-level evidence, not copied source bodies.",
        ],
    ),
    "agent_tool": PluginHookContract(
        hook="agent_tool",
        lifecycle="platform_agent_contract",
        entrypoint_symbols=["tool_manifest"],
        required_permissions=["read:context"],
        optional_permissions=["network:http", "read:sessions"],
        input_contract="Tool-specific JSON schema declared by the plugin.",
        output_contract="Structured tool result validated by the platform Agent adapter.",
        alpha_runtime="metadata-only; no automatic tool execution by Study Anything",
        privacy_notes=[
            "Real model keys, browser access, and external tool credentials stay in the platform Agent.",
        ],
    ),
    "agent_panel": PluginHookContract(
        hook="agent_panel",
        lifecycle="frontend_extension_contract",
        entrypoint_symbols=["panel_manifest"],
        required_permissions=["ui:panel"],
        optional_permissions=["read:agents"],
        input_contract="Panel registration metadata.",
        output_contract="agent_panel manifest for a future UI host.",
        alpha_runtime="metadata-only",
        privacy_notes=[
            "Panels must not request or display raw model secrets.",
        ],
    ),
    "agent_provider": PluginHookContract(
        hook="agent_provider",
        lifecycle="backend_configuration_template",
        entrypoint_symbols=["provider_template"],
        required_permissions=["read:agents", "write:agents"],
        optional_permissions=["network:http", "ui:panel"],
        input_contract="User-owned Agent provider configuration template.",
        output_contract="AgentProviderConfig template; secrets remain outside Study Anything.",
        alpha_runtime="metadata-only",
        privacy_notes=[
            "Provider plugins can describe endpoints and capabilities, but Study Anything does not store model API keys.",
        ],
    ),
    "model_provider": PluginHookContract(
        hook="model_provider",
        lifecycle="deprecated_compatibility",
        entrypoint_symbols=["provider_template"],
        required_permissions=["read:models"],
        optional_permissions=["write:models", "network:http"],
        input_contract="Deprecated model-provider compatibility metadata.",
        output_contract="Agent-backed provider template.",
        alpha_runtime="deprecated alias; use agent_provider",
        privacy_notes=[
            "This hook remains only for one-release compatibility and should not store model secrets.",
        ],
    ),
    "quiz_generator": PluginHookContract(
        hook="quiz_generator",
        lifecycle="metadata_contract",
        entrypoint_symbols=["generate_quiz_items"],
        required_permissions=["read:context"],
        optional_permissions=["network:http"],
        input_contract="Source-bound quiz generation task.",
        output_contract="validated quiz item list.",
        alpha_runtime="metadata-only; real reasoning is delegated to user-owned Agents",
        privacy_notes=[
            "Quiz generators should preserve source references and avoid opaque answer keys in logs.",
        ],
    ),
    "grader": PluginHookContract(
        hook="grader",
        lifecycle="metadata_contract",
        entrypoint_symbols=["grade_answer"],
        required_permissions=["read:sessions"],
        optional_permissions=["network:http"],
        input_contract="Answer grading task with rubric and bounded source references.",
        output_contract="validated grading result.",
        alpha_runtime="metadata-only; real reasoning is delegated to user-owned Agents",
        privacy_notes=[
            "Graders must not publish learner answers or feedback outside the local workflow.",
        ],
    ),
    "ui_panel": PluginHookContract(
        hook="ui_panel",
        lifecycle="deprecated_frontend_extension_contract",
        entrypoint_symbols=["panel_manifest"],
        required_permissions=["ui:panel"],
        optional_permissions=[],
        input_contract="Panel registration metadata.",
        output_contract="ui_panel manifest for compatibility clients.",
        alpha_runtime="metadata-only; use agent_panel for new work",
        privacy_notes=[
            "UI panels are display metadata only in this alpha.",
        ],
    ),
}


def plugin_sdk_contract() -> dict[str, object]:
    """Return the public SDK contract without inspecting or executing plugins."""

    return {
        "schema_version": PLUGIN_SDK_SCHEMA_VERSION,
        "manifest_schema_version": PLUGIN_MANIFEST_SCHEMA_VERSION,
        "api_version": "0.1",
        "local_first": True,
        "remote_code_downloads_allowed": False,
        "entrypoints_executed": False,
        "supported_hooks": [HOOK_CONTRACTS[hook].public_dict() for hook in sorted(HOOK_CONTRACTS)],
        "allowed_hooks": sorted(ALLOWED_HOOKS),
        "allowed_permissions": [
            detail.public_dict() for detail in describe_permissions(sorted(ALLOWED_PERMISSIONS))
        ],
        "allowed_capabilities": sorted(ALLOWED_PLUGIN_CAPABILITIES),
        "sample_plugins": [
            "example-note-importer",
            "example-web-importer",
            "example-exporter",
            "example-agent-provider",
        ],
        "privacy": {
            "raw_source_text_allowed_in_registry": False,
            "learner_answers_allowed_in_registry": False,
            "agent_endpoints_allowed_in_registry": False,
            "agent_metadata_allowed_in_registry": False,
            "secrets_allowed_in_registry": False,
            "plugin_entrypoints_executed_during_validation": False,
        },
    }


def plugin_capability_index(statuses: Iterable[PluginStatus]) -> dict[str, object]:
    items = [_capability_item(status) for status in statuses]
    hook_counts: dict[str, int] = {}
    for item in items:
        for hook in item.get("hooks", []):
            hook_counts[str(hook)] = hook_counts.get(str(hook), 0) + 1
    return {
        "schema_version": PLUGIN_CAPABILITY_INDEX_SCHEMA_VERSION,
        "manifest_schema_version": PLUGIN_MANIFEST_SCHEMA_VERSION,
        "plugin_count": len(items),
        "hook_counts": dict(sorted(hook_counts.items())),
        "items": items,
        "privacy": {
            "entrypoints_executed": False,
            "returns_plugin_source_code": False,
            "returns_raw_source_text": False,
            "returns_learner_answers": False,
            "returns_agent_secrets": False,
        },
    }


def validate_plugin_package(source_dir: Path, registry: PluginRegistry) -> dict[str, object]:
    """Preview one local plugin as an SDK package without copying or executing it."""

    status = registry.preview_local(source_dir)
    manifest = status.manifest
    trust = status.trust.public_dict() if status.trust else None
    validation_errors = _contract_errors(manifest)
    installable = (
        status.status == "ready"
        and manifest is not None
        and not validation_errors
        and (status.trust is None or status.trust.install_recommendation == "allow_with_confirmation")
    )
    return {
        "schema_version": PLUGIN_PACKAGE_VALIDATION_SCHEMA_VERSION,
        "status": "valid" if status.status == "ready" and not validation_errors else "invalid",
        "manifest": _manifest_public(manifest) if manifest else None,
        "required_permission_confirmations": sorted(manifest.permissions) if manifest else [],
        "capabilities": _manifest_capabilities(manifest) if manifest else [],
        "hook_contracts": _hook_contracts(manifest.hooks if manifest else []),
        "trust": trust,
        "installable_with_confirmation": installable,
        "execution_allowed_by_validation": False,
        "validation_errors": validation_errors,
        "warnings": list(status.trust.warnings) if status.trust else [],
        "privacy": {
            "entrypoints_executed": False,
            "package_copied": False,
            "returns_plugin_source_code": False,
            "returns_raw_source_text": False,
            "returns_learner_answers": False,
            "returns_agent_secrets": False,
        },
    }


def _capability_item(status: PluginStatus) -> dict[str, object]:
    manifest = status.manifest
    if manifest is None:
        return {
            "plugin_id": None,
            "name": None,
            "status": status.status,
            "message": status.message,
            "hooks": [],
            "capabilities": [],
            "install_recommendation": status.trust.install_recommendation if status.trust else "do_not_install",
        }
    return {
        "plugin_id": manifest.plugin_id,
        "name": manifest.name,
        "version": manifest.version,
        "manifest_schema_version": manifest.schema_version,
        "status": status.status,
        "hooks": list(manifest.hooks),
        "capabilities": _manifest_capabilities(manifest),
        "permissions": list(manifest.permissions),
        "permission_risks": {
            detail.permission: detail.risk for detail in describe_permissions(manifest.permissions)
        },
        "trust": status.trust.public_dict() if status.trust else None,
        "runtime": [_runtime_for_hook(hook) for hook in manifest.hooks],
    }


def _manifest_public(manifest: PluginManifest | None) -> dict[str, object] | None:
    if manifest is None:
        return None
    return {
        "plugin_id": manifest.plugin_id,
        "name": manifest.name,
        "version": manifest.version,
        "api_version": manifest.api_version,
        "schema_version": manifest.schema_version,
        "hooks": list(manifest.hooks),
        "permissions": list(manifest.permissions),
        "capabilities": _manifest_capabilities(manifest),
        "description": manifest.description,
    }


def _manifest_capabilities(manifest: PluginManifest) -> list[str]:
    declared = set(manifest.capabilities)
    inferred = set()
    for hook in manifest.hooks:
        inferred.update(_capabilities_for_hook(hook))
    return sorted(declared | inferred)


def _capabilities_for_hook(hook: str) -> list[str]:
    mapping = {
        "agent_panel": ["ui.register_panel"],
        "agent_provider": ["agent.register_provider"],
        "agent_tool": ["agent.invoke_tool"],
        "enrichment": ["enrich.micro_lesson"],
        "exporter": ["export.markdown"],
        "grader": ["answer.grade"],
        "importer": ["import.context"],
        "model_provider": ["agent.register_provider"],
        "quiz_generator": ["quiz.generate"],
        "source_verifier": ["source.verify_reference"],
        "ui_panel": ["ui.register_panel"],
    }
    return mapping.get(hook, [])


def _contract_errors(manifest: PluginManifest | None) -> list[str]:
    if manifest is None:
        return ["manifest_invalid_or_missing"]
    errors: list[str] = []
    for hook in manifest.hooks:
        contract = HOOK_CONTRACTS.get(hook)
        if contract is None:
            errors.append(f"unsupported_hook:{hook}")
            continue
        missing = sorted(set(contract.required_permissions) - set(manifest.permissions))
        if missing:
            errors.append(f"hook:{hook}:missing_required_permissions:{','.join(missing)}")
        unsupported = sorted(
            set(manifest.permissions)
            - set(contract.required_permissions)
            - set(contract.optional_permissions)
        )
        if unsupported and len(manifest.hooks) == 1:
            errors.append(f"hook:{hook}:unsupported_permissions:{','.join(unsupported)}")
    return errors


def _hook_contracts(hooks: Iterable[str]) -> list[dict[str, object]]:
    return [
        HOOK_CONTRACTS[hook].public_dict()
        for hook in sorted(set(hooks))
        if hook in HOOK_CONTRACTS
    ]


def _runtime_for_hook(hook: str) -> Mapping[str, object]:
    contract = HOOK_CONTRACTS.get(hook)
    if contract is None:
        return {"hook": hook, "alpha_runtime": "unsupported"}
    return {"hook": hook, "alpha_runtime": contract.alpha_runtime}
