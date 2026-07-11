#!/usr/bin/env python3
"""Verify the CBB v1 conformance pack with a package-independent consumer."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_cbb_v1_conformance_pack import (  # noqa: E402
    ARCHIVE_ROOT,
    JSON_OUTPUT as PACK_SUMMARY_PATH,
    ZIP_OUTPUT,
    expected_outputs,
)


REPORT_PATH = ROOT / "platform" / "generated" / "study-anything-cbb-v1-external-consumer.json"
CONSUMER_PATH = ROOT / "conformance" / "python" / "cbb_v1_consumer.py"
FORBIDDEN_IMPORT_ROOTS = {
    "httpx",
    "langchain",
    "openai",
    "pydantic",
    "requests",
    "socket",
    "study_anything",
    "subprocess",
    "urllib",
}


def _json_bytes(value: dict[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if not members:
        raise ValueError("conformance archive is empty")
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("conformance archive contains unsafe path")
        if not path.parts or path.parts[0] != ARCHIVE_ROOT:
            raise ValueError("conformance archive must use one declared root")
        file_type = (member.external_attr >> 16) & 0o170000
        if file_type == 0o120000:
            raise ValueError("conformance archive cannot contain symlinks")
    return members


def _extract(archive_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive_path) as archive:
        _safe_members(archive)
        archive.extractall(destination)
    return destination / ARCHIVE_ROOT


def _consumer_imports() -> set[str]:
    tree = ast.parse(CONSUMER_PATH.read_text(encoding="utf-8"), filename=str(CONSUMER_PATH))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def _run_consumer(pack_root: Path) -> tuple[int, dict[str, Any], str]:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
    }
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            str(pack_root / "consumer" / "python" / "cbb_v1_consumer.py"),
            "--pack-root",
            str(pack_root),
        ],
        cwd=pack_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    return completed.returncode, payload, completed.stderr


def _archive_privacy_ok(archive_path: Path) -> bool:
    forbidden_names = ("private-key", "private_key", ".pem", ".key")
    forbidden_bytes = (
        b"-----BEGIN " + b"PRIVATE KEY-----",
        b"/" + b"Users/",
        b"/private/" + b"var/folders/",
    )
    with zipfile.ZipFile(archive_path) as archive:
        for member in _safe_members(archive):
            lower_name = member.filename.lower()
            if any(token in lower_name for token in forbidden_names):
                return False
            if member.is_dir():
                continue
            data = archive.read(member)
            if any(token in data for token in forbidden_bytes):
                return False
    return True


def build_report() -> dict[str, Any]:
    expected = expected_outputs()
    generated_current = all(path.exists() and path.read_bytes() == data for path, data in expected.items())
    summary = json.loads(PACK_SUMMARY_PATH.read_text(encoding="utf-8"))
    archive_sha = hashlib.sha256(ZIP_OUTPUT.read_bytes()).hexdigest()
    imports = _consumer_imports()

    with tempfile.TemporaryDirectory(prefix="cbb-v1-conformance-") as tmp:
        pack_root = _extract(ZIP_OUTPUT, Path(tmp) / "positive")
        positive_rc, positive, positive_stderr = _run_consumer(pack_root)

        tampered_root = _extract(ZIP_OUTPUT, Path(tmp) / "tampered")
        tampered_vector = tampered_root / "vectors" / "canonical-vectors.json"
        tampered_vector.write_bytes(tampered_vector.read_bytes() + b"\n")
        tampered_rc, tampered, tampered_stderr = _run_consumer(tampered_root)

    checks = {
        "pack_generated_current": generated_current,
        "archive_digest_matches_summary": archive_sha == summary["archive_sha256"],
        "archive_paths_safe": True,
        "archive_privacy_boundary": _archive_privacy_ok(ZIP_OUTPUT),
        "consumer_outside_study_package": CONSUMER_PATH.relative_to(ROOT).parts[0]
        == "conformance",
        "consumer_forbidden_imports_absent": not imports.intersection(FORBIDDEN_IMPORT_ROOTS),
        "consumer_runs_in_isolated_python": positive_rc == 0 and positive.get("status") == "pass",
        "consumer_covers_eight_schemas": positive.get("counts", {}).get("canonical_schemas") == 8,
        "consumer_verifies_canonical_vectors": positive.get("checks", {}).get(
            "canonical_vectors"
        )
        is True,
        "consumer_replays_trust_kernel": positive.get("checks", {}).get(
            "deterministic_kernel_vectors"
        )
        is True,
        "consumer_verifies_signatures_expiry_replay_revocation": positive.get(
            "checks", {}
        ).get("signed_provenance_vectors")
        is True,
        "consumer_replays_outcome_degradation": positive.get("checks", {}).get(
            "outcome_degradation_vectors"
        )
        is True,
        "consumer_replays_evolution_gate": positive.get("checks", {}).get(
            "evolution_gate_vectors"
        )
        is True,
        "consumer_rejects_authority_extensions": positive.get("checks", {}).get(
            "extension_authority_fail_closed"
        )
        is True,
        "consumer_negotiates_versions": positive.get("checks", {}).get(
            "version_negotiation"
        )
        is True,
        "consumer_preserves_v0_as_compatibility_only": positive.get("checks", {}).get(
            "v0_migration_narrows_only"
        )
        is True,
        "consumer_rejects_privacy_negatives": positive.get("checks", {}).get(
            "privacy_negative_vectors"
        )
        is True,
        "tampered_pack_fails_closed": tampered_rc != 0
        and tampered.get("status") == "fail"
        and "file_digests" in tampered.get("failed_checks", []),
        "consumer_stderr_clean": not positive_stderr and not tampered_stderr,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": "cbb-v1-external-consumer-verification-v1",
        "status": "pass" if not failed else "fail",
        "checks": checks,
        "failed_checks": failed,
        "consumer": {
            "implementation_id": positive.get("implementation", {}).get(
                "implementation_id"
            ),
            "language": "python",
            "imports": sorted(imports),
            "study_anything_imported": False,
            "isolated_mode": True,
        },
        "package": {
            "archive_sha256": archive_sha,
            "declared_file_count": summary["declared_file_count"],
            "archive_entry_count": summary["archive_entry_count"],
            "schema_count": summary["schema_count"],
            "vector_counts": summary["vector_counts"],
        },
        "claim_boundary": (
            "This proves local cross-implementation conformance against published "
            "fixtures. It does not create a certification authority, prove production "
            "safety, establish global revocation, guarantee customer outcomes, or "
            "complete an independent security audit."
        ),
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "production_mutation_performed": False,
            "private_keys_included": False,
            "local_absolute_paths_included": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    data = _json_bytes(report)
    if args.check:
        if not REPORT_PATH.exists() or REPORT_PATH.read_bytes() != data:
            print(
                "verify_cbb_v1_external_consumer failed: report is stale. "
                "Run `python3 scripts/verify_cbb_v1_external_consumer.py`.",
                file=sys.stderr,
            )
            return 1
        print(data.decode("utf-8"), end="")
        return 0 if report["status"] == "pass" else 1
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_bytes(data)
    print(f"wrote {REPORT_PATH.relative_to(ROOT)}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
