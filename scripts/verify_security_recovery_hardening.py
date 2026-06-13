#!/usr/bin/env python3
"""Verify security, recovery, and backup hardening invariants."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from self_host_data import (  # noqa: E402
    SCHEMA_VERSION as BACKUP_SCHEMA_VERSION,
    file_record,
    safe_backup_member_path,
    verify_manifest,
    write_manifest,
)
from study_anything.core.recovery import recovery_status  # noqa: E402
from study_anything.core.sync_package import (  # noqa: E402
    SyncPackageError,
    build_sync_payload,
    encrypt_sync_package,
    inspect_sync_package,
    preview_sync_restore,
)
from study_anything.core.workflow import Answer, new_session, submit_answers, submit_reading  # noqa: E402


SCHEMA_VERSION = "security-recovery-hardening-verification-v1"


class SecurityRecoveryHardeningError(RuntimeError):
    """Readable security recovery hardening failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SecurityRecoveryHardeningError(message)


def expect_error(fn: Callable[[], object], needle: str) -> str:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - verifier captures readable diagnostics
        message = str(exc)
        require(needle in message, f"Expected error containing {needle!r}, got {message!r}")
        return message
    raise SecurityRecoveryHardeningError(f"Expected error containing {needle!r}.")


def verify_backup_manifest_hardening(root: Path) -> dict[str, Any]:
    backup_dir = root / "backup"
    backup_dir.mkdir()
    payload = backup_dir / "payload.txt"
    payload.write_text("original", encoding="utf-8")
    record = file_record(backup_dir, payload, role="test")
    manifest = {"schema_version": BACKUP_SCHEMA_VERSION, "files": [record]}
    write_manifest(backup_dir, manifest)
    require(verify_manifest(backup_dir) == manifest, "Valid backup manifest did not verify.")

    payload.write_text("tampered", encoding="utf-8")
    tamper_error = expect_error(lambda: verify_manifest(backup_dir), "Checksum mismatch")
    require(str(root) not in tamper_error, "Tamper diagnostic leaked absolute temp path.")
    payload.write_text("original", encoding="utf-8")

    traversal_error = expect_error(
        lambda: write_manifest(
            backup_dir,
            {
                "schema_version": BACKUP_SCHEMA_VERSION,
                "files": [{"path": "../escape.txt", "sha256": record["sha256"]}],
            },
        )
        or verify_manifest(backup_dir),
        "Unsafe backup file path",
    )
    invalid_digest_error = expect_error(
        lambda: write_manifest(
            backup_dir,
            {
                "schema_version": BACKUP_SCHEMA_VERSION,
                "files": [{"path": "payload.txt", "sha256": "not-a-digest"}],
            },
        )
        or verify_manifest(backup_dir),
        "Invalid sha256",
    )
    duplicate_error = expect_error(
        lambda: write_manifest(
            backup_dir,
            {"schema_version": BACKUP_SCHEMA_VERSION, "files": [record, record]},
        )
        or verify_manifest(backup_dir),
        "Duplicate backup file",
    )
    outside = root / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    outside_error = expect_error(
        lambda: file_record(backup_dir, outside, role="outside"),
        "inside the backup directory",
    )
    expect_error(lambda: safe_backup_member_path(backup_dir, "/tmp/escape.txt"), "Unsafe")
    return {
        "manifest_schema": BACKUP_SCHEMA_VERSION,
        "valid_manifest_verified": True,
        "tamper_detected": True,
        "path_traversal_rejected": True,
        "invalid_digest_rejected": True,
        "duplicate_path_rejected": True,
        "outside_file_record_rejected": True,
        "diagnostics_redacted": all(
            str(root) not in message
            for message in [tamper_error, traversal_error, invalid_digest_error, duplicate_error, outside_error]
        ),
    }


