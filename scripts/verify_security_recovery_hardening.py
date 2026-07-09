#!/usr/bin/env python3
"""Verify security, recovery, and backup hardening invariants."""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))


SCHEMA_VERSION = "security-recovery-hardening-verification-v1"
MIN_PYTHON = (3, 11)


def python_version_error_payload(version: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": "security-recovery-hardening-error-v1",
        "status": "blocked",
        "classification": "python_version_unsupported",
        "diagnostic": "verify_security_recovery_hardening requires Python 3.11 or newer.",
        "python_version": version or sys.version.split()[0],
        "next_steps": [
            ".venv/bin/python scripts/verify_security_recovery_hardening.py",
            "python3 scripts/setup_env.py",
            "./scripts/run_skill_mode_demo.sh",
        ],
        "privacy": {
            "local_absolute_paths_included": False,
            "secrets_recorded": False,
        },
    }


def ensure_supported_python() -> None:
    if sys.version_info >= MIN_PYTHON:
        return
    print(
        json.dumps(
            python_version_error_payload(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    raise SystemExit(1)


ensure_supported_python()

from self_host_data import (  # noqa: E402
    SCHEMA_VERSION as BACKUP_SCHEMA_VERSION,
    file_record,
    safe_backup_member_path,
    verify_manifest,
    write_manifest,
)
from study_anything.core.recovery import recovery_status  # noqa: E402
from study_anything.core.sync_package import (  # noqa: E402
    build_sync_payload,
    encrypt_sync_package,
    inspect_sync_package,
    preview_sync_restore,
)
from study_anything.core.workflow import Answer, new_session, submit_answers, submit_reading  # noqa: E402


PRIVATE_USER = "security-recovery-user@example.com"
PRIVATE_SOURCE_TEXT = "Private recovery source text."
PRIVATE_ANSWER = "Private recovery answer."
PRIVATE_TITLE = "Private Recovery Title"
PRIVATE_ENDPOINT = "http://127.0.0.1:8787/private-token"
PRIVATE_PASSPHRASE = "security recovery passphrase"
FORBIDDEN_LITERALS = (
    PRIVATE_USER,
    PRIVATE_SOURCE_TEXT,
    PRIVATE_ANSWER,
    PRIVATE_TITLE,
    PRIVATE_ENDPOINT,
    PRIVATE_PASSPHRASE,
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
)


class SecurityRecoveryHardeningError(RuntimeError):
    """Readable security recovery hardening failure."""


def sanitize_text(value: str | bytes | None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    replacements = {
        PRIVATE_USER: "<private-user>",
        PRIVATE_SOURCE_TEXT: "<private-source-text>",
        PRIVATE_ANSWER: "<private-answer>",
        PRIVATE_TITLE: "<private-title>",
        PRIVATE_ENDPOINT: "<private-agent-endpoint>",
        PRIVATE_PASSPHRASE: "<private-passphrase>",
    }
    for literal, replacement in replacements.items():
        text = text.replace(literal, replacement)
    text = re.sub(r"(?i)private recovery source text[^\"'\n.]*\.?", "<private-source-text>", text)
    text = re.sub(r"(?i)private recovery answer[^\"'\n.]*\.?", "<private-answer>", text)
    text = re.sub(r"(?i)security recovery passphrase", "<private-passphrase>", text)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", text)
    text = re.sub(r"/Users/[^\s\"'?&]+", "<local-path>", text)
    text = re.sub(r"/private/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"/tmp/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", r"\1=<redacted>", text)
    text = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "sk-<redacted>", text)
    text = re.sub(r"([?&](?:api[_-]?key|token|secret)=)[^&\s\"']+", r"\1<redacted>", text, flags=re.IGNORECASE)
    return text.strip()[:1600]


def classify_failure(message: str) -> str:
    lowered = message.lower()
    if "no module named" in lowered or "importerror" in lowered:
        return "dependency_missing"
    if (
        "backup manifest" in lowered
        or "checksum mismatch" in lowered
        or "unsafe backup file path" in lowered
        or "invalid sha256" in lowered
        or "duplicate backup file" in lowered
        or "inside the backup directory" in lowered
    ):
        return "backup_manifest_hardening_failed"
    if (
        "sync restore" in lowered
        or "restore preview" in lowered
        or "passphrase" in lowered
        or "could not be decrypted" in lowered
        or "plaintext" in lowered
        or "ciphertext" in lowered
    ):
        return "sync_restore_privacy_failed"
    if "recovery status" in lowered or "destructive api restore" in lowered or "traversal safeguard" in lowered:
        return "recovery_status_failed"
    if "leaked" in lowered or "private" in lowered or "secret-looking" in lowered:
        return "privacy_leak"
    return "security_recovery_hardening_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "python3 scripts/verify_security_recovery_hardening.py",
        "python3 scripts/diagnose_adoption.py",
        "python3 scripts/verify_backup_restore_drill.py",
    ]
    matrix = {
        "dependency_missing": [
            "Run `python3 scripts/setup_env.py` to prepare the local Python environment.",
            "Use `.venv/bin/python` if your system Python does not have the project dependencies.",
        ],
        "backup_manifest_hardening_failed": [
            "Inspect `scripts/self_host_data.py` backup manifest validation.",
            "Do not trust backups until checksum, path traversal, digest, and duplicate-path checks pass.",
        ],
        "sync_restore_privacy_failed": [
            "Inspect `study_anything.core.sync_package` encryption, inspect, and restore-preview paths.",
            "Restore preview must stay non-destructive and must not return plaintext.",
        ],
        "recovery_status_failed": [
            "Inspect `study_anything.core.recovery.recovery_status`.",
            "Recovery status must not expose destructive restore APIs or absolute project paths.",
        ],
        "privacy_leak": [
            "Do not share the raw transcript publicly.",
            "Fix the leaking recovery/sync/backup diagnostic before using this run as evidence.",
        ],
    }
    return matrix.get(classification, ["Rerun the security recovery verifier after fixing the reported invariant."]) + common


def failure_report(exc: BaseException) -> dict[str, Any]:
    diagnostic = sanitize_text(str(exc))
    classification = classify_failure(diagnostic)
    report = {
        "status": "blocked",
        "classification": classification,
        "diagnostic": diagnostic,
        "next_steps": failure_next_steps(classification),
        "source": {
            "verifier": "verify_security_recovery_hardening",
            "schema_version": SCHEMA_VERSION,
        },
        "privacy": {
            "absolute_paths_included": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoints_included": False,
            "passphrases_included": False,
            "real_model_keys_included": False,
        },
    }
    assert_failure_report_redacted(report)
    return report


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"/private/(?:var/)?folders/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"/tmp/[^\s\"']+", serialized):
        leaks.append("tmp path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise SecurityRecoveryHardeningError(
            f"Security recovery failure report leaked private data: {leaks}"
        )


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
                        "endpoint": PRIVATE_ENDPOINT,
                    }
                ],
                "defaults": {},
            }
        ),
        encoding="utf-8",
    )
    state = new_session(PRIVATE_USER)
    state = submit_reading(
        state,
        source_type="local_text",
        reference="security://source",
        title=PRIVATE_TITLE,
        text=PRIVATE_SOURCE_TEXT,
    )
    state = submit_answers(
        state,
        [Answer(item_id="q1", text=PRIVATE_ANSWER)],
    )
    payload = build_sync_payload(sessions=[state], data_dir=data_dir)
    exported = encrypt_sync_package(payload, passphrase=PRIVATE_PASSPHRASE)
    inspected = inspect_sync_package(
        exported.package,
        passphrase=PRIVATE_PASSPHRASE,
    )
    preview = preview_sync_restore(
        exported.package,
        passphrase=PRIVATE_PASSPHRASE,
        current_sessions=[state],
    )
    wrong_passphrase_error = expect_error(
        lambda: inspect_sync_package(exported.package, passphrase="wrong passphrase"),
        "could not be decrypted",
    )
    tampered_package = dict(exported.package)
    tampered_package["ciphertext_sha256"] = "0" * 64
    tamper_error = expect_error(
        lambda: inspect_sync_package(tampered_package, passphrase=PRIVATE_PASSPHRASE),
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
        PRIVATE_USER,
        PRIVATE_SOURCE_TEXT,
        PRIVATE_ANSWER,
        PRIVATE_ENDPOINT,
    ]
    leaked = [item for item in forbidden if item in combined]
    require(not leaked, f"Sync restore preview leaked private values: {leaked}")
    require(preview["restore_api_enabled"] is False, "Restore preview must not enable API restore.")
    require(preview["privacy"]["plaintext_returned"] is False, "Restore preview returned plaintext.")
    return {
        "inspect_schema": inspected["schema_version"],
        "restore_preview_schema": preview["schema_version"],
        "wrong_passphrase_redacted": PRIVATE_PASSPHRASE not in wrong_passphrase_error,
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
        print(json.dumps(failure_report(exc), ensure_ascii=False, sort_keys=True))
        print(f"verify_security_recovery_hardening failed: {sanitize_text(str(exc))}", file=sys.stderr)
        sys.exit(1)
