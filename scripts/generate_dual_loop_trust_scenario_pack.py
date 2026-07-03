#!/usr/bin/env python3
"""Generate a portable Dual Loop trust scenario pack."""

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
SCHEMA_VERSION = "dual-loop-trust-scenario-pack-v1"
VERSION = "v0.3.31-alpha"
PACKAGE_NAME = "study-anything-dual-loop-trust-scenario-pack"
ARCHIVE_ROOT = PACKAGE_NAME
SIDECAR_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.json"
MARKDOWN_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.md"
ARCHIVE_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.zip"
SHA256_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.sha256"


class ScenarioPackError(RuntimeError):
    """Readable scenario-pack generation failure."""


@dataclass(frozen=True)
class PackFile:
    path: str
    role: str
    purpose: str


PACK_FILES: tuple[PackFile, ...] = (
    PackFile("docs/dual-loop-scenario-harness.md", "operator_doc", "Dual Loop customer-delivery scenario harness guide."),
    PackFile("docs/dual-loop-mvp.md", "operator_doc", "Dual Loop boundary model and MVP contract."),
    PackFile("docs/delivery-trust-receipt.md", "operator_doc", "Delivery trust receipt rules and negative cases."),
    PackFile("docs/customer-handoff-package.md", "operator_doc", "Portable customer handoff package rules."),
    PackFile("docs/trust-model.md", "operator_doc", "Cognitive Black Box trust model."),
    PackFile("scripts/run_dual_loop_scenario_harness.py", "cli", "Run deterministic Dual Loop customer-delivery scenarios."),
    PackFile("scripts/verify_dual_loop_scenario_harness.py", "verification", "Verify Dual Loop scenario fixtures and report."),
    PackFile("scripts/cbb_delivery_harness.py", "cli", "Run Cognitive Black Box tri-loop delivery scenarios."),
    PackFile("scripts/verify_cbb_delivery_harness.py", "verification", "Verify Cognitive Black Box tri-loop delivery scenario fixtures."),
    PackFile("platform/generated/study-anything-dual-loop-contracts.json", "evidence", "Dual Loop contract verification evidence."),
    PackFile("platform/generated/study-anything-dual-loop-scenario-harness.json", "evidence", "Dual Loop trust scenario harness evidence."),
    PackFile("platform/generated/study-anything-cbb-delivery-scenario-harness.json", "evidence", "Cognitive Black Box tri-loop delivery harness evidence."),
    PackFile("platform/generated/study-anything-delivery-trust-receipt.json", "evidence", "Delivery trust receipt verification evidence."),
    PackFile("platform/generated/study-anything-customer-handoff-package.json", "evidence", "Customer handoff package verification evidence."),
    PackFile("platform/schemas/dual-loop/failure-contract-v1.schema.json", "schema", "Controlled failure contract schema."),
    PackFile("platform/schemas/dual-loop/sandbox-receipt-v1.schema.json", "schema", "Sandbox receipt schema."),
    PackFile("platform/schemas/dual-loop/attention-reconstruction-trace-v1.schema.json", "schema", "Attention reconstruction trace schema."),
    PackFile("platform/schemas/dual-loop/attention-reconstruction-summary-v1.schema.json", "schema", "Attention reconstruction summary schema."),
    PackFile("platform/schemas/dual-loop/dual-loop-gate-receipt-v1.schema.json", "schema", "Dual Loop gate receipt schema."),
    PackFile("platform/schemas/cbb/cbb-delivery-scenario-v1.schema.json", "schema", "Cognitive Black Box delivery scenario schema."),
    PackFile("platform/schemas/cbb/cbb-external-feedback-intake-v1.schema.json", "schema", "External feedback intake schema."),
    PackFile("platform/schemas/cbb/cbb-tri-loop-run-v1.schema.json", "schema", "Tri-loop run schema."),
)


