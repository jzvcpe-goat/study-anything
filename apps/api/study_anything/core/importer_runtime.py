"""Controlled runtime for local importer plugins."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping
from uuid import uuid4

from .learning_context import LearningContextPackage, validate_learning_context_package
from .plugin_registry import PluginRegistry, PluginStatus


class ImporterRuntimeError(RuntimeError):
    """Raised when an importer cannot run safely."""


@dataclass(frozen=True)
class ImporterRunResult:
    plugin_id: str
    status: str
    package: LearningContextPackage
    trust: dict[str, object] | None
    network_allowed: bool

    def public_dict(self, *, include_text: bool = True) -> dict[str, object]:
        return {
            "schema_version": "importer-run-v1",
            "plugin_id": self.plugin_id,
            "status": self.status,
            "network_allowed": self.network_allowed,
            "trust": self.trust,
            "package": self.package.public_dict(include_text=include_text),
            "redacted_package": self.package.public_dict(include_text=False),
            "privacy": {
                "agent_secrets_allowed": False,
                "network_disabled_by_default": True,
                "raw_plugin_output_validated": True,
            },
        }


class ImporterRuntime:
    """Run explicitly confirmed local importer plugins.

    Discovery, preview, install, and registry review remain metadata-only. This
    runtime executes an importer only when the caller names a local plugin,
    confirms the manifest permissions, and accepts any high-risk network
    permission with a separate flag.
    """

    def __init__(self, registry: PluginRegistry) -> None:
        self.registry = registry

    def run(
        self,
        plugin_id: str,
        *,
        inputs: Mapping[str, Any],
        confirmed_permissions: list[str],
        allow_network: bool = False,
    ) -> ImporterRunResult:
        status = self._find_ready_importer(plugin_id)
        assert status.manifest is not None
        manifest = status.manifest
        expected_permissions = sorted(manifest.permissions)
        if sorted(set(confirmed_permissions)) != expected_permissions:
            raise ImporterRuntimeError("Importer permissions must be explicitly confirmed.")
        if "write:context" not in manifest.permissions:
            raise ImporterRuntimeError("Importer plugins must request write:context.")
        if "network:http" in manifest.permissions and not allow_network:
            raise ImporterRuntimeError(
                "Importer requests network:http; pass allow_network=true after external review."
            )
        if status.trust and status.trust.install_recommendation != "allow_with_confirmation":
            raise ImporterRuntimeError(
                f"Importer trust recommendation blocks execution: "
                f"{status.trust.install_recommendation}."
            )

        entrypoint = _safe_entrypoint_path(Path(status.path), manifest.entrypoint)
        module = _load_module(entrypoint)
        build_context_package = getattr(module, "build_context_package", None)
        if not callable(build_context_package):
            raise ImporterRuntimeError("Importer entrypoint must expose build_context_package(...).")
        if not isinstance(inputs, Mapping):
            raise ImporterRuntimeError("Importer inputs must be a JSON object.")

        try:
            raw_package = build_context_package(**dict(inputs))
        except TypeError as exc:
            raise ImporterRuntimeError(f"Importer input mismatch: {exc}") from exc
        except Exception as exc:  # pragma: no cover - defensive boundary
            raise ImporterRuntimeError(f"Importer execution failed: {exc.__class__.__name__}.") from exc
        if not isinstance(raw_package, Mapping):
            raise ImporterRuntimeError("Importer must return a Learning Context Package object.")
        try:
            package = validate_learning_context_package(raw_package)
        except ValueError as exc:
            raise ImporterRuntimeError(f"Importer returned invalid Learning Context Package: {exc}") from exc
        return ImporterRunResult(
            plugin_id=manifest.plugin_id,
            status="package_created",
            package=package,
            trust=status.trust.public_dict() if status.trust else None,
            network_allowed=allow_network,
        )

    def _find_ready_importer(self, plugin_id: str) -> PluginStatus:
        matches = [
            status
            for status in self.registry.discover()
            if status.manifest is not None and status.manifest.plugin_id == plugin_id
        ]
        if not matches:
            raise ImporterRuntimeError(f"Importer plugin not found: {plugin_id}.")
        status = matches[0]
        if status.status != "ready":
            raise ImporterRuntimeError(f"Importer plugin is not ready: {status.message}")
        assert status.manifest is not None
        if "importer" not in status.manifest.hooks:
            raise ImporterRuntimeError(f"Plugin {plugin_id} does not expose an importer hook.")
        return status


def _safe_entrypoint_path(plugin_dir: Path, entrypoint: str) -> Path:
    root = plugin_dir.resolve()
    path = (root / entrypoint).resolve()
    if root != path and root not in path.parents:
        raise ImporterRuntimeError("Importer entrypoint must stay inside the plugin directory.")
    if not path.exists() or not path.is_file():
        raise ImporterRuntimeError("Importer entrypoint file does not exist.")
    if path.suffix != ".py":
        raise ImporterRuntimeError("Importer entrypoint must be a Python file.")
    return path


def _load_module(entrypoint: Path) -> ModuleType:
    module_name = f"study_anything_importer_{entrypoint.stem}_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, entrypoint)
    if spec is None or spec.loader is None:
        raise ImporterRuntimeError("Importer entrypoint could not be loaded.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
