"""Plugin discovery for the self-host alpha."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional

from .plugin_manifest import PluginManifest, validate_manifest


@dataclass(frozen=True)
class PluginStatus:
    manifest: Optional[PluginManifest]
    path: str
    status: str
    message: str

    def public_dict(self) -> dict[str, object]:
        return {
            "manifest": asdict(self.manifest) if self.manifest else None,
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
