#!/usr/bin/env python3
"""Generate the metadata-only independent security audit preparation pack."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import sys
import tomllib
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "platform" / "generated"
PACKAGE_NAME = "study-anything-external-security-audit-pack"
ARCHIVE_ROOT = PACKAGE_NAME
SCHEMA_VERSION = "external-security-audit-pack-v1"
SIDECAR_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.json"
MARKDOWN_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.md"
ARCHIVE_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.zip"
SHA256_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.sha256"


class ExternalAuditPackError(RuntimeError):
    """Raised when the independent audit preparation pack is invalid."""


@dataclass(frozen=True)
class PackFile:
    path: str
    role: str
    purpose: str


PACK_FILES: tuple[PackFile, ...] = (
    PackFile("SECURITY.md", "security_policy", "Public vulnerability reporting and audit claim boundary."),
    PackFile("security/audit/README.md", "auditor_guide", "Independent auditor start and claim boundary."),
    PackFile("security/audit/audit-plan.json", "audit_plan", "Machine-readable scope, methods, acceptance, and independence rules."),
    PackFile("security/audit/threat-model.md", "threat_model", "Assets, trust boundaries, actors, abuse cases, and exclusions."),
    PackFile("security/audit/rules-of-engagement.md", "rules_of_engagement", "Authorized targets, methods, restrictions, and completion rules."),
    PackFile("security/audit/remediation-policy.md", "remediation_policy", "Severity SLA, closure evidence, and commercial gate."),
    PackFile("security/audit/report-template.md", "report_template", "Human-readable signed audit report template."),
    PackFile(".github/ISSUE_TEMPLATE/external-security-audit.yml", "coordination_template", "Redacted external audit execution issue template."),
    PackFile("platform/schemas/security/external-security-audit-finding-v1.schema.json", "schema", "Metadata-only security finding schema."),
    PackFile("platform/schemas/security/external-security-audit-report-v1.schema.json", "schema", "Signed independent audit report schema."),
    PackFile("docs/security.md", "security_doc", "Local-first security and privacy boundary."),
    PackFile("docs/security-baseline.md", "security_doc", "Container, CI, supply-chain, and repository security baseline."),
    PackFile("docs/hosted-identity-tenancy.md", "security_doc", "OIDC and application-layer tenant authorization boundary."),
    PackFile("docs/agent-contract.md", "security_doc", "User-owned Agent contract and egress boundary."),
    PackFile("docs/commercial-readiness.md", "readiness_doc", "Hosted commercial readiness and non-claims."),
    PackFile("docs/dual-loop-mvp.md", "trust_doc", "Controlled failure and human reconstruction boundary."),
    PackFile("docs/trust-model.md", "trust_doc", "Delivery trust and AI-only review rejection model."),
    PackFile("docs/protocol.md", "protocol_doc", "CBB protocol boundary, verifier surface, and non-claims."),
    PackFile("docs/cbb-protocol-v1-contracts.md", "protocol_doc", "Canonical Protocol v1 contracts and v0 compatibility map."),
    PackFile("docs/cbb-protocol-v1-kernel.md", "protocol_doc", "Deterministic Protocol v1 Trust Kernel and runtime-isolation boundary."),
    PackFile("docs/cbb-protocol-v1-provenance.md", "protocol_doc", "Local Ed25519 provenance, expiry, replay, revocation, and claim boundaries."),
    PackFile("docs/release-checklist.md", "release_doc", "Release acceptance and claim-boundary checklist."),
    PackFile("docs/quality-audits/phase-23-repository-security-remediation.md", "quality_audit", "Repository security remediation evidence."),
    PackFile("docs/quality-audits/phase-24-python-supply-chain.md", "quality_audit", "Python supply-chain evidence."),
    PackFile("docs/quality-audits/phase-25-dependency-and-agent-egress.md", "quality_audit", "Dependency risk and Agent egress evidence."),
    PackFile("docs/quality-audits/phase-26-hosted-identity-tenancy.md", "quality_audit", "Hosted identity and tenancy evidence."),
    PackFile("platform/generated/study-anything-python-supply-chain.json", "generated_evidence", "Lock, hash export, and SBOM receipt."),
    PackFile("platform/generated/study-anything-python-sbom.cdx.json", "generated_evidence", "CycloneDX Python dependency inventory."),
    PackFile("platform/generated/study-anything-strict-reliability-acceptance.json", "generated_evidence", "Strict reliability acceptance receipt."),
    PackFile("platform/generated/study-anything-dual-loop-contracts.json", "generated_evidence", "Dual Loop contract verification receipt."),
    PackFile("platform/generated/study-anything-dual-loop-gate.json", "generated_evidence", "Dual Loop propagation gate receipt."),
    PackFile("platform/generated/study-anything-cbb-v1-contracts.json", "generated_evidence", "Canonical CBB Protocol v1 contract verification receipt."),
    PackFile("platform/generated/study-anything-cbb-v0-compatibility.json", "generated_evidence", "Non-expanding v0 compatibility verification receipt."),
    PackFile("platform/generated/study-anything-cbb-v1-kernel.json", "generated_evidence", "Deterministic CBB Protocol v1 Trust Kernel verification receipt."),
    PackFile("platform/generated/study-anything-cbb-runtime-isolation.json", "generated_evidence", "Static canonical kernel runtime-isolation receipt."),
    PackFile("platform/generated/study-anything-cbb-v1-provenance.json", "generated_evidence", "Local signing and offline provenance verification receipt."),
    PackFile("platform/generated/study-anything-cbb-v1-tamper-cases.json", "generated_evidence", "Canonical object and signature tamper rejection receipt."),
    PackFile("platform/schemas/cbb/cbb.trust-policy.v1.schema.json", "protocol_schema", "Canonical trust policy schema."),
    PackFile("platform/schemas/cbb/cbb.evidence-bundle.v1.schema.json", "protocol_schema", "Canonical evidence bundle schema."),
    PackFile("platform/schemas/cbb/cbb.qualified-reconstruction.v1.schema.json", "protocol_schema", "Canonical qualified reconstruction schema."),
    PackFile("platform/schemas/cbb/cbb.gate-decision.v1.schema.json", "protocol_schema", "Canonical gate decision schema."),
    PackFile("platform/schemas/cbb/cbb.delivery-trust-receipt.v1.schema.json", "protocol_schema", "Canonical delivery trust receipt schema."),
    PackFile("platform/schemas/cbb/cbb.receipt-provenance.v1.schema.json", "protocol_schema", "Canonical unsigned-development and local-signing provenance schema."),
    PackFile("fixtures/cbb-v1-contracts/pass.json", "protocol_fixture", "Canonical passing compatibility fixture."),
    PackFile("fixtures/cbb-v1-contracts/missing-evidence.json", "protocol_fixture", "Missing reconstruction fixture."),
    PackFile("fixtures/cbb-v1-contracts/hard-deny.json", "protocol_fixture", "Hard-deny fixture."),
    PackFile("fixtures/cbb-v1-contracts/stale.json", "protocol_fixture", "Stale reconstruction fixture."),
    PackFile("fixtures/cbb-v1-contracts/secret-like.json", "protocol_fixture", "Unsafe metadata rejection fixture."),
    PackFile("fixtures/cbb-v1-contracts/malformed.json", "protocol_fixture", "Malformed contract rejection fixture."),
    PackFile("fixtures/cbb-v1-contracts/naive-timestamp.json", "protocol_fixture", "Timezone ambiguity rejection fixture."),
    PackFile("fixtures/cbb-v1-contracts/invalid-state.json", "protocol_fixture", "Cross-field state rejection fixture."),
    PackFile("fixtures/cbb-v1-contracts/scope-expansion.json", "protocol_fixture", "Authority expansion rejection fixture."),
    PackFile("fixtures/cbb-v1-kernel/pass.json", "kernel_fixture", "Canonical Trust Kernel passing decision fixture."),
    PackFile("fixtures/cbb-v1-kernel/missing-evidence.json", "kernel_fixture", "Canonical missing evidence decision fixture."),
    PackFile("fixtures/cbb-v1-kernel/failed-evidence.json", "kernel_fixture", "Canonical failed evidence blocking fixture."),
    PackFile("fixtures/cbb-v1-kernel/stale-reconstruction.json", "kernel_fixture", "Canonical stale reconstruction fixture."),
    PackFile("fixtures/cbb-v1-kernel/hard-deny.json", "kernel_fixture", "Canonical hard-deny blocking fixture."),
    PackFile("fixtures/cbb-v1-kernel/reference-mismatch.json", "kernel_fixture", "Canonical reference-integrity rejection fixture."),
    PackFile("fixtures/cbb-v1-kernel/claim-boundary-narrowing.json", "kernel_fixture", "Canonical claim-boundary scope narrowing fixture."),
    PackFile("fixtures/cbb-v1-provenance/pass-signed.json", "provenance_fixture", "Locally signed offline verification fixture."),
    PackFile("fixtures/cbb-v1-provenance/unsigned-development.json", "provenance_fixture", "Unsigned development receipt rejection fixture."),
    PackFile("fixtures/cbb-v1-provenance/expired.json", "provenance_fixture", "Expired receipt rejection fixture."),
    PackFile("fixtures/cbb-v1-provenance/revoked.json", "provenance_fixture", "Locally revoked receipt rejection fixture."),
    PackFile("fixtures/cbb-v1-provenance/replay.json", "provenance_fixture", "Optional nonce consumption replay fixture."),
    PackFile("fixtures/cbb-v1-provenance/tampered-policy.json", "provenance_fixture", "Policy tamper rejection fixture."),
    PackFile("fixtures/cbb-v1-provenance/tampered-evidence.json", "provenance_fixture", "Evidence tamper rejection fixture."),
    PackFile("fixtures/cbb-v1-provenance/tampered-reconstruction.json", "provenance_fixture", "Human reconstruction tamper rejection fixture."),
    PackFile("fixtures/cbb-v1-provenance/tampered-decision.json", "provenance_fixture", "Gate decision tamper rejection fixture."),
    PackFile("fixtures/cbb-v1-provenance/tampered-receipt.json", "provenance_fixture", "Delivery receipt envelope tamper rejection fixture."),
    PackFile("fixtures/cbb-v1-provenance/tampered-signature.json", "provenance_fixture", "Signature tamper rejection fixture."),
    PackFile("fixtures/cbb-v1-provenance/wrong-public-key.json", "provenance_fixture", "Wrong public key rejection fixture."),
)


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def project_version() -> str:
    values = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return f"v{values['project']['version']}"


def require_file(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.is_file():
        raise ExternalAuditPackError(f"Missing external audit pack file: {relative_path}")
    return path


def file_record(item: PackFile) -> dict[str, Any]:
    data = require_file(item.path).read_bytes()
    return {
        "path": item.path,
        "archive_path": f"{ARCHIVE_ROOT}/{item.path}",
        "role": item.role,
        "purpose": item.purpose,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def audit_plan() -> dict[str, Any]:
    values = json.loads(require_file("security/audit/audit-plan.json").read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ExternalAuditPackError("security/audit/audit-plan.json must contain an object")
    return values


def build_manifest(*, archive: bytes | None = None) -> dict[str, Any]:
    plan = audit_plan()
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "name": PACKAGE_NAME,
        "title": "Study Anything External Security Audit Pack",
        "version": project_version(),
        "status": "ready_for_independent_audit",
        "package_type": "independent_security_audit_preparation",
        "repository": plan["repository"],
        "scope_commit_binding": plan["scope_commit_binding"],
        "scope_area_ids": [item["id"] for item in plan["scope_areas"]],
        "independence": plan["independence"],
        "acceptance": plan["acceptance"],
        "required_outputs": plan["required_outputs"],
        "verification_commands": [
            "python3 scripts/generate_external_security_audit_pack.py --check",
            "python3 scripts/verify_external_security_audit_pack.py --check",
        ],
        "privacy": {
            **plan["privacy"],
            "local_absolute_paths_included": False,
            "environment_values_included": False,
            "raw_logs_included": False,
            "audit_finding_bodies_included": False,
        },
        "claim_boundary": plan["claim_boundary"],
        "files": [file_record(item) for item in PACK_FILES],
    }
    if archive is not None:
        manifest["archive"] = {
            "path": f"platform/generated/{PACKAGE_NAME}.zip",
            "root": ARCHIVE_ROOT,
            "bytes": len(archive),
            "sha256": sha256_bytes(archive),
        }
    return manifest


def auditor_start_text(manifest: dict[str, Any]) -> str:
    return f"""# Auditor Start Here

