"""Local-first plugin trust summaries.

The alpha plugin layer never downloads remote code, executes entrypoints during
installation, or stores third-party secrets. This module gives users a compact
review surface for local plugins before copying them into the data directory.
"""

from __future__ import annotations

import hashlib
import base64
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .plugin_manifest import (
    ALLOWED_REVIEW_STATUSES,
    PluginManifest,
    describe_permissions,
)


IGNORED_DIGEST_NAMES = {"__pycache__", ".DS_Store", ".git"}
IGNORED_DIGEST_SUFFIXES = {".pyc", ".pyo"}
RISK_ORDER = {"low": 1, "medium": 2, "high": 3, "unknown": 4}


@dataclass(frozen=True)
class PluginTrustReport:
    source_digest: Optional[str]
    review_status: str
    signature_status: str
    registry_status: str
    risk_level: str
    install_recommendation: str
    warnings: list[str]
    local_only: bool = True
    remote_code_downloads_allowed: bool = False
    entrypoints_executed_during_install: bool = False
    raw_secrets_allowed: bool = False

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


def compute_plugin_source_digest(plugin_dir: Path) -> Optional[str]:
    """Return a stable SHA-256 digest for install-relevant plugin files."""

    root = plugin_dir.resolve()
    if not root.exists() or not root.is_dir():
        return None
    files = sorted(
        path
        for path in root.rglob("*")
        if _should_include_in_digest(root, path)
    )
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def assess_plugin_trust(
    plugin_dir: Path,
    manifest: Optional[PluginManifest],
    *,
    registry_entry: Optional[Mapping[str, object]] = None,
    trusted_registry_keys: Optional[Mapping[str, Mapping[str, object]]] = None,
) -> PluginTrustReport:
    source_digest = compute_plugin_source_digest(plugin_dir)
    if manifest is None:
        return PluginTrustReport(
            source_digest=source_digest,
            review_status="invalid_manifest",
            signature_status="unknown",
            registry_status="not_listed",
            risk_level="unknown",
            install_recommendation="do_not_install",
            warnings=["Manifest is invalid or missing; installation is blocked."],
        )

    permission_details = describe_permissions(manifest.permissions)
    risk_level = _highest_risk([detail.risk for detail in permission_details])
    review_status = manifest.review.status if manifest.review else "unreviewed"
    registry_status, signature_status, registry_blocks_install, registry_warnings = (
        _assess_registry_entry(
            manifest,
            source_digest,
            registry_entry,
            trusted_registry_keys or {},
        )
    )
    if signature_status == "unsigned":
        signature_status = "metadata_only" if manifest.signature else "unsigned"
    warnings: list[str] = []

    if review_status != "maintainer_reviewed":
        warnings.append("Maintainer review metadata is not present.")
    if signature_status == "unsigned":
        warnings.append("Plugin is unsigned.")
    elif signature_status == "metadata_only":
        warnings.append("Signature metadata is present but not cryptographically verified.")
    warnings.extend(registry_warnings)
    high_risk_permissions = [
        detail.permission for detail in permission_details if detail.risk == "high"
    ]
    if high_risk_permissions:
        warnings.append(
            "High-risk permissions requested: " + ", ".join(sorted(high_risk_permissions)) + "."
        )

    install_recommendation = "allow_with_confirmation"
    if risk_level == "high" and review_status != "maintainer_reviewed":
        install_recommendation = "review_required"
    if registry_blocks_install:
        install_recommendation = "do_not_install"

    return PluginTrustReport(
        source_digest=source_digest,
        review_status=review_status,
        signature_status=signature_status,
        registry_status=registry_status,
        risk_level=risk_level,
        install_recommendation=install_recommendation,
        warnings=warnings,
    )


