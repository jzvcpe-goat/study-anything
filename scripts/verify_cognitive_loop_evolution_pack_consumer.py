#!/usr/bin/env python3
"""Verify a Professional Evolution Pack from the ZIP alone."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from typing import Any, Mapping
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-evolution-pack-consumer.json"
SCHEMA_VERSION = "cognitive-loop-evolution-pack-consumer-v1"
MANIFEST_SCHEMA_VERSION = "cognitive-loop-evolution-pack-manifest-v1"
ARCHIVE_ROOT = "cognitive-loop-professional-evolution-pack"
EXPECTED_STATUSES = {"pack_ready", "manual_review", "blocked", "degraded_missing_artifacts"}

SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bdiff --git\b"),
    re.compile(r"http://127\.0\.0\.1:8787[^\s\"']*"),
    re.compile(r"/Users/[^\s\"']+"),
)
FORBIDDEN_LITERALS = (
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "learner answer:",
    "raw source text",
    "raw diff",
    "private source text",
    "agent endpoint:",
    "agent metadata:",
    "prompt:",
)
POLICY_WEAKENING_PHRASES = (
    "disable privacy",
    "skip privacy",
    "weaken privacy",
    "disable audit",
    "skip audit",
    "remove rollback",
    "skip rollback",
    "disable tests",
    "skip tests",
    "lower risk threshold",
    "weaken risk",
    "disable human gate",
    "bypass human gate",
    "loosen permissions",
)
FALSE_KEYS = (
    "source_text_included",
    "raw_source_text_included",
    "raw_diff_included",
    "diff_bodies_included",
    "file_contents_included",
    "learner_answers_included",
    "agent_endpoint_included",
    "agent_endpoints_included",
    "agent_metadata_included",
    "prompt_text_included",
    "real_model_keys_stored",
    "model_called",
    "daemon_started",
    "production_mastra_daemon_started",
    "mastra_workflow_started",
    "apply_executed",
    "raw_unified_diff_generated",
    "policy_weakened",
    "source_files_modified",
    "real_source_mutated",
)
PROTECTED_TARGET_FRAGMENTS = (
    ".env",
    ".pem",
    ".key",
    "secrets/",
    ".github/workflows/",
    ".cognitive-loop/permissions",
    ".cognitive-loop/risk",
)


class EvolutionPackConsumerError(RuntimeError):
    """Readable evolution-pack consumer failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def assert_no_private_text(text: str, *, label: str) -> None:
    lowered = text.lower()
    literals = [literal for literal in FORBIDDEN_LITERALS if literal.lower() in lowered]
    patterns = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
    weakening = [phrase for phrase in POLICY_WEAKENING_PHRASES if phrase in lowered]
    if literals or patterns or weakening:
        raise EvolutionPackConsumerError(
            f"{label} is not safe for public consumption: literals={literals} patterns={patterns} policy={weakening}"
        )


def assert_public_payload(payload: Any, *, label: str) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert_no_private_text(text, label=label)


