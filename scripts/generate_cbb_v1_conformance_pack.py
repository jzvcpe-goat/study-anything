#!/usr/bin/env python3
"""Generate the deterministic CBB Protocol v1 cross-implementation conformance pack."""

from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys
import zipfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.protocol.canonical import canonical_json_bytes  # noqa: E402
from study_anything.cbb.protocol.models import PROTOCOL_MODELS  # noqa: E402


ARCHIVE_ROOT = "delivery-clearance-cbb-v1-conformance"
OUTPUT_BASE = ROOT / "platform" / "generated" / "study-anything-cbb-v1-conformance-pack"
JSON_OUTPUT = OUTPUT_BASE.with_suffix(".json")
MARKDOWN_OUTPUT = OUTPUT_BASE.with_suffix(".md")
ZIP_OUTPUT = OUTPUT_BASE.with_suffix(".zip")
SHA_OUTPUT = OUTPUT_BASE.with_suffix(".sha256")
CONSUMER = ROOT / "conformance" / "python" / "cbb_v1_consumer.py"
GOVERNANCE_DOCS = (
    ROOT / "docs" / "cbb-protocol-v1-conformance.md",
    ROOT / "docs" / "protocol-governance.md",
    ROOT / "docs" / "extensions-and-versioning.md",
    ROOT / "docs" / "compatibility-and-trademark.md",
)


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _canonical_vectors() -> dict[str, Any]:
    contract = _read_json(ROOT / "fixtures" / "cbb-v1-contracts" / "pass.json")
    canonical = contract["canonical"]
    payloads: dict[str, Mapping[str, Any]] = {
        "cbb.trust-policy.v1": canonical["trust_policy"],
        "cbb.evidence-bundle.v1": canonical["evidence_bundle"],
        "cbb.qualified-reconstruction.v1": canonical["qualified_reconstruction"],
        "cbb.gate-decision.v1": canonical["gate_decision"],
        "cbb.delivery-trust-receipt.v1": canonical["delivery_trust_receipt"],
        "cbb.receipt-provenance.v1": canonical["receipt_provenance"],
        "cbb.delivery-outcome-receipt.v1": _read_json(
            ROOT
            / "fixtures"
            / "cbb-v1-outcomes"
            / "monitored-no-adverse-signal.json"
        )["receipt"],
        "cbb.evolution-gate-receipt.v1": _read_json(
            ROOT
            / "fixtures"
            / "cbb-v1-agentic-evolution"
            / "approved-local-candidate.json"
        )["receipt"],
    }
    if set(payloads) != set(PROTOCOL_MODELS):
        raise ValueError("canonical conformance vectors do not cover the protocol schema set")
    vectors = []
    for schema_version in PROTOCOL_MODELS:
        payload = dict(payloads[schema_version])
        canonical = canonical_json_bytes(payload)
        vectors.append(
            {
                "vector_id": f"canonical:{schema_version}",
                "schema_version": schema_version,
                "payload": payload,
                "canonical_json": canonical.decode("utf-8"),
                "sha256": _sha256(canonical),
            }
        )
    return {
        "schema_version": "cbb.canonical-vectors.v1",
        "canonicalization": "cbb-json-c14n-v1",
        "vectors": vectors,
    }


def _version_vectors() -> dict[str, Any]:
    return {
        "schema_version": "cbb.version-negotiation-vectors.v1",
        "supported_version": "1.0.0",
        "vectors": [
            {
                "requested": "1.0.0",
                "migration_available": False,
                "expected": "accept",
            },
            {
                "requested": "1.1.0",
                "migration_available": False,
                "expected": "reject_unsupported_version",
            },
            {
                "requested": "2.0.0",
                "migration_available": False,
                "expected": "reject_major",
            },
            {
                "requested": "0.3.0",
                "migration_available": True,
                "expected": "compatibility_only",
            },
        ],
    }


def _extension_vectors() -> dict[str, Any]:
    return {
        "schema_version": "cbb.extension-registry.v1",
        "registered_extensions": [
            {
                "extension_id": "cbb.ext.fixture-metadata.v1",
                "owner_ref": "protocol-maintainers",
                "spec_ref": "docs/extensions-and-versioning.md",
                "authority": "informational_only",
                "claims_authority": False,
                "unknown_handling": "preserve_or_ignore",
            }
        ],
        "vectors": [
            {
                "case_id": "registered-informational",
                "extension_id": "cbb.ext.fixture-metadata.v1",
                "claims_authority": False,
                "expected": "accept_registered_informational",
            },
            {
                "case_id": "unknown-informational",
                "extension_id": "vendor.example.note.v1",
                "claims_authority": False,
                "expected": "ignore_unknown_informational",
            },
            {
                "case_id": "unknown-authority",
                "extension_id": "vendor.example.approve.v1",
                "claims_authority": True,
                "expected": "reject_authority_claim",
            },
            {
                "case_id": "registered-authority-inflation",
                "extension_id": "cbb.ext.fixture-metadata.v1",
                "claims_authority": True,
                "expected": "reject_authority_claim",
            },
        ],
    }


