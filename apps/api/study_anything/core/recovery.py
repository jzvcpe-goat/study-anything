"""Read-only backup and restore readiness for self-host operators."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _gitignore_includes_backups(root: Path) -> bool:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return False
    entries = {
        line.strip()
        for line in gitignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    return "backups/" in entries or "backups" in entries


def recovery_status(project_root: Path) -> dict[str, Any]:
    """Return public recovery readiness without running backup or restore commands."""

    script_exists = (project_root / "scripts" / "self_host_data.py").exists()
    backups_gitignored = _gitignore_includes_backups(project_root)
    ready = script_exists and backups_gitignored
    return {
        "schema_version": "recovery-status-v1",
        "status": "ready" if ready else "needs_attention",
        "local_only": True,
        "backup_supported": script_exists,
        "restore_supported": script_exists,
        "restore_api_enabled": False,
        "restore_requires_confirmation": True,
        "destructive_restore": True,
        "backup_root": "backups/",
        "commands": {
            "backup": "python3 scripts/self_host_data.py backup",
            "backup_include_optional": "python3 scripts/self_host_data.py backup --include-optional",
            "restore": "python3 scripts/self_host_data.py restore backups/study-anything-backup-YYYYmmddTHHMMSSZ --yes",
        },
        "coverage": {
            "canonical_postgres": True,
            "study_anything_data_volume": True,
            "agent_configuration": True,
            "local_plugins": True,
            "env_snapshot": True,
            "optional_service_volumes": "opt_in",
        },
        "safeguards": {
            "sha256_manifest": True,
            "restore_requires_yes": True,
            "restore_env_preserved_by_default": True,
            "path_traversal_protection": True,
            "backups_gitignored": backups_gitignored,
        },
        "privacy": {
            "contains_private_learning_data": True,
            "contains_env_snapshot": True,
            "raw_secrets_may_be_present": True,
            "commit_safe": False,
            "encrypt_at_rest_required": True,
        },
        "notes": [
            "Backups are local artifacts and can include private learning data and environment secrets.",
            "Restore is intentionally explicit and destructive; the public API never triggers it.",
        ],
    }
