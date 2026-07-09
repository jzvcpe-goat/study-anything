"""Plugin discovery for the self-host alpha."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Mapping, Optional

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
        public_path = _public_plugin_path(self.path)
        assert public_path is not None
        public_message = self.message.replace(self.path, public_path)
        permission_details: list[dict[str, str]] = []
        if self.manifest:
            permission_details = [
                detail.public_dict() for detail in describe_permissions(self.manifest.permissions)
            ]
        return {
            "manifest": asdict(self.manifest) if self.manifest else None,
            "permission_details": permission_details,
            "path": public_path,
            "status": self.status,
            "message": public_message,
            "trust": self.trust.public_dict() if self.trust else None,
        }


@dataclass(frozen=True)
class PluginRegistryReviewItem:
    plugin_id: str
    name: str
    installed_version: Optional[str]
    registry_version: Optional[str]
    registry_path: str
    source_path: Optional[str]
    registry_status: str
    signature_status: str
    review_status: str
    risk_level: str
    install_recommendation: str
    update_status: str
    action: str
    warnings: list[str]

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PluginRegistryReview:
    registry_files: list[str]
    trusted_key_count: int
    plugin_count: int
    verified_count: int
    signature_verified_count: int
    review_required_count: int
    update_available_count: int
    blocked_count: int
    items: list[PluginRegistryReviewItem]

    def public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "plugin-registry-review-v1",
            "local_first": True,
            "remote_code_downloads_allowed": False,
            "entrypoints_executed": False,
            "registry_files": self.registry_files,
            "trusted_key_count": self.trusted_key_count,
            "plugin_count": self.plugin_count,
            "verified_count": self.verified_count,
            "signature_verified_count": self.signature_verified_count,
            "review_required_count": self.review_required_count,
            "update_available_count": self.update_available_count,
            "blocked_count": self.blocked_count,
            "items": [item.public_dict() for item in self.items],
            "notes": [
                "Registry review reads metadata only and never downloads plugin code.",
                "Install and update remain explicit local-directory operations.",
                "Remote marketplace payments and automatic updates are not enabled in the self-host alpha.",
            ],
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

        return self._copy_local_plugin(
            source_dir,
            install_dir,
            replace_existing=replace_existing,
            blocked_message="Plugin trust policy blocks installation.",
        )

    def quarantine_local(
        self,
        source_dir: Path,
        quarantine_dir: Path,
        *,
        replace_existing: bool = True,
    ) -> PluginStatus:
        """Validate and copy one selected plugin into a quarantine directory.

        Quarantine is still metadata-only: entrypoints are not executed and the
        copied package is not scanned as an installed plugin unless the caller
        explicitly includes the quarantine root in `plugin_dirs`.
        """

        return self._copy_local_plugin(
            source_dir,
            quarantine_dir,
            replace_existing=replace_existing,
            blocked_message="Plugin trust policy blocks quarantine copy.",
        )

    def _copy_local_plugin(
        self,
        source_dir: Path,
        destination_dir: Path,
        *,
        replace_existing: bool,
        blocked_message: str,
    ) -> PluginStatus:
        source = source_dir.resolve()
        source_status = self._load_manifest(source / "plugin.json")
        if source_status.manifest is None:
            raise ValueError(f"Cannot install invalid plugin: {source_status.message}")
        if (
            source_status.trust is not None
            and source_status.trust.install_recommendation == "do_not_install"
        ):
            raise ValueError(blocked_message)

        destination_root = destination_dir.resolve()
        target = destination_root / source_status.manifest.plugin_id
        if target == source or source in target.parents or target in source.parents:
            raise ValueError("Plugin destination must be outside the source directory.")
        if target.exists():
            if not replace_existing:
                raise FileExistsError(
                    f"Plugin '{source_status.manifest.plugin_id}' is already present."
                )
            shutil.rmtree(target)
        destination_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pyo", ".DS_Store", ".git"),
        )
        return self._load_manifest(target / "plugin.json")

    def registry_review(self) -> PluginRegistryReview:
        """Summarize local registry metadata against discovered plugins.

        This is the self-host alpha foundation for a future signed plugin
        marketplace. It reads registry metadata only and never downloads,
        installs, updates, or executes plugin code.
        """

        statuses = self.discover()
        discovered = {
            status.manifest.plugin_id: status
            for status in statuses
            if status.manifest is not None
        }
        registry_documents = self._registry_documents()
        items: list[PluginRegistryReviewItem] = []
        seen_ids: set[str] = set()
        trusted_key_count = sum(len(_trusted_registry_keys(document.values)) for document in registry_documents)
        for document in registry_documents:
            for entry in _registry_plugins(document.values):
                plugin_id = _string_field(entry, "id")
                if not plugin_id:
                    continue
                status = discovered.get(plugin_id)
                seen_ids.add(plugin_id)
                registry_version = _string_field(entry, "version")
                source_path = _string_field(entry, "path")
                if status and status.manifest:
                    trust = status.trust
                    installed_version = status.manifest.version
                    name = status.manifest.name
                    registry_status = trust.registry_status if trust else "unknown"
                    signature_status = trust.signature_status if trust else "unknown"
                    review_status = trust.review_status if trust else "unreviewed"
                    risk_level = trust.risk_level if trust else "unknown"
                    install_recommendation = trust.install_recommendation if trust else "review_required"
                    warnings = list(trust.warnings) if trust else ["Trust report unavailable."]
                    update_status = _update_status(installed_version, registry_version)
                    action = _review_action(
                        registry_status=registry_status,
                        signature_status=signature_status,
                        install_recommendation=install_recommendation,
                        update_status=update_status,
                    )
                else:
                    installed_version = None
                    name = _string_field(entry, "name") or plugin_id
                    registry_status = "metadata_only"
                    signature_status = _entry_signature_status(entry)
                    review_status = _entry_review_status(entry)
                    risk_level = "unknown"
                    install_recommendation = "review_required"
                    update_status = "not_installed"
                    action = "manual_review_required"
                    warnings = [
                        "Registry entry is not installed locally; review and fetch source outside Study Anything before installing.",
                    ]
                items.append(
                    PluginRegistryReviewItem(
                        plugin_id=plugin_id,
                        name=name,
                        installed_version=installed_version,
                        registry_version=registry_version,
                        registry_path=document.public_path,
                        source_path=_public_plugin_path(source_path),
                        registry_status=registry_status,
                        signature_status=signature_status,
                        review_status=review_status,
                        risk_level=risk_level,
                        install_recommendation=install_recommendation,
                        update_status=update_status,
                        action=action,
                        warnings=warnings,
                    )
                )
        for plugin_id, status in discovered.items():
            if plugin_id in seen_ids or status.manifest is None:
                continue
            trust = status.trust
            items.append(
                PluginRegistryReviewItem(
                    plugin_id=plugin_id,
                    name=status.manifest.name,
                    installed_version=status.manifest.version,
                    registry_version=None,
                    registry_path="not_listed",
                    source_path=_public_plugin_path(status.path),
                    registry_status=trust.registry_status if trust else "not_listed",
                    signature_status=trust.signature_status if trust else "unsigned",
                    review_status=trust.review_status if trust else "unreviewed",
                    risk_level=trust.risk_level if trust else "unknown",
                    install_recommendation=trust.install_recommendation if trust else "review_required",
                    update_status="not_listed",
                    action="add_to_signed_registry",
                    warnings=list(trust.warnings) if trust else ["Plugin is not listed in a registry."],
                )
            )
        items = sorted(items, key=lambda item: (item.action, item.plugin_id))
        return PluginRegistryReview(
            registry_files=[document.public_path for document in registry_documents],
            trusted_key_count=trusted_key_count,
            plugin_count=len(items),
            verified_count=sum(1 for item in items if item.registry_status == "digest_verified"),
            signature_verified_count=sum(1 for item in items if item.signature_status == "registry_signature_verified"),
            review_required_count=sum(1 for item in items if item.action in {"manual_review_required", "confirm_update_review"}),
            update_available_count=sum(1 for item in items if item.update_status == "update_available"),
            blocked_count=sum(1 for item in items if item.action == "block_install"),
            items=items,
        )

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

    def _registry_documents(self) -> list["_RegistryDocument"]:
        documents: list[_RegistryDocument] = []
        seen: set[Path] = set()
        for plugin_dir in self.plugin_dirs:
            registry_path = (plugin_dir / "registry.json").resolve()
            if registry_path in seen or not registry_path.exists():
                continue
            seen.add(registry_path)
            try:
                values = json.loads(registry_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(values, dict):
                documents.append(
                    _RegistryDocument(
                        path=registry_path,
                        values=values,
                    )
                )
        return documents


@dataclass(frozen=True)
class _RegistryDocument:
    path: Path
    values: dict[str, object]

    @property
    def public_path(self) -> str:
        return self.path.name


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


def _registry_plugins(values: Mapping[str, object]) -> list[dict[str, object]]:
    plugins = values.get("plugins")
    if not isinstance(plugins, list):
        return []
    return [entry for entry in plugins if isinstance(entry, dict)]


def _string_field(values: Mapping[str, object], key: str) -> Optional[str]:
    value = values.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _entry_signature_status(entry: Mapping[str, object]) -> str:
    signature = entry.get("signature")
    if isinstance(signature, Mapping):
        return "metadata_only"
    if _string_field(entry, "sourceDigest"):
        return "registry_digest_declared"
    return "unsigned"


def _entry_review_status(entry: Mapping[str, object]) -> str:
    review = entry.get("review")
    if isinstance(review, Mapping):
        status = _string_field(review, "status")
        if status:
            return status
    status = _string_field(entry, "reviewStatus")
    return status or "unreviewed"


def _update_status(installed_version: str, registry_version: Optional[str]) -> str:
    if not registry_version:
        return "unknown"
    comparison = _compare_versions(registry_version, installed_version)
    if comparison > 0:
        return "update_available"
    if comparison < 0:
        return "local_newer"
    return "current"


def _compare_versions(left: str, right: str) -> int:
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    max_len = max(len(left_parts), len(right_parts))
    left_parts += [0] * (max_len - len(left_parts))
    right_parts += [0] * (max_len - len(right_parts))
    if left_parts > right_parts:
        return 1
    if left_parts < right_parts:
        return -1
    return 0


def _version_parts(value: str) -> list[int]:
    parts: list[int] = []
    for raw_part in value.replace("-", ".").split("."):
        digits = "".join(char for char in raw_part if char.isdigit())
        if digits:
            parts.append(int(digits))
    return parts or [0]


def _review_action(
    *,
    registry_status: str,
    signature_status: str,
    install_recommendation: str,
    update_status: str,
) -> str:
    if install_recommendation == "do_not_install" or registry_status in {"digest_mismatch", "missing_digest"}:
        return "block_install"
    if update_status == "update_available":
        return "confirm_update_review"
    if signature_status in {"registry_signature_verified", "registry_digest_verified"} and install_recommendation == "allow_with_confirmation":
        return "ready"
    return "manual_review_required"


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


def _public_plugin_path(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return "<local-plugin-path>" if Path(value).is_absolute() else value