def _privacy_vectors() -> dict[str, Any]:
    return {
        "schema_version": "cbb.privacy-negative-vectors.v1",
        "vectors": [
            {
                "case_id": "forbidden-api-key-field",
                "payload": {"api_key": "synthetic-fixture-value"},
                "expected": "reject",
            },
            {
                "case_id": "forbidden-raw-source-field",
                "payload": {"raw_source_text": "synthetic fixture only"},
                "expected": "reject",
            },
            {
                "case_id": "safe-negative-flags",
                "payload": {
                    "metadata_only": True,
                    "raw_source_text_included": False,
                    "production_mutation_performed": False,
                },
                "expected": "accept",
            },
        ],
    }


def _migration_map() -> dict[str, Any]:
    mappings = []
    for source, target in (
        ("failure-contract-v1", "cbb.trust-policy.v1"),
        ("sandbox-receipt-v1", "cbb.evidence-bundle.v1"),
        ("attention-reconstruction-summary-v1", "cbb.qualified-reconstruction.v1"),
        ("dual-loop-gate-receipt-v1", "cbb.gate-decision.v1"),
        ("delivery-trust-receipt-v1", "cbb.delivery-trust-receipt.v1"),
    ):
        mappings.append(
            {
                "source_schema_version": source,
                "target_schema_version": target,
                "authority": "compatibility_only",
                "scope_rule": "may_narrow_never_expand",
                "canonical_name_claimed": False,
            }
        )
    return {
        "schema_version": "cbb.v0-migration-map.v1",
        "mappings": mappings,
        "claim_boundary": (
            "Compatibility mappings may narrow or reject v0 evidence. They never "
            "promote a v0 identifier to canonical authority or expand delivery scope."
        ),
    }


def _pack_readme() -> bytes:
    return (
        "# Delivery Clearance CBB Protocol v1 Conformance Pack\n\n"
        "Run the independent consumer after extracting this archive:\n\n"
        "```bash\n"
        "python3 -I consumer/python/cbb_v1_consumer.py --pack-root .\n"
        "```\n\n"
        "The consumer does not import the Study Anything package. The optional project "
        "`cryptography` dependency is required only to verify Ed25519 fixture signatures.\n\n"
        "Passing proves fixture-bounded local interoperability only. It is not production "
        "approval, certification, customer-outcome proof, or an independent audit.\n"
    ).encode("utf-8")


def _collect_files() -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    files: dict[str, bytes] = {
        "README.md": _pack_readme(),
        "consumer/python/cbb_v1_consumer.py": CONSUMER.read_bytes(),
        "vectors/canonical-vectors.json": _json_bytes(_canonical_vectors()),
        "vectors/version-negotiation.json": _json_bytes(_version_vectors()),
        "vectors/extensions.json": _json_bytes(_extension_vectors()),
        "vectors/privacy-negative.json": _json_bytes(_privacy_vectors()),
        "migration/v0-compatibility.json": _json_bytes(_migration_map()),
    }
    for doc in GOVERNANCE_DOCS:
        files[f"governance/{doc.name}"] = doc.read_bytes()

    schemas: list[dict[str, Any]] = []
    for schema_version in PROTOCOL_MODELS:
        source = ROOT / "platform" / "schemas" / "cbb" / f"{schema_version}.schema.json"
        archive_path = f"schemas/{source.name}"
        data = source.read_bytes()
        files[archive_path] = data
        schemas.append(
            {
                "schema_version": schema_version,
                "path": archive_path,
                "sha256": _sha256(data),
            }
        )

    fixture_groups = {
        "kernel": ROOT / "fixtures" / "cbb-v1-kernel",
        "provenance": ROOT / "fixtures" / "cbb-v1-provenance",
        "outcomes": ROOT / "fixtures" / "cbb-v1-outcomes",
        "evolution": ROOT / "fixtures" / "cbb-v1-agentic-evolution",
    }
    for group, directory in fixture_groups.items():
        for source in sorted(directory.glob("*.json")):
            files[f"vectors/{group}/{source.name}"] = source.read_bytes()
    return files, schemas


