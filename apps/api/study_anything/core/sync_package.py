"""Encrypted local sync packages for self-host Study Anything installs.

This is the local-first foundation for future paid Study Sync convenience
services. The API never stores passphrases and the package envelope never
contains source text, answers, Agent endpoints, or raw user identifiers in
plaintext.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .events import utc_now
from .plugin_registry import PluginStatus
from .workflow import LearningState


SYNC_PACKAGE_SCHEMA_VERSION = "sync-package-v1"
SYNC_PAYLOAD_SCHEMA_VERSION = "sync-payload-v1"
KDF_NAME = "pbkdf2-sha256"
CIPHER_NAME = "AES-256-GCM"
KDF_ITERATIONS = 390_000
MIN_PASSPHRASE_LENGTH = 12


class SyncPackageError(ValueError):
    """Raised when a sync package cannot be built or inspected."""


@dataclass(frozen=True)
class SyncPayloadSummary:
    session_count: int
    agent_provider_count: int
    workspace_count: int
    pmf_interest_count: int
    plugin_inventory_count: int
    includes_agent_registry: bool
    includes_workspace_state: bool
    includes_pmf_interests: bool
    includes_plugin_inventory: bool

    def public_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EncryptedSyncExport:
    package: dict[str, Any]
    payload_summary: SyncPayloadSummary
    size_bytes: int

    def public_dict(self) -> dict[str, object]:
        return {
            "schema_version": SYNC_PACKAGE_SCHEMA_VERSION,
            "package": self.package,
            "payload_summary": self.payload_summary.public_dict(),
            "size_bytes": self.size_bytes,
            "privacy": sync_privacy_boundary(),
        }


def sync_status() -> dict[str, object]:
    return {
        "schema_version": "sync-status-v1",
        "status": "local_foundation_ready",
        "encrypted_package_supported": True,
        "hosted_sync_enabled": False,
        "raw_passphrase_stored": False,
        "local_first": True,
        "commercial_boundary": {
            "accounts_enabled": False,
            "billing_enabled": False,
            "remote_storage_enabled": False,
            "conflict_resolution": "planned",
        },
    }


def sync_privacy_boundary() -> dict[str, object]:
    return {
        "encrypted": True,
        "cipher": CIPHER_NAME,
        "raw_passphrase_stored": False,
        "hosted_upload": False,
        "plaintext_excluded_from_envelope": [
            "raw_user_id",
            "source_text",
            "source_title",
            "quiz_prompts",
            "answers",
            "grading_feedback",
            "insights",
            "scribe_log",
            "agent_endpoint",
            "agent_metadata",
            "plugin_source_code",
        ],
    }


def build_sync_payload(
    *,
    sessions: Iterable[LearningState],
    data_dir: Path,
    plugin_statuses: Iterable[PluginStatus] = (),
    include_pmf: bool = True,
    include_plugin_inventory: bool = True,
    created_at: Optional[str] = None,
) -> dict[str, Any]:
    agent_registry = _read_json(data_dir / "agent_registry.json")
    workspace_state = _read_json(data_dir / "workspace_state.json")
    pmf_interests = _read_json(data_dir / "pmf_interests.json") if include_pmf else None
    plugin_inventory = (
        [status.public_dict() for status in plugin_statuses]
        if include_plugin_inventory
        else []
    )
    session_payloads = [asdict(state) for state in sessions]
    summary = _summarize_payload(
        sessions=session_payloads,
        agent_registry=agent_registry,
        workspace_state=workspace_state,
        pmf_interests=pmf_interests,
        plugin_inventory=plugin_inventory,
        include_pmf=include_pmf,
        include_plugin_inventory=include_plugin_inventory,
    )
    return {
        "schema_version": SYNC_PAYLOAD_SCHEMA_VERSION,
        "created_at": created_at or utc_now(),
        "app": "study-anything",
        "summary": summary.public_dict(),
        "privacy": {
            "encrypted_at_rest": True,
            "raw_passphrase_stored": False,
            "restore_api_enabled": False,
        },
        "data": {
            "sessions": session_payloads,
            "agent_registry": agent_registry,
            "workspace_state": workspace_state,
            "pmf_interests": pmf_interests,
            "plugin_inventory": plugin_inventory,
        },
    }


def encrypt_sync_package(
    payload: Mapping[str, Any],
    *,
    passphrase: str,
    created_at: Optional[str] = None,
) -> EncryptedSyncExport:
    _require_passphrase(passphrase)
    plaintext = _canonical_json(payload)
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(passphrase, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    package = {
        "schema_version": SYNC_PACKAGE_SCHEMA_VERSION,
        "created_at": created_at or utc_now(),
        "kdf": {
            "name": KDF_NAME,
            "iterations": KDF_ITERATIONS,
            "salt": _b64encode(salt),
        },
        "cipher": {
            "name": CIPHER_NAME,
            "nonce": _b64encode(nonce),
        },
        "ciphertext": _b64encode(ciphertext),
        "ciphertext_sha256": hashlib.sha256(ciphertext).hexdigest(),
        "privacy": sync_privacy_boundary(),
    }
    payload_summary = _summary_from_payload(payload)
    return EncryptedSyncExport(
        package=package,
        payload_summary=payload_summary,
        size_bytes=len(_canonical_json(package)),
    )


def decrypt_sync_package(package: Mapping[str, Any], *, passphrase: str) -> dict[str, Any]:
    _require_passphrase(passphrase, allow_short=True)
    try:
        if package.get("schema_version") != SYNC_PACKAGE_SCHEMA_VERSION:
            raise SyncPackageError("Unsupported sync package schema version.")
        kdf = _require_mapping(package.get("kdf"), "kdf")
        cipher = _require_mapping(package.get("cipher"), "cipher")
        if kdf.get("name") != KDF_NAME:
            raise SyncPackageError("Unsupported sync package KDF.")
        if cipher.get("name") != CIPHER_NAME:
            raise SyncPackageError("Unsupported sync package cipher.")
        salt = _b64decode(_require_string(kdf.get("salt"), "kdf.salt"))
        nonce = _b64decode(_require_string(cipher.get("nonce"), "cipher.nonce"))
        ciphertext = _b64decode(_require_string(package.get("ciphertext"), "ciphertext"))
        checksum = package.get("ciphertext_sha256")
        if isinstance(checksum, str) and hashlib.sha256(ciphertext).hexdigest() != checksum:
            raise SyncPackageError("Sync package ciphertext checksum mismatch.")
        iterations = int(kdf.get("iterations", 0))
        if iterations <= 0:
            raise SyncPackageError("Sync package KDF iterations are invalid.")
        key = _derive_key(passphrase, salt, iterations=iterations)
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
        payload = json.loads(plaintext.decode("utf-8"))
    except SyncPackageError:
        raise
    except (InvalidTag, binascii.Error, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise SyncPackageError("Sync package could not be decrypted or validated.") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != SYNC_PAYLOAD_SCHEMA_VERSION:
        raise SyncPackageError("Unsupported sync payload schema version.")
    return payload


def inspect_sync_package(package: Mapping[str, Any], *, passphrase: str) -> dict[str, object]:
    payload = decrypt_sync_package(package, passphrase=passphrase)
    return {
        "schema_version": "sync-inspect-v1",
        "package_schema_version": package.get("schema_version"),
        "payload_schema_version": payload.get("schema_version"),
        "created_at": payload.get("created_at"),
        "payload_summary": _summary_from_payload(payload).public_dict(),
        "privacy": {
            "plaintext_returned": False,
            "restore_api_enabled": False,
            "raw_passphrase_stored": False,
        },
    }


def _summarize_payload(
    *,
    sessions: list[Mapping[str, Any]],
    agent_registry: Any,
    workspace_state: Any,
    pmf_interests: Any,
    plugin_inventory: list[Mapping[str, Any]],
    include_pmf: bool,
    include_plugin_inventory: bool,
) -> SyncPayloadSummary:
    return SyncPayloadSummary(
        session_count=len(sessions),
        agent_provider_count=_agent_provider_count(agent_registry),
        workspace_count=_workspace_count(workspace_state),
        pmf_interest_count=_pmf_interest_count(pmf_interests),
        plugin_inventory_count=len(plugin_inventory),
        includes_agent_registry=agent_registry is not None,
        includes_workspace_state=workspace_state is not None,
        includes_pmf_interests=include_pmf and pmf_interests is not None,
        includes_plugin_inventory=include_plugin_inventory,
    )


def _summary_from_payload(payload: Mapping[str, Any]) -> SyncPayloadSummary:
    summary = payload.get("summary")
    if isinstance(summary, Mapping):
        return SyncPayloadSummary(
            session_count=int(summary.get("session_count", 0)),
            agent_provider_count=int(summary.get("agent_provider_count", 0)),
            workspace_count=int(summary.get("workspace_count", 0)),
            pmf_interest_count=int(summary.get("pmf_interest_count", 0)),
            plugin_inventory_count=int(summary.get("plugin_inventory_count", 0)),
            includes_agent_registry=bool(summary.get("includes_agent_registry", False)),
            includes_workspace_state=bool(summary.get("includes_workspace_state", False)),
            includes_pmf_interests=bool(summary.get("includes_pmf_interests", False)),
            includes_plugin_inventory=bool(summary.get("includes_plugin_inventory", False)),
        )
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return SyncPayloadSummary(
            session_count=0,
            agent_provider_count=0,
            workspace_count=0,
            pmf_interest_count=0,
            plugin_inventory_count=0,
            includes_agent_registry=False,
            includes_workspace_state=False,
            includes_pmf_interests=False,
            includes_plugin_inventory=False,
        )
    sessions = data.get("sessions", [])
    plugin_inventory = data.get("plugin_inventory", [])
    return _summarize_payload(
        sessions=list(sessions) if isinstance(sessions, list) else [],
        agent_registry=data.get("agent_registry"),
        workspace_state=data.get("workspace_state"),
        pmf_interests=data.get("pmf_interests"),
        plugin_inventory=list(plugin_inventory) if isinstance(plugin_inventory, list) else [],
        include_pmf=data.get("pmf_interests") is not None,
        include_plugin_inventory=isinstance(plugin_inventory, list),
    )


def _agent_provider_count(agent_registry: Any) -> int:
    if not isinstance(agent_registry, Mapping):
        return 0
    providers = agent_registry.get("providers", [])
    return len(providers) if isinstance(providers, list) else 0


def _workspace_count(workspace_state: Any) -> int:
    if not isinstance(workspace_state, Mapping):
        return 0
    workspaces = workspace_state.get("workspaces", {})
    if isinstance(workspaces, Mapping):
        return len(workspaces)
    if isinstance(workspaces, list):
        return len(workspaces)
    return 0


def _pmf_interest_count(pmf_interests: Any) -> int:
    if isinstance(pmf_interests, list):
        return len(pmf_interests)
    return 0


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json(values: Mapping[str, Any]) -> bytes:
    return json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _derive_key(
    passphrase: str,
    salt: bytes,
    *,
    iterations: int = KDF_ITERATIONS,
) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    ).derive(passphrase.encode("utf-8"))


def _require_passphrase(passphrase: str, *, allow_short: bool = False) -> None:
    if not passphrase:
        raise SyncPackageError("A sync package passphrase is required.")
    if not allow_short and len(passphrase) < MIN_PASSPHRASE_LENGTH:
        raise SyncPackageError(
            f"Sync package passphrase must be at least {MIN_PASSPHRASE_LENGTH} characters."
        )


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SyncPackageError(f"Sync package field '{field_name}' must be an object.")
    return value


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise SyncPackageError(f"Sync package field '{field_name}' must be a non-empty string.")
    return value


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))