def walk_mappings(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        found.append(value)
        for child in value.values():
            found.extend(walk_mappings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(walk_mappings(child))
    return found


def privacy_regressions(payload: Mapping[str, Any]) -> list[str]:
    regressions: list[str] = []
    for mapping in walk_mappings(payload):
        for key in FALSE_KEYS:
            if mapping.get(key) is True:
                regressions.append(key)
    return sorted(set(regressions))


def protected_path_hits(payload: Mapping[str, Any]) -> list[str]:
    hits: list[str] = []
    interesting_keys = {"target_path", "source_ref", "ref", "json_ref", "html_ref", "zip_ref"}
    for mapping in walk_mappings(payload):
        for key, value in mapping.items():
            if key not in interesting_keys or not isinstance(value, str):
                continue
            normalized = value.strip().replace("\\", "/").lstrip("/")
            lowered = normalized.lower()
            if any(fragment in lowered for fragment in PROTECTED_TARGET_FRAGMENTS):
                hits.append(normalized)
    return sorted(set(hits))


def assert_safe_zip_member(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise EvolutionPackConsumerError(f"Unsafe ZIP member path: {name}")
    if not name.startswith(f"{ARCHIVE_ROOT}/"):
        raise EvolutionPackConsumerError(f"ZIP member is outside archive root: {name}")


def read_json_member(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        raw = archive.read(name)
    except KeyError as exc:
        raise EvolutionPackConsumerError(f"Missing ZIP member: {name}") from exc
    text = raw.decode("utf-8", errors="replace")
    assert_public_payload(text, label=name)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EvolutionPackConsumerError(f"ZIP member is not valid JSON: {name}") from exc
    if not isinstance(payload, dict):
        raise EvolutionPackConsumerError(f"ZIP member JSON must be an object: {name}")
    return payload


def expected_pack_id(manifest: Mapping[str, Any]) -> str:
    generated_at = str(manifest.get("generated_at") or "")
    pack_files = manifest.get("pack_files")
    if not isinstance(pack_files, list):
        raise EvolutionPackConsumerError("Manifest pack_files must be a list.")
    return f"evolution-pack-{sha256_text(generated_at + json.dumps(pack_files, sort_keys=True))[:16]}"


def validate_manifest_shape(manifest: dict[str, Any]) -> None:
    assert_public_payload(manifest, label="manifest")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise EvolutionPackConsumerError("Manifest has the wrong schema_version.")
    if manifest.get("archive_root") != ARCHIVE_ROOT:
        raise EvolutionPackConsumerError("Manifest archive_root does not match this consumer.")
    if manifest.get("status") not in EXPECTED_STATUSES:
        raise EvolutionPackConsumerError(f"Manifest status is not supported: {manifest.get('status')}")
    if manifest.get("pack_id") != expected_pack_id(manifest):
        raise EvolutionPackConsumerError("Manifest pack_id does not match generated_at and pack_files.")
    if manifest.get("no_real_source_mutation") is not True:
        raise EvolutionPackConsumerError("Manifest must assert no_real_source_mutation=true.")
    if manifest.get("no_model_calls") is not True or manifest.get("no_raw_payloads") is not True:
        raise EvolutionPackConsumerError("Manifest must assert no_model_calls=true and no_raw_payloads=true.")

    guardrails = manifest.get("guardrails")
    privacy = manifest.get("privacy")
    if not isinstance(guardrails, Mapping) or not isinstance(privacy, Mapping):
        raise EvolutionPackConsumerError("Manifest must include guardrails and privacy objects.")
    required_guardrails = {
        "read_only": True,
        "metadata_only": True,
        "no_real_source_mutation": True,
        "real_worktree_apply_executed": False,
        "model_called": False,
        "daemon_started": False,
        "source_files_modified": False,
        "real_source_mutated": False,
        "policy_weakened": False,
    }
    required_privacy = {
        "metadata_only": True,
        "source_text_included": False,
        "raw_diff_included": False,
        "learner_answers_included": False,
        "agent_endpoint_included": False,
        "agent_metadata_included": False,
        "prompt_text_included": False,
        "real_model_keys_stored": False,
        "model_called": False,
        "daemon_started": False,
        "no_model_calls": True,
        "no_raw_payloads": True,
    }
    for key, expected in required_guardrails.items():
        if guardrails.get(key) is not expected:
            raise EvolutionPackConsumerError(f"Manifest guardrail {key} must be {expected}.")
    for key, expected in required_privacy.items():
        if privacy.get(key) is not expected:
            raise EvolutionPackConsumerError(f"Manifest privacy {key} must be {expected}.")
    regressions = privacy_regressions(manifest)
    if regressions:
        raise EvolutionPackConsumerError(f"Manifest has privacy regressions: {regressions}")
    protected = protected_path_hits(manifest)
    if protected:
        raise EvolutionPackConsumerError(f"Manifest references protected paths: {protected}")


def validate_archive_layout(archive: zipfile.ZipFile, manifest: Mapping[str, Any]) -> list[str]:
    names = archive.namelist()
    for name in names:
        assert_safe_zip_member(name)
    name_set = set(names)
    required = {f"{ARCHIVE_ROOT}/manifest.json", f"{ARCHIVE_ROOT}/index.html"}
    missing_required = required - name_set
    if missing_required:
        raise EvolutionPackConsumerError(f"Pack is missing required entries: {sorted(missing_required)}")

    pack_files = manifest.get("pack_files")
    if not isinstance(pack_files, list):
        raise EvolutionPackConsumerError("Manifest pack_files must be a list.")
    archive_layout = manifest.get("archive_layout")
    if not isinstance(archive_layout, list):
        raise EvolutionPackConsumerError("Manifest archive_layout must be a list.")
    expected_layout = [
        f"{ARCHIVE_ROOT}/manifest.json",
        f"{ARCHIVE_ROOT}/index.html",
        *[
            str(record.get("archive_path"))
            for record in pack_files
            if isinstance(record, Mapping) and record.get("archive_path") != f"{ARCHIVE_ROOT}/index.html"
        ],
    ]
    if archive_layout != expected_layout:
        raise EvolutionPackConsumerError("Manifest archive_layout does not match pack_files.")

    for record in pack_files:
        if not isinstance(record, Mapping):
            raise EvolutionPackConsumerError("Manifest pack_files entries must be objects.")
        archive_path = str(record.get("archive_path") or "")
        if not archive_path:
            raise EvolutionPackConsumerError("Manifest pack_files entry is missing archive_path.")
        assert_safe_zip_member(archive_path)
        if archive_path not in name_set:
            raise EvolutionPackConsumerError(f"Pack file is missing from ZIP: {archive_path}")
        data = archive.read(archive_path)
        if sha256_bytes(data) != record.get("sha256"):
            raise EvolutionPackConsumerError(f"Pack file hash mismatch: {archive_path}")
        if record.get("content_included") is not False:
            raise EvolutionPackConsumerError(f"Pack file must be metadata-only: {archive_path}")
        assert_public_payload(data.decode("utf-8", errors="replace"), label=archive_path)
    return names


def validate_artifact_refs(manifest: Mapping[str, Any]) -> dict[str, Any]:
    refs = manifest.get("artifact_refs")
    if not isinstance(refs, list):
        raise EvolutionPackConsumerError("Manifest artifact_refs must be a list.")
    expected = int(manifest.get("expected_artifact_count") or 0)
    if expected != 8 or len(refs) != expected:
        raise EvolutionPackConsumerError("Manifest must describe the eight expected evolution-chain artifacts.")
    missing_roles = [str(item.get("role")) for item in refs if isinstance(item, Mapping) and item.get("status") == "missing"]
    if manifest.get("missing_roles") != missing_roles:
        raise EvolutionPackConsumerError("Manifest missing_roles does not match artifact_refs.")
    for item in refs:
        if not isinstance(item, Mapping):
            raise EvolutionPackConsumerError("Artifact refs entries must be objects.")
        if item.get("content_included") is not False:
            raise EvolutionPackConsumerError(f"Artifact ref must not include content: {item.get('role')}")
        if item.get("pack_included") is True and not item.get("sha256"):
            raise EvolutionPackConsumerError(f"Packed artifact must include sha256: {item.get('role')}")
    return {"artifact_count": len(refs), "missing_roles": missing_roles}


def consume_pack(pack_path: Path) -> dict[str, Any]:
    if not pack_path.is_file():
        raise EvolutionPackConsumerError(f"Pack ZIP is missing: {pack_path}")
    try:
        archive = zipfile.ZipFile(pack_path)
    except zipfile.BadZipFile as exc:
        raise EvolutionPackConsumerError("Pack is not a valid ZIP archive.") from exc
    with archive:
        manifest_raw = archive.read(f"{ARCHIVE_ROOT}/manifest.json")
        manifest = read_json_member(archive, f"{ARCHIVE_ROOT}/manifest.json")
        validate_manifest_shape(manifest)
        names = validate_archive_layout(archive, manifest)
        artifact_summary = validate_artifact_refs(manifest)
        html = archive.read(f"{ARCHIVE_ROOT}/index.html").decode("utf-8", errors="replace")
        assert_public_payload(html, label="index.html")
        if "Cognitive Loop Professional Evolution Pack" not in html or 'name="viewport"' not in html:
            raise EvolutionPackConsumerError("Pack HTML index is missing required standalone structure.")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "pack": {
            "path": str(pack_path),
            "archive_root": ARCHIVE_ROOT,
            "manifest_schema_version": manifest["schema_version"],
            "pack_status": manifest["status"],
            "manifest_sha256": sha256_bytes(manifest_raw),
            "zip_sha256": sha256_bytes(pack_path.read_bytes()),
            "entry_count": len(names),
            "pack_file_count": len(manifest["pack_files"]),
            "artifact_count": artifact_summary["artifact_count"],
            "missing_roles": artifact_summary["missing_roles"],
        },
        "zip_only_validation": {
            "repo_checkout_required": False,
            "api_required": False,
            "docker_required": False,
            "model_called": False,
            "daemon_started": False,
            "real_worktree_apply_executed": False,
            "source_files_modified": False,
        },
        "privacy": {
            "metadata_only": True,
            "source_text_included": False,
            "raw_diff_included": False,
            "learner_answers_included": False,
            "agent_endpoint_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
            "no_model_calls": True,
            "no_raw_payloads": True,
        },
    }


def import_export_fixtures() -> Any:
    sys.path.insert(0, str(ROOT / "scripts"))
    import verify_cognitive_loop_evolution_pack_export as fixtures  # type: ignore

    return fixtures


def create_fixture_pack(mode: str) -> tuple[dict[str, Any], bytes]:
    fixtures = import_export_fixtures()
    with tempfile.TemporaryDirectory(prefix=f"study-anything-evolution-pack-consumer-{mode}-") as tmp:
        root = Path(tmp)
        fixtures.write_ready_pack(root)
        if mode == "manual_review":
            fixtures.mutate_manual(root)
        elif mode == "blocked":
            fixtures.mutate_blocked(root)
        elif mode == "degraded_missing_artifacts":
            root = root / "missing"
            root.mkdir()
        manifest, _html, zip_bytes = fixtures.run_export(root)
        pack_path = root / manifest["outputs"]["zip_ref"]
        consumed = consume_pack(pack_path)
        return consumed, zip_bytes


def write_zip(path: Path, entries: Mapping[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)


def mutate_manifest(zip_bytes: bytes, mutator: Any, *, extra: Mapping[str, bytes] | None = None) -> bytes:
    with tempfile.TemporaryDirectory(prefix="study-anything-evolution-pack-tamper-") as tmp:
        root = Path(tmp)
        source = root / "source.zip"
        source.write_bytes(zip_bytes)
        entries: dict[str, bytes] = {}
        with zipfile.ZipFile(source) as archive:
            for name in archive.namelist():
                data = archive.read(name)
                if name == f"{ARCHIVE_ROOT}/manifest.json":
                    manifest = json.loads(data.decode("utf-8"))
                    mutator(manifest)
                    data = dump_json(manifest).encode("utf-8")
                entries[name] = data
        if extra:
            entries.update(extra)
        target = root / "target.zip"
        write_zip(target, entries)
        return target.read_bytes()


def mutate_entry(zip_bytes: bytes, archive_path: str, data: bytes) -> bytes:
    with tempfile.TemporaryDirectory(prefix="study-anything-evolution-pack-entry-") as tmp:
        root = Path(tmp)
        source = root / "source.zip"
        source.write_bytes(zip_bytes)
        entries: dict[str, bytes] = {}
        with zipfile.ZipFile(source) as archive:
            for name in archive.namelist():
                entries[name] = data if name == archive_path else archive.read(name)
        target = root / "target.zip"
        write_zip(target, entries)
        return target.read_bytes()


def remove_entry(zip_bytes: bytes, archive_path: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="study-anything-evolution-pack-remove-") as tmp:
        root = Path(tmp)
        source = root / "source.zip"
        source.write_bytes(zip_bytes)
        entries: dict[str, bytes] = {}
        with zipfile.ZipFile(source) as archive:
            for name in archive.namelist():
                if name != archive_path:
                    entries[name] = archive.read(name)
        target = root / "target.zip"
        write_zip(target, entries)
        return target.read_bytes()


def expect_consumer_failure(name: str, zip_bytes: bytes) -> bool:
    with tempfile.TemporaryDirectory(prefix=f"study-anything-evolution-pack-consumer-fail-{name}-") as tmp:
        pack = Path(tmp) / "pack.zip"
        pack.write_bytes(zip_bytes)
        try:
            consume_pack(pack)
        except EvolutionPackConsumerError:
            return True
    raise RuntimeError(f"Unsafe or invalid pack was not rejected: {name}")


def verify_failure_modes(ready_zip: bytes) -> dict[str, bool]:
    with tempfile.TemporaryDirectory(prefix="study-anything-evolution-pack-consumer-ready-") as tmp:
        ready_pack = Path(tmp) / "ready.zip"
        ready_pack.write_bytes(ready_zip)
        with zipfile.ZipFile(ready_pack) as archive:
            manifest = json.loads(archive.read(f"{ARCHIVE_ROOT}/manifest.json").decode("utf-8"))
            first_pack_file = manifest["pack_files"][1]["archive_path"]

    def bad_pack_id(payload: dict[str, Any]) -> None:
        payload["pack_id"] = "evolution-pack-deadbeef"

    def secret(payload: dict[str, Any]) -> None:
        payload["title"] = "OPENAI_API_KEY=sk-proj-abcdefghijklmnop"

    def raw_diff(payload: dict[str, Any]) -> None:
        payload["title"] = "diff --git a/file b/file"

    def policy(payload: dict[str, Any]) -> None:
        payload["operator_next_commands"] = ["disable tests and bypass human gate"]

    def privacy(payload: dict[str, Any]) -> None:
        payload["privacy"]["raw_diff_included"] = True

    def protected(payload: dict[str, Any]) -> None:
        payload["artifact_refs"][0]["ref"] = ".env"

    def missing_layout(payload: dict[str, Any]) -> None:
        payload["archive_layout"] = payload["archive_layout"][:-1]

    results = {
        "tampered_zip_rejected": expect_consumer_failure("tampered_zip", b"not-a-zip"),
        "manifest_drift_rejected": expect_consumer_failure("manifest_drift", mutate_manifest(ready_zip, bad_pack_id)),
        "missing_pack_file_rejected": expect_consumer_failure("missing_pack_file", remove_entry(ready_zip, first_pack_file)),
        "hash_mismatch_rejected": expect_consumer_failure("hash_mismatch", mutate_entry(ready_zip, first_pack_file, b"changed\n")),
        "secret_like_text_rejected": expect_consumer_failure("secret", mutate_manifest(ready_zip, secret)),
        "raw_diff_text_rejected": expect_consumer_failure("raw_diff", mutate_manifest(ready_zip, raw_diff)),
        "policy_weakening_rejected": expect_consumer_failure("policy", mutate_manifest(ready_zip, policy)),
        "privacy_regression_rejected": expect_consumer_failure("privacy", mutate_manifest(ready_zip, privacy)),
        "protected_path_rejected": expect_consumer_failure("protected", mutate_manifest(ready_zip, protected)),
        "unsafe_zip_path_rejected": expect_consumer_failure(
            "unsafe_zip_path",
            mutate_manifest(ready_zip, lambda payload: None, extra={"../evil.json": b"{}"}),
        ),
        "archive_layout_mismatch_rejected": expect_consumer_failure(
            "archive_layout",
            mutate_manifest(ready_zip, missing_layout),
        ),
    }
    return results


def build_report() -> dict[str, Any]:
    ready, ready_zip = create_fixture_pack("pack_ready")
    manual, _manual_zip = create_fixture_pack("manual_review")
    blocked, _blocked_zip = create_fixture_pack("blocked")
    missing, _missing_zip = create_fixture_pack("degraded_missing_artifacts")
    failures = verify_failure_modes(ready_zip)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "purpose": "Verify external zip-only consumption of Cognitive Loop Professional Evolution Pack exports.",
        "manifest_schema": MANIFEST_SCHEMA_VERSION,
        "consumer": {
            "script": "scripts/verify_cognitive_loop_evolution_pack_consumer.py",
            "command": "python3 scripts/verify_cognitive_loop_evolution_pack_consumer.py --pack <cognitive-loop-professional-evolution-pack.zip>",
            "repo_checkout_required_for_pack_mode": False,
            "api_required": False,
            "docker_required": False,
        },
        "success_modes": {
            "ready_status": ready["pack"]["pack_status"],
            "manual_status": manual["pack"]["pack_status"],
            "blocked_status": blocked["pack"]["pack_status"],
            "missing_status": missing["pack"]["pack_status"],
            "ready_entry_count": ready["pack"]["entry_count"],
            "ready_pack_file_count": ready["pack"]["pack_file_count"],
            "ready_manifest_sha256": ready["pack"]["manifest_sha256"],
            "ready_zip_sha256": ready["pack"]["zip_sha256"],
        },
        "failure_modes": failures,
        "privacy": {
            "metadata_only": True,
            "source_text_included": False,
            "raw_diff_included": False,
            "learner_answers_included": False,
            "agent_endpoint_included": False,
            "agent_metadata_included": False,
            "prompt_text_included": False,
            "real_model_keys_stored": False,
            "no_model_calls": True,
            "no_raw_payloads": True,
        },
        "runtime_boundaries": {
            "standalone_frontend_required": False,
            "production_mastra_daemon_started": False,
            "model_called": False,
            "api_required": False,
            "docker_required": False,
            "real_worktree_apply_executed": False,
            "source_files_modified": False,
        },
    }
    assert_public_payload(report, label="consumer verification report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", help="Path to cognitive-loop-professional-evolution-pack.zip.")
    parser.add_argument("--write", action="store_true", help="Write generated verification report.")
    parser.add_argument("--check", action="store_true", help="Require generated verification report to be up to date.")
    parser.add_argument("--output", default=str(REPORT), help="Report path for --write/--check.")
    args = parser.parse_args()

    try:
        if args.pack and not args.write and not args.check:
            print(dump_json(consume_pack(Path(args.pack).resolve())), end="")
            return 0
        report = build_report()
        rendered = dump_json(report)
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            print(f"wrote {output.relative_to(ROOT)}")
            return 0
        if args.check:
            current = output.read_text(encoding="utf-8") if output.is_file() else ""
            if current != rendered:
                raise SystemExit("generated evolution pack consumer report is stale; run with --write")
            print("ok    Cognitive Loop evolution pack consumer report is up to date")
            return 0
        print(rendered, end="")
        return 0
    except EvolutionPackConsumerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