Package status: `{manifest['status']}`

This is an audit preparation pack, not an audit report or security certificate.

1. Verify `{PACKAGE_NAME}.zip` against the published SHA-256 sidecar.
2. Pin the exact repository commit under review.
3. Read `security/audit/README.md`, `threat-model.md`, and
   `rules-of-engagement.md`.
4. Confirm the seven scope areas in `security/audit/audit-plan.json`.
5. Run the listed evidence commands from the pinned repository checkout.
6. Perform independent source review and negative testing.
7. Return schema-valid findings and a signed machine-readable report.

The implementation team may remediate findings, but it cannot sign the
independent audit decision.
"""


def _write_archive_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{name}")
    info.date_time = (2026, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


def build_archive(manifest_without_archive: dict[str, Any]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        start = auditor_start_text(manifest_without_archive).encode("utf-8")
        _write_archive_entry(archive, "AUDITOR_START_HERE.md", start)
        for record in manifest_without_archive["files"]:
            _write_archive_entry(archive, record["path"], require_file(record["path"]).read_bytes())
        archive_manifest = dict(manifest_without_archive)
        archive_manifest["files"] = list(manifest_without_archive["files"]) + [
            {
                "path": "AUDITOR_START_HERE.md",
                "archive_path": f"{ARCHIVE_ROOT}/AUDITOR_START_HERE.md",
                "role": "auditor_entrypoint",
                "purpose": "First action and claim-boundary guide for the independent auditor.",
                "bytes": len(start),
                "sha256": sha256_bytes(start),
            }
        ]
        _write_archive_entry(archive, "manifest.json", dump_json(archive_manifest).encode("utf-8"))
    return output.getvalue()


def markdown_summary(manifest: dict[str, Any]) -> str:
    return f"""# External Security Audit Pack

