"""Plugin discovery for the self-host alpha."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .plugin_manifest import PluginManifest, describe_permissions, validate_manifest


@dataclass(frozen=True)
class PluginStatus:
    manifest: Optional[PluginManifest]
    path: str
    status: str
    message: str

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
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )
        return self._load_manifest(target / "plugin.json")

    def _load_manifest(self, manifest_path: Path) -> PluginStatus:
        try:
            values = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = validate_manifest(values)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return PluginStatus(
                manifest=None,
                path=str(manifest_path.parent),
                status="invalid",
                message=str(exc),
            )
        return PluginStatus(
            manifest=manifest,
            path=str(manifest_path.parent),
            status="ready",
            message="Plugin manifest is valid.",
        )