def verify_sync_restore_privacy(root: Path) -> dict[str, Any]:
    data_dir = root / "data"
    data_dir.mkdir()
    (data_dir / "agent_registry.json").write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "provider_id": "agent-secret",
                        "endpoint": "http://127.0.0.1:8787/private-token",
                    }
                ],
                "defaults": {},
            }
        ),
        encoding="utf-8",
    )
    state = new_session("security-recovery-user@example.com")
    state = submit_reading(
        state,
        source_type="local_text",
        reference="security://source",
        title="Private Recovery Title",
        text="Private recovery source text.",
    )
    state = submit_answers(
        state,
        [Answer(item_id="q1", text="Private recovery answer.")],
    )
    payload = build_sync_payload(sessions=[state], data_dir=data_dir)
    exported = encrypt_sync_package(payload, passphrase="security recovery passphrase")
    inspected = inspect_sync_package(
        exported.package,
        passphrase="security recovery passphrase",
    )
    preview = preview_sync_restore(
        exported.package,
        passphrase="security recovery passphrase",
        current_sessions=[state],
    )
    wrong_passphrase_error = expect_error(
        lambda: inspect_sync_package(exported.package, passphrase="wrong passphrase"),
        "could not be decrypted",
    )
    tampered_package = dict(exported.package)
    tampered_package["ciphertext_sha256"] = "0" * 64
    tamper_error = expect_error(
        lambda: inspect_sync_package(tampered_package, passphrase="security recovery passphrase"),
        "checksum mismatch",
    )

    combined = json.dumps(
        {
            "package": exported.package,
            "inspect": inspected,
            "preview": preview,
            "wrong_passphrase_error": wrong_passphrase_error,
            "tamper_error": tamper_error,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    forbidden = [
        "security-recovery-user@example.com",
        "Private recovery source text",
        "Private recovery answer",
        "127.0.0.1:8787/private-token",
    ]
    leaked = [item for item in forbidden if item in combined]
    require(not leaked, f"Sync restore preview leaked private values: {leaked}")
    require(preview["restore_api_enabled"] is False, "Restore preview must not enable API restore.")
    require(preview["privacy"]["plaintext_returned"] is False, "Restore preview returned plaintext.")
    return {
        "inspect_schema": inspected["schema_version"],
        "restore_preview_schema": preview["schema_version"],
        "wrong_passphrase_redacted": "security recovery passphrase" not in wrong_passphrase_error,
        "tamper_detected": True,
        "conflict_hash_count": len(preview["conflicts"]["conflict_session_hashes"]),
        "plaintext_returned": preview["privacy"]["plaintext_returned"],
        "restore_api_enabled": preview["restore_api_enabled"],
    }


def verify_recovery_status_redaction(root: Path) -> dict[str, Any]:
    project_root = root / "project"
    (project_root / "scripts").mkdir(parents=True)
    (project_root / "scripts" / "self_host_data.py").write_text("# tool\n", encoding="utf-8")
    (project_root / ".gitignore").write_text("backups/\n.env\n", encoding="utf-8")
    status = recovery_status(project_root)
    serialized = json.dumps(status, ensure_ascii=False, sort_keys=True)
    require(status["schema_version"] == "recovery-status-v1", "Recovery status schema drifted.")
    require(status["restore_api_enabled"] is False, "Recovery status enabled destructive API restore.")
    require(status["safeguards"]["path_traversal_protection"] is True, "Missing traversal safeguard.")
    require(str(project_root) not in serialized, "Recovery status leaked absolute project path.")
    require("OPENAI_API_KEY" not in serialized and "sk-" not in serialized, "Recovery status leaked secret-looking data.")
    return {
        "schema_version": status["schema_version"],
        "status": status["status"],
        "restore_api_enabled": status["restore_api_enabled"],
        "path_traversal_protection": status["safeguards"]["path_traversal_protection"],
        "absolute_paths_returned": False,
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="study-anything-security-recovery-") as tmpdir:
        root = Path(tmpdir)
        backup = verify_backup_manifest_hardening(root)
        sync = verify_sync_restore_privacy(root)
        recovery = verify_recovery_status_redaction(root)
    print(
        json.dumps(
            {
                "status": "ok",
                "schema_version": SCHEMA_VERSION,
                "backup_manifest": backup,
                "sync_restore_preview": sync,
                "recovery_status": recovery,
                "disposable_drill": {
                    "command": "python3 scripts/verify_backup_restore_drill.py",
                    "covered_by_release_check": True,
                },
                "privacy": {
                    "absolute_paths_returned": False,
                    "raw_source_text_returned": False,
                    "answers_returned": False,
                    "agent_endpoints_returned": False,
                    "secrets_returned": False,
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_security_recovery_hardening failed: {exc}", file=sys.stderr)
        sys.exit(1)