- Schema: `{manifest['schema_version']}`
- Status: `{manifest['status']}`
- Version: `{manifest['version']}`
- Scope areas: `{len(manifest['scope_area_ids'])}`
- Source/evidence files: `{len(manifest['files'])}`
- Archive SHA-256: `{manifest['archive']['sha256']}`

This pack is ready for an external human-led security audit at a pinned commit.
It does not claim that an audit, penetration test, or production certification
has completed. AI-only review and repository self-certification are forbidden.

Verification:

```bash
python3 scripts/generate_external_security_audit_pack.py --check
python3 scripts/verify_external_security_audit_pack.py --check
```
"""


def build_outputs() -> tuple[dict[str, Any], str, bytes, str]:
    manifest_without_archive = build_manifest()
    archive = build_archive(manifest_without_archive)
    manifest = build_manifest(archive=archive)
    markdown = markdown_summary(manifest)
    checksum = f"{manifest['archive']['sha256']}  {PACKAGE_NAME}.zip\n"
    return manifest, markdown, archive, checksum


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest, markdown, archive, checksum = build_outputs()
    SIDECAR_PATH.write_text(dump_json(manifest), encoding="utf-8")
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")
    ARCHIVE_PATH.write_bytes(archive)
    SHA256_PATH.write_text(checksum, encoding="utf-8")
    for path in (SIDECAR_PATH, MARKDOWN_PATH, ARCHIVE_PATH, SHA256_PATH):
        print(f"wrote {path.relative_to(ROOT)}")


def check_outputs() -> None:
    manifest, markdown, archive, checksum = build_outputs()
    expected = {
        SIDECAR_PATH: dump_json(manifest).encode("utf-8"),
        MARKDOWN_PATH: markdown.encode("utf-8"),
        ARCHIVE_PATH: archive,
        SHA256_PATH: checksum.encode("utf-8"),
    }
    missing = [path.relative_to(ROOT).as_posix() for path in expected if not path.is_file()]
    stale = [
        path.relative_to(ROOT).as_posix()
        for path, data in expected.items()
        if path.is_file() and path.read_bytes() != data
    ]
    if missing or stale:
        raise ExternalAuditPackError(
            "External security audit pack is stale. Run "
            "`python3 scripts/generate_external_security_audit_pack.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    external security audit pack assets are up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check_outputs()
    else:
        write_outputs()


if __name__ == "__main__":
    try:
        main()
    except (ExternalAuditPackError, OSError, ValueError, KeyError) as exc:
        print(f"generate_external_security_audit_pack failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
