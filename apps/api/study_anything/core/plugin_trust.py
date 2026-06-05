"""Local-first plugin trust summaries.

The alpha plugin layer never downloads remote code, executes entrypoints during
installation, or stores third-party secrets. This module gives users a compact
review surface for local plugins before copying them into the data directory.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

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


def assess_plugin_trust(plugin_dir: Path, manifest: Optional[PluginManifest]) -> PluginTrustReport:
    source_digest = compute_plugin_source_digest(plugin_dir)
    if manifest is None:
        return PluginTrustReport(
            source_digest=source_digest,
            review_status="invalid_manifest",
            signature_status="unknown",
            risk_level="unknown",
            install_recommendation="do_not_install",
            warnings=["Manifest is invalid or missing; installation is blocked."],
        )

    permission_details = describe_permissions(manifest.permissions)
    risk_level = _highest_risk([detail.risk for detail in permission_details])
    review_status = manifest.review.status if manifest.review else "unreviewed"
    signature_status = "metadata_only" if manifest.signature else "unsigned"
    warnings: list[str] = []

    if review_status != "maintainer_reviewed":
        warnings.append("Maintainer review metadata is not present.")
    if signature_status == "unsigned":
        warnings.append("Plugin is unsigned.")
    else:
        warnings.append("Signature metadata is present but not cryptographically verified.")
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

    return PluginTrustReport(
        source_digest=source_digest,
        review_status=review_status,
        signature_status=signature_status,
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
        "signature_statuses": ["unsigned", "metadata_only"],
        "risk_levels": ["low", "medium", "high", "unknown"],
        "install_recommendations": [
            "allow_with_confirmation",
            "review_required",
            "do_not_install",
        ],
        "notes": [
            "Plugins are installed only from explicitly selected local directories.",
            "Study Anything does not store model keys or agent secrets for plugins.",
            "Signature fields are manifest metadata until verification is implemented.",
            "High-risk plugins should be reviewed before installation.",
        ],
    }


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