DUAL_LOOP_CASE_FILES = (
    "failure-contract.json",
    "sandbox-receipt.json",
    "attention-reconstruction-trace.json",
    "attention-reconstruction-summary.json",
    "dual-loop-gate-receipt.json",
    "delivery-trust-receipt.json",
    "customer-handoff-package.json",
    "scenario-result.json",
)
DUAL_LOOP_CASES = ("pass", "attention-missing", "risk-over-budget", "both-fail")
CBB_CASES = (
    "pass",
    "blocked-missing-developer-reconstruction",
    "blocked-risk-over-budget",
    "blocked-external-scope-expansion",
    "blocked-stale-receipt-chain",
    "blocked-ai-review-only",
)
CBB_CASE_FILES = (
    "delivery-scenario.json",
    "external-feedback-intake.json",
    "receipt-chain.json",
    "self-intake-receipt.json",
    "tri-loop-run.json",
)


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_file(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.is_file():
        raise ScenarioPackError(f"Missing scenario pack file: {relative_path}")
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
    for case_id in DUAL_LOOP_CASES:
        for filename in DUAL_LOOP_CASE_FILES:
            relative = f"fixtures/dual-loop-scenarios/{case_id}/{filename}"
            if (ROOT / relative).is_file():
                records.append(
                    file_record(
                        relative,
                        "dual_loop_fixture",
                        f"Dual Loop scenario fixture {case_id}/{filename}.",
                    )
                )
    for case_id in CBB_CASES:
        for filename in CBB_CASE_FILES:
            relative = f"fixtures/cbb-delivery-harness/{case_id}/{filename}"
            records.append(
                file_record(
                    relative,
                    "cbb_fixture",
                    f"Cognitive Black Box delivery fixture {case_id}/{filename}.",
                )
            )
    return records


def build_manifest(include_archive: bool = False, archive: bytes | None = None) -> dict[str, Any]:
    files = [file_record(item.path, item.role, item.purpose) for item in PACK_FILES]
    files.extend(fixture_records())
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "name": PACKAGE_NAME,
        "title": "Study Anything Dual Loop Trust Scenario Pack",
        "version": VERSION,
        "package_type": "dual_loop_trust_scenario_pack",
        "scenario_class": "customer_delivery_readiness",
        "summary": (
            "Portable metadata-only fixtures and verifiers showing how an AI-generated "
            "customer handoff candidate is allowed only when controlled failure and "
            "human attention reconstruction both satisfy the Dual Loop gate."
        ),
        "entrypoints": {
            "run_dual_loop_scenarios": "python3 scripts/run_dual_loop_scenario_harness.py run --case all",
            "verify_dual_loop_scenarios": "python3 scripts/verify_dual_loop_scenario_harness.py --check",
            "run_cbb_delivery_scenarios": "python3 scripts/cbb_delivery_harness.py run --case all",
            "verify_cbb_delivery_scenarios": "python3 scripts/verify_cbb_delivery_harness.py --check",
        },
        "verification_commands": [
            "python3 scripts/verify_dual_loop_scenario_harness.py --check",
            "python3 scripts/verify_cbb_delivery_harness.py --check",
            "python3 scripts/verify_dual_loop_trust_scenario_pack.py --check",
        ],
        "trust_rules": {
            "controlled_failure_loop_required": True,
            "human_attention_reconstruction_required": True,
            "dual_loop_gate_required": True,
            "delivery_trust_receipt_required": True,
            "customer_handoff_package_only_for_allowed_case": True,
            "neither_loop_may_dominate": True,
            "ai_review_only_rejected": True,
        },
        "case_matrix": {
            "dual_loop": list(DUAL_LOOP_CASES),
            "cbb_delivery": list(CBB_CASES),
        },
        "claim_boundary": {
            "current_claim": (
                "This pack proves deterministic local metadata-only Dual Loop and CBB "
                "scenario behavior for customer-delivery readiness."
            ),
            "not_claimed": [
                "production deployment approval",
                "real customer acceptance",
                "general model correctness",
                "legal compliance certification",
                "security certification",
            ],
        },
        "privacy_boundaries": {
            "metadata_only": True,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "production_mutation_performed": False,
            "raw_source_text_included": False,
            "raw_report_text_included": False,
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
            raise ScenarioPackError("archive metadata requested without archive bytes")
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

## Start

Run the scenario matrix from an extracted repository or adoption-pack checkout:

```bash
python3 scripts/run_dual_loop_scenario_harness.py run --case all
python3 scripts/verify_dual_loop_scenario_harness.py --check
python3 scripts/cbb_delivery_harness.py run --case all
python3 scripts/verify_cbb_delivery_harness.py --check
```

## Verification

{commands}

## Boundary

This pack is local-first and metadata-only. It does not call models, start a
daemon, mutate production, send customer messages, or include raw source text,
raw reports, screenshots, attention streams, secrets, cookies, bearer tokens,
signed URLs, or user-owned Agent credentials.

## Claim Boundary

Current claim: {manifest["claim_boundary"]["current_claim"]}

Not claimed: {", ".join(manifest["claim_boundary"]["not_claimed"])}.
"""


def markdown_report(manifest: dict[str, Any]) -> str:
    return f"""# Dual Loop Trust Scenario Pack

- Schema: `{manifest["schema_version"]}`
- Package: `{manifest["name"]}`
- Version: `{manifest["version"]}`
- Scenario class: `{manifest["scenario_class"]}`
- File count: `{len(manifest["files"])}`
- Archive SHA-256: `{manifest.get("archive", {}).get("sha256", "pending")}`

## Trust Rules

- Controlled failure loop required.
- Human attention reconstruction required.
- Dual Loop gate required.
- Delivery trust receipt required.
- Customer handoff package is emitted only for the allowed case.
- Neither loop may dominate the other.
- AI-review-only evidence is rejected.

## Privacy

The generated pack is metadata-only and excludes raw source text, raw reports,
screenshots, keystrokes, mouse coordinates, biometrics, real secrets, bearer
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

        write_bytes("SCENARIO_PACK_README.md", readme)
        for record in files:
            data = require_file(record["path"]).read_bytes()
            write_bytes(record["path"], data)
        manifest_for_archive = dict(manifest_without_archive)
        manifest_for_archive["files"] = files + [
            {
                "path": "SCENARIO_PACK_README.md",
                "archive_path": f"{ARCHIVE_ROOT}/SCENARIO_PACK_README.md",
                "role": "pack_readme",
                "purpose": "Beginner-readable scenario pack entrypoint.",
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
        raise ScenarioPackError(
            "Dual Loop trust scenario pack assets are stale. "
            "Run `python3 scripts/generate_dual_loop_trust_scenario_pack.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    generated Dual Loop trust scenario pack assets are up to date")


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
        print(f"generate_dual_loop_trust_scenario_pack failed: {exc}", file=sys.stderr)
        sys.exit(1)