def _manifest(files: Mapping[str, bytes], schemas: list[dict[str, Any]]) -> dict[str, Any]:
    records = [
        {"path": path, "bytes": len(data), "sha256": _sha256(data)}
        for path, data in sorted(files.items())
    ]
    return {
        "schema_version": "cbb.conformance-pack.v1",
        "protocol_name": "AI Delivery Clearance Protocol",
        "protocol_version": "1.0.0",
        "canonicalization": "cbb-json-c14n-v1",
        "schemas": schemas,
        "vectors": {
            "canonical": "vectors/canonical-vectors.json",
            "kernel_dir": "vectors/kernel",
            "provenance_dir": "vectors/provenance",
            "outcome_dir": "vectors/outcomes",
            "evolution_dir": "vectors/evolution",
            "version_negotiation": "vectors/version-negotiation.json",
            "extensions": "vectors/extensions.json",
            "privacy_negative": "vectors/privacy-negative.json",
        },
        "migration_map": "migration/v0-compatibility.json",
        "independent_consumer": "consumer/python/cbb_v1_consumer.py",
        "files": records,
        "signed_fixture_count": 18,
        "claim_boundary": (
            "The pack proves local cross-implementation fixture conformance only. It is "
            "not certification, production approval, customer-outcome proof, global "
            "revocation, or an independent audit result."
        ),
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "network_required": False,
            "production_mutation_performed": False,
            "private_keys_included": False,
            "real_secrets_included": False,
        },
    }


def _archive_bytes(files: Mapping[str, bytes], manifest: Mapping[str, Any]) -> bytes:
    buffer = BytesIO()
    entries = {"manifest.json": _json_bytes(manifest), **dict(files)}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, data in sorted(entries.items()):
            info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{path}")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def _summary(
    files: Mapping[str, bytes], manifest: Mapping[str, Any], archive: bytes
) -> dict[str, Any]:
    group_counts = {
        "canonical": 8,
        "kernel": len(list((ROOT / "fixtures" / "cbb-v1-kernel").glob("*.json"))),
        "provenance": len(list((ROOT / "fixtures" / "cbb-v1-provenance").glob("*.json"))),
        "outcomes": len(list((ROOT / "fixtures" / "cbb-v1-outcomes").glob("*.json"))),
        "evolution": len(
            list((ROOT / "fixtures" / "cbb-v1-agentic-evolution").glob("*.json"))
        ),
    }
    return {
        "schema_version": "cbb-conformance-pack-artifact-v1",
        "status": "ready_for_offline_conformance",
        "protocol_version": manifest["protocol_version"],
        "schema_count": len(manifest["schemas"]),
        "vector_counts": group_counts,
        "declared_file_count": len(files),
        "archive_entry_count": len(files) + 1,
        "archive_sha256": _sha256(archive),
        "manifest_sha256": _sha256(_json_bytes(manifest)),
        "independent_consumer": manifest["independent_consumer"],
        "study_anything_runtime_required_by_consumer": False,
        "claim_boundary": manifest["claim_boundary"],
        "privacy": manifest["privacy"],
    }


def _markdown(summary: Mapping[str, Any]) -> bytes:
    vectors = summary["vector_counts"]
    return (
        "# CBB Protocol v1 Conformance Pack\n\n"
        f"Status: `{summary['status']}`\n\n"
        f"Protocol version: `{summary['protocol_version']}`\n\n"
        f"Schemas: {summary['schema_count']}\n\n"
        f"Vectors: canonical {vectors['canonical']}, kernel {vectors['kernel']}, "
        f"provenance {vectors['provenance']}, outcomes {vectors['outcomes']}, "
        f"evolution {vectors['evolution']}\n\n"
        f"Archive SHA-256: `{summary['archive_sha256']}`\n\n"
        "The independent consumer does not import the Study Anything package.\n\n"
        f"Claim boundary: {summary['claim_boundary']}\n"
    ).encode("utf-8")


def expected_outputs() -> dict[Path, bytes]:
    files, schemas = _collect_files()
    manifest = _manifest(files, schemas)
    archive = _archive_bytes(files, manifest)
    summary = _summary(files, manifest, archive)
    return {
        JSON_OUTPUT: _json_bytes(summary),
        MARKDOWN_OUTPUT: _markdown(summary),
        ZIP_OUTPUT: archive,
        SHA_OUTPUT: f"{summary['archive_sha256']}  {ZIP_OUTPUT.name}\n".encode("utf-8"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = expected_outputs()
    if args.check:
        stale = [str(path.relative_to(ROOT)) for path, data in outputs.items() if not path.exists() or path.read_bytes() != data]
        if stale:
            print(
                "generate_cbb_v1_conformance_pack failed: conformance pack is stale. "
                "Run `python3 scripts/generate_cbb_v1_conformance_pack.py`. "
                f"stale={stale}",
                file=sys.stderr,
            )
            return 1
        print("ok    CBB Protocol v1 conformance pack is up to date")
        return 0
    for path, data in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
