#!/usr/bin/env python3
"""Generate a portable Delivery Trust Case consumer pack."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "platform" / "generated"
SCHEMA_VERSION = "delivery-trust-case-pack-v1"
VERSION = "v0.3.31-alpha"
PACKAGE_NAME = "study-anything-delivery-trust-case-pack"
ARCHIVE_ROOT = PACKAGE_NAME
SIDECAR_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.json"
MARKDOWN_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.md"
ARCHIVE_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.zip"
SHA256_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.sha256"

CASE_IDS = (
    "pass",
    "blocked-product-loop",
    "blocked-dual-loop",
    "blocked-customer-handoff",
    "blocked-ai-review-only",
)
CASE_FILES = (
    "failure-contract.json",
    "sandbox-receipt.json",
    "attention-reconstruction-trace.json",
    "attention-reconstruction-summary.json",
    "dual-loop-gate-receipt.json",
    "delivery-trust-receipt.json",
    "customer-handoff-package.json",
    "product-loop-scenario.json",
    "product-loop-run.json",
    "delivery-trust-case.json",
)


class DeliveryTrustCasePackError(RuntimeError):
    """Readable delivery-trust-case pack generation failure."""


@dataclass(frozen=True)
class PackFile:
    path: str
    role: str
    purpose: str


PACK_FILES: tuple[PackFile, ...] = (
    PackFile("docs/delivery-trust-case-harness.md", "operator_doc", "Delivery Trust Case Harness guide."),
    PackFile("docs/trust-model.md", "operator_doc", "Cognitive Black Box trust model."),
    PackFile("docs/product-runway.md", "operator_doc", "Current product runway and claim boundary."),
    PackFile("docs/delivery-trust-receipt.md", "operator_doc", "Delivery trust receipt rules."),
    PackFile("docs/customer-handoff-package.md", "operator_doc", "Customer handoff package rules."),
    PackFile("scripts/delivery_trust_case_harness.py", "cli", "Run deterministic Delivery Trust Case examples."),
    PackFile("scripts/verify_delivery_trust_case_harness.py", "verification", "Verify Delivery Trust Case fixtures."),
    PackFile("platform/generated/study-anything-delivery-trust-case-harness.json", "evidence", "Delivery Trust Case Harness verification report."),
    PackFile("platform/generated/study-anything-delivery-trust-case-harness.html", "evidence", "Static Delivery Trust Case Harness report."),
    PackFile("platform/schemas/delivery-trust/delivery-trust-case-v1.schema.json", "schema", "Delivery Trust Case schema."),
)


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_file(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.is_file():
        raise DeliveryTrustCasePackError(f"Missing delivery trust case pack file: {relative_path}")
    return path


def file_record(relative_path: str, role: str, purpose: str) -> dict[str, Any]:
    data = require_file(relative_path).read_bytes()
    return {
        "path": relative_path,
        "archive_path": f"{ARCHIVE_ROOT}/{relative_path}",
        "role": role,
        "purpose": purpose,
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def fixture_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case_id in CASE_IDS:
        for filename in CASE_FILES:
            relative = f"fixtures/delivery-trust-case/{case_id}/{filename}"
            if (ROOT / relative).is_file():
                records.append(
                    file_record(
                        relative,
                        "delivery_trust_case_fixture",
                        f"Delivery Trust Case fixture {case_id}/{filename}.",
                    )
                )
    return records


def build_manifest(include_archive: bool = False, archive: bytes | None = None) -> dict[str, Any]:
    files = [file_record(item.path, item.role, item.purpose) for item in PACK_FILES]
    files.extend(fixture_records())
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "name": PACKAGE_NAME,
        "title": "Study Anything Delivery Trust Case Pack",
        "version": VERSION,
        "package_type": "delivery_trust_case_pack",
        "scenario_class": "controlled_customer_handoff",
        "summary": (
            "Portable metadata-only evidence showing how Product Loop, Dual Loop, "
            "Delivery Trust Receipt, and CustomerHandoffPackage must agree before "
            "a controlled customer handoff is allowed."
        ),
        "entrypoints": {
            "run_cases": "python3 scripts/delivery_trust_case_harness.py run --case all",
            "verify_cases": "python3 scripts/verify_delivery_trust_case_harness.py --check",
        },
        "verification_commands": [
            "python3 scripts/generate_delivery_trust_case_pack.py --check",
            "python3 scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py --check",
        ],
        "trust_rules": {
            "product_loop_required": True,
            "dual_loop_gate_required": True,
            "delivery_trust_receipt_required": True,
            "customer_handoff_package_required": True,
            "external_eval_receipts_supporting_only": True,
            "ai_review_only_rejected": True,
            "automatic_customer_sending_blocked": True,
            "production_mutation_blocked": True,
        },
        "case_matrix": list(CASE_IDS),
        "claim_boundary": {
            "current_claim": (
                "This pack proves deterministic metadata-only end-to-end gating "
                "for controlled customer handoff."
            ),
            "not_claimed": [
                "production deployment approval",
                "real customer delivery",
                "customer outcome guarantee",
                "general model correctness",
                "legal certification",
                "security certification",
            ],
        },
        "privacy_boundaries": {
            "metadata_only": True,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "production_mutation_performed": False,
            "automatic_customer_sending_performed": False,
            "raw_source_text_included": False,
            "raw_report_text_included": False,
            "raw_customer_payload_included": False,
            "delivery_artifact_body_included": False,
            "screenshots_included": False,
            "keystrokes_included": False,
            "mouse_coordinates_included": False,
            "eye_tracking_or_biometrics_included": False,
            "real_secrets_included": False,
            "cookies_or_bearer_tokens_included": False,
            "signed_urls_included": False,
            "user_owned_agent_credentials_included": False,
        },
        "files": files,
    }
    if include_archive:
        if archive is None:
            raise DeliveryTrustCasePackError("archive metadata requested without archive bytes")
        manifest["archive"] = {
            "path": f"platform/generated/{PACKAGE_NAME}.zip",
            "root": ARCHIVE_ROOT,
            "bytes": len(archive),
            "sha256": sha256_bytes(archive),
        }
    return manifest


def readme_text(manifest: dict[str, Any]) -> str:
    commands = "\n".join(f"- `{command}`" for command in manifest["verification_commands"])
    return f"""# {manifest["title"]}