def plugin_trust_policy() -> dict[str, object]:
    return {
        "schema_version": "plugin-trust-v1",
        "local_first": True,
        "remote_code_downloads_allowed": False,
        "entrypoints_executed_during_install": False,
        "raw_secrets_allowed": False,
        "review_statuses": sorted(ALLOWED_REVIEW_STATUSES),
        "signature_statuses": [
            "unsigned",
            "metadata_only",
            "registry_digest_verified",
            "registry_signature_verified",
            "registry_signature_invalid",
            "registry_signature_unverified",
        ],
        "registry_statuses": [
            "not_listed",
            "digest_verified",
            "digest_mismatch",
            "missing_digest",
        ],
        "registry_signature": {
            "supported_type": "ed25519",
            "payload": "study-anything-plugin-registry-v1\\n<plugin_id>\\n<version>\\n<source_digest>\\n",
        },
        "risk_levels": ["low", "medium", "high", "unknown"],
        "install_recommendations": [
            "allow_with_confirmation",
            "review_required",
            "do_not_install",
        ],
        "notes": [
            "Plugins are installed only from explicitly selected local directories.",
            "Study Anything does not store model keys or agent secrets for plugins.",
            "Registry Ed25519 signatures are verified when a local registry provides trusted public keys.",
            "Registry review reads metadata only and does not download, update, or execute plugin code.",
            "High-risk plugins should be reviewed before installation.",
        ],
    }


def plugin_registry_signature_payload(plugin_id: str, version: str, source_digest: str) -> bytes:
    return (
        "study-anything-plugin-registry-v1\n"
        + plugin_id
        + "\n"
        + version
        + "\n"
        + source_digest
        + "\n"
    ).encode("utf-8")


def _assess_registry_entry(
    manifest: PluginManifest,
    source_digest: Optional[str],
    registry_entry: Optional[Mapping[str, object]],
    trusted_registry_keys: Mapping[str, Mapping[str, object]],
) -> tuple[str, str, bool, list[str]]:
    if registry_entry is None:
        return "not_listed", "unsigned", False, []

    expected_digest = _string_field(registry_entry, "sourceDigest")
    if not expected_digest:
        return (
            "missing_digest",
            "registry_signature_unverified",
            True,
            ["Registry entry is missing sourceDigest; installation should not proceed."],
        )
    if source_digest != expected_digest:
        return (
            "digest_mismatch",
            "registry_signature_invalid",
            True,
            ["Registry sourceDigest does not match the selected plugin directory."],
        )

    signature = registry_entry.get("signature")
    if not isinstance(signature, Mapping):
        return (
            "digest_verified",
            "registry_digest_verified",
            False,
            ["Registry digest matches, but no cryptographic registry signature is present."],
        )

    signature_type = _string_field(signature, "type")
    key_id = _string_field(signature, "keyId")
    signature_value = _string_field(signature, "value")
    key = trusted_registry_keys.get(key_id or "")
    if signature_type != "ed25519" or not key_id or not signature_value or key is None:
        return (
            "digest_verified",
            "registry_signature_unverified",
            True,
            ["Registry signature is present but cannot be verified with a trusted Ed25519 key."],
        )
    if _string_field(key, "type") != "ed25519":
        return (
            "digest_verified",
            "registry_signature_unverified",
            True,
            ["Registry trusted key is not an Ed25519 key."],
        )

    public_key_value = _string_field(key, "publicKey")
    if not public_key_value:
        return (
            "digest_verified",
            "registry_signature_unverified",
            True,
            ["Registry trusted key is missing publicKey."],
        )
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_value))
        public_key.verify(
            base64.b64decode(signature_value),
            plugin_registry_signature_payload(manifest.plugin_id, manifest.version, source_digest),
        )
    except (InvalidSignature, ValueError) as exc:
        return (
            "digest_verified",
            "registry_signature_invalid",
            True,
            [f"Registry signature verification failed: {exc.__class__.__name__}."],
        )
    return "digest_verified", "registry_signature_verified", False, []


def _string_field(values: Mapping[str, object], key: str) -> Optional[str]:
    value = values.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _should_include_in_digest(root: Path, path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    relative = path.relative_to(root)
    if any(part in IGNORED_DIGEST_NAMES for part in relative.parts):
        return False
    return path.suffix not in IGNORED_DIGEST_SUFFIXES


def _highest_risk(risks: list[str]) -> str:
    highest = "low"
    for risk in risks:
        if RISK_ORDER.get(risk, RISK_ORDER["unknown"]) > RISK_ORDER[highest]:
            highest = risk
    return highest
