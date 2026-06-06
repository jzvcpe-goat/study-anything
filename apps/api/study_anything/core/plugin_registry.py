"""Plugin discovery for the self-host alpha."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .plugin_manifest import PluginManifest, describe_permissions, validate_manifest
from .plugin_trust import PluginTrustReport, assess_plugin_trust


@dataclass(frozen=True)
class PluginStatus:
    manifest: Optional[PluginManifest]
    path: str
    status: str
    message: str
    trust: Optional[PluginTrustReport] = None

    def public_dict(self) -> dict[str, object]:
        permission_details: list[dict[str, str]] = []
        if self.manifest:
            permission_details = [
                detail.public_dict() for detail in describe_permissions(self.manifest.permissions)
            ]
        return {
            "manifest": asdict(self.manifest) if self.manifest else None,
            "permission_details": permission_details,
            "path": self.path,
            "status": self.status,
            "message": self.message,
            "trust": self.trust.public_dict() if self.trust else None,
        }


class PluginRegistry:
    def __init__(self, plugin_dirs: Iterable[Path]) -> None:
        self.plugin_dirs = list(plugin_dirs)

    def discover(self) -> List[PluginStatus]:
        statuses: List[PluginStatus] = []
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                continue
            for manifest_path in sorted(plugin_dir.glob("*/plugin.json")):
                statuses.append(self._load_manifest(manifest_path))
        return statuses

    def preview_local(self, source_dir: Path) -> PluginStatus:
        """Validate one explicitly selected local plugin without installing it."""

        source = source_dir.resolve()
        return self._load_manifest(source / "plugin.json")

    def install_local(
        self,
        source_dir: Path,
        install_dir: Path,
        *,
        replace_existing: bool = False,
    ) -> PluginStatus:
        """Validate and copy one explicitly selected local plugin directory."""

        source = source_dir.resolve()
        source_status = self._load_manifest(source / "plugin.json")
        if source_status.manifest is None:
            raise ValueError(f"Cannot install invalid plugin: {source_status.message}")

        install_root = install_dir.resolve()
        target = install_root / source_status.manifest.plugin_id
        if target == source or source in target.parents or target in source.parents:
            raise ValueError("Plugin install destination must be outside the source directory.")
        if target.exists():
            if not replace_existing:
                raise FileExistsError(
                    f"Plugin '{source_status.manifest.plugin_id}' is already installed."
                )
            shutil.rmtree(target)
        install_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pyo", ".DS_Store", ".git"),
        )
        return self._load_manifest(target / "plugin.json")

    def _load_manifest(self, manifest_path: Path) -> PluginStatus:
        plugin_dir = manifest_path.parent
        try:
            values = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = validate_manifest(values)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return PluginStatus(
                manifest=None,
                path=str(plugin_dir),
                status="invalid",
                message=str(exc),
                trust=assess_plugin_trust(plugin_dir, None),
            )
        registry_entry, trusted_keys = self._registry_context(plugin_dir, manifest)
        return PluginStatus(
            manifest=manifest,
            path=str(plugin_dir),
            status="ready",
            message="Plugin manifest is valid.",
            trust=assess_plugin_trust(
                plugin_dir,
                manifest,
                registry_entry=registry_entry,
                trusted_registry_keys=trusted_keys,
            ),
        )

    def _registry_context(
        self,
        plugin_dir: Path,
        manifest: PluginManifest,
    ) -> tuple[Optional[dict[str, object]], dict[str, dict[str, object]]]:
        registry_path = plugin_dir.parent / "registry.json"
        if not registry_path.exists():
            return None, {}
        try:
            values = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, {}
        plugins = values.get("plugins")
        if not isinstance(plugins, list):
            return None, {}
        trusted_keys = _trusted_registry_keys(values)
        for entry in plugins:
            if not isinstance(entry, dict):
                continue
            if entry.get("id") != manifest.plugin_id:
                continue
            if _registry_path_matches(registry_path, plugin_dir, entry.get("path")):
                return entry, trusted_keys
        return None, trusted_keys


def _trusted_registry_keys(values: dict[str, object]) -> dict[str, dict[str, object]]:
    keys = values.get("trustedKeys")
    if not isinstance(keys, list):
        return {}
    indexed: dict[str, dict[str, object]] = {}
    for key in keys:
        if not isinstance(key, dict):
            continue
        key_id = key.get("id")
        if isinstance(key_id, str) and key_id.strip():
            indexed[key_id.strip()] = key
    return indexed


def _registry_path_matches(registry_path: Path, plugin_dir: Path, raw_path: object) -> bool:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return True
    entry_path = Path(raw_path)
    plugin_resolved = plugin_dir.resolve()
    candidates = [
        (registry_path.parent / entry_path).resolve(),
        (registry_path.parent.parent / entry_path).resolve(),
    ]
    return plugin_resolved in candidates or entry_path.name == plugin_dir.name