{manifest["summary"]}

## Verify

{commands}

## Boundary

This pack is local-first and metadata-only. It does not call models, start a
daemon, mutate production, send customer messages, or include raw source text,
raw customer payloads, artifact bodies, screenshots, attention streams, secrets,
cookies, bearer tokens, signed URLs, or user-owned Agent credentials.

## Claim Boundary

Current claim: {manifest["claim_boundary"]["current_claim"]}

Not claimed: {", ".join(manifest["claim_boundary"]["not_claimed"])}.
"""


def markdown_report(manifest: dict[str, Any]) -> str:
    return f"""# Delivery Trust Case Pack

- Schema: `{manifest["schema_version"]}`
- Package: `{manifest["name"]}`
- Version: `{manifest["version"]}`
- Scenario class: `{manifest["scenario_class"]}`
- Case count: `{len(manifest["case_matrix"])}`
- File count: `{len(manifest["files"])}`
- Archive SHA-256: `{manifest.get("archive", {}).get("sha256", "pending")}`

## Trust Rules

- Product Loop required.
- Dual Loop gate required.
- Delivery Trust Receipt required.
- CustomerHandoffPackage required.
- External eval receipts are supporting only.
- AI-review-only evidence is rejected.
- Automatic customer sending and production mutation are blocked.

## Privacy

The pack is metadata-only and excludes raw source text, raw customer payloads,
artifact bodies, screenshots, attention streams, secrets, cookies, bearer
tokens, signed URLs, and user-owned Agent credentials.
"""


def build_archive(manifest_without_archive: dict[str, Any]) -> bytes:
    files = list(manifest_without_archive["files"])
    readme = readme_text(manifest_without_archive).encode("utf-8")
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:

        def write_bytes(name: str, data: bytes) -> None:
            info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{name}")
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)

        write_bytes("CASE_PACK_README.md", readme)
        for record in files:
            write_bytes(record["path"], require_file(record["path"]).read_bytes())
        manifest_for_archive = dict(manifest_without_archive)
        manifest_for_archive["files"] = files + [
            {
                "path": "CASE_PACK_README.md",
                "archive_path": f"{ARCHIVE_ROOT}/CASE_PACK_README.md",
                "role": "pack_readme",
                "purpose": "Beginner-readable delivery trust case pack entrypoint.",
                "bytes": len(readme),
                "sha256": sha256_bytes(readme),
            }
        ]
        write_bytes("manifest.json", dump_json(manifest_for_archive).encode("utf-8"))
    return archive_buffer.getvalue()


def build_outputs() -> tuple[dict[str, Any], str, bytes, str]:
    manifest_without_archive = build_manifest()
    archive = build_archive(manifest_without_archive)
    manifest = build_manifest(include_archive=True, archive=archive)
    markdown = markdown_report(manifest)
    checksum = f"{manifest['archive']['sha256']}  {PACKAGE_NAME}.zip\n"
    return manifest, markdown, archive, checksum


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest, markdown, archive, checksum = build_outputs()
    SIDECAR_PATH.write_text(dump_json(manifest), encoding="utf-8")
    MARKDOWN_PATH.write_text(markdown, encoding="utf-8")
    ARCHIVE_PATH.write_bytes(archive)
    SHA256_PATH.write_text(checksum, encoding="utf-8")
    print(f"wrote {SIDECAR_PATH.relative_to(ROOT)}")
    print(f"wrote {MARKDOWN_PATH.relative_to(ROOT)}")
    print(f"wrote {ARCHIVE_PATH.relative_to(ROOT)}")
    print(f"wrote {SHA256_PATH.relative_to(ROOT)}")


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
        raise DeliveryTrustCasePackError(
            "Delivery Trust Case pack assets are stale. "
            "Run `python3 scripts/generate_delivery_trust_case_pack.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated Delivery Trust Case pack assets are up to date")


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
    except Exception as exc:
        print(f"generate_delivery_trust_case_pack failed: {exc}", file=sys.stderr)
        sys.exit(1)
