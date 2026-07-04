#!/usr/bin/env python3
"""Generate a portable Trust Evidence Handoff Pack."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "platform" / "generated"
SCHEMA_VERSION = "trust-evidence-handoff-pack-v1"
VERSION = "v0.3.31-alpha"
PACKAGE_NAME = "study-anything-trust-evidence-handoff-pack"
ARCHIVE_ROOT = PACKAGE_NAME
SIDECAR_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.json"
MARKDOWN_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.md"
ARCHIVE_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.zip"
SHA256_PATH = OUTPUT_DIR / f"{PACKAGE_NAME}.sha256"

PRIVATE_PATTERNS = (
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{12,}=*"),
    re.compile(r"/Users/[A-Za-z0-9._-]+/[^\s'\"<>]+"),
    re.compile(r"/private/var/folders/[A-Za-z0-9._-]+/[^\s'\"<>]+"),
)


class TrustEvidenceHandoffPackError(RuntimeError):
    """Readable Trust Evidence Handoff Pack generation failure."""


@dataclass(frozen=True)
class PackFile:
    path: str
    role: str
    purpose: str


PACK_FILES: tuple[PackFile, ...] = (
    PackFile("docs/trust-model.md", "operator_doc", "Cognitive Black Box trust model."),
    PackFile("docs/product-runway.md", "operator_doc", "Current product runway and claim boundary."),
    PackFile("docs/delivery-class-registry.md", "operator_doc", "Delivery class registry guide."),
    PackFile("docs/trust-scenario-catalog.md", "operator_doc", "Trust scenario catalog guide."),
    PackFile("docs/trust-scenario-decision-gate.md", "operator_doc", "Trust scenario decision gate guide."),
    PackFile("docs/delivery-trust-case-pack.md", "operator_doc", "Delivery trust case pack guide."),
    PackFile("platform/generated/study-anything-delivery-class-registry.json", "evidence", "Delivery Class Registry report."),
    PackFile("platform/generated/study-anything-delivery-class-registry.html", "evidence", "Delivery Class Registry HTML report."),
    PackFile("platform/generated/study-anything-trust-scenario-catalog.json", "evidence", "Trust Scenario Catalog report."),
    PackFile("platform/generated/study-anything-trust-scenario-catalog.html", "evidence", "Trust Scenario Catalog HTML report."),
    PackFile("platform/generated/study-anything-trust-scenario-decision-gate.json", "evidence", "Trust Scenario Decision Gate report."),
    PackFile("platform/generated/study-anything-trust-scenario-decision-gate.html", "evidence", "Trust Scenario Decision Gate HTML report."),
    PackFile("platform/generated/study-anything-delivery-trust-case-pack.json", "evidence", "Delivery Trust Case Pack manifest."),
    PackFile("platform/generated/study-anything-delivery-trust-case-pack.md", "evidence", "Delivery Trust Case Pack markdown report."),
    PackFile("platform/generated/study-anything-delivery-trust-case-pack.sha256", "checksum", "Delivery Trust Case Pack checksum."),
    PackFile("scripts/verify_delivery_class_registry.py", "verification", "Verify Delivery Class Registry."),
    PackFile("scripts/verify_trust_scenario_catalog.py", "verification", "Verify Trust Scenario Catalog."),
    PackFile("scripts/trust_scenario_decision_gate.py", "cli", "Evaluate Trust Scenario decisions."),
    PackFile("scripts/verify_trust_scenario_decision_gate.py", "verification", "Verify Trust Scenario Decision Gate."),
    PackFile("scripts/generate_delivery_trust_case_pack.py", "generator", "Generate Delivery Trust Case Pack."),
    PackFile("scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py", "verification", "Verify Delivery Trust Case Pack from ZIP."),
)

DECISION_FIXTURE_ROOT = "fixtures/trust-scenario-decision-gate"
DECISION_FIXTURE_CASES = (
    "allow-code-review",
    "allow-client-report",
    "block-missing-artifact",
    "block-forbidden-shortcut",
    "block-passive-attention",
    "block-production-mutation",
    "block-truth-certification",
)
DECISION_FIXTURE_FILES = ("input.json", "trust-scenario-decision-receipt.json")


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_no_private_text(text: str, *, label: str) -> None:
    for pattern in PRIVATE_PATTERNS:
        match = pattern.search(text)
        if match:
            raise TrustEvidenceHandoffPackError(f"{label} contains private-looking text: {match.group(0)[:80]}")


def require_file(relative_path: str) -> Path:
    path = ROOT / relative_path
    if not path.is_file():
        raise TrustEvidenceHandoffPackError(f"Missing Trust Evidence Handoff Pack file: {relative_path}")
    return path


def load_json(relative_path: str) -> dict[str, Any]:
    payload = json.loads(require_file(relative_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TrustEvidenceHandoffPackError(f"Expected JSON object: {relative_path}")
    assert_no_private_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), label=relative_path)
    return payload


def file_record(relative_path: str, role: str, purpose: str) -> dict[str, Any]:
    data = require_file(relative_path).read_bytes()
    if not relative_path.endswith(".zip"):
        assert_no_private_text(data.decode("utf-8", errors="replace"), label=relative_path)
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
    for case_id in DECISION_FIXTURE_CASES:
        for filename in DECISION_FIXTURE_FILES:
            relative = f"{DECISION_FIXTURE_ROOT}/{case_id}/{filename}"
            records.append(
                file_record(
                    relative,
                    "trust_scenario_decision_fixture",
                    f"Trust Scenario Decision fixture {case_id}/{filename}.",
                )
            )
    return records


def validate_core_reports() -> dict[str, Any]:
    registry = load_json("platform/generated/study-anything-delivery-class-registry.json")
    catalog = load_json("platform/generated/study-anything-trust-scenario-catalog.json")
    decision = load_json("platform/generated/study-anything-trust-scenario-decision-gate.json")
    case_pack = load_json("platform/generated/study-anything-delivery-trust-case-pack.json")

    delivery_class_ids = sorted(row["id"] for row in registry.get("delivery_classes", []))
    if delivery_class_ids != ["client_report_handoff", "code_review_handoff"]:
        raise TrustEvidenceHandoffPackError("Delivery Class Registry must expose code review and client report handoffs.")
    if catalog.get("scenario_count") != 4 or catalog.get("blocked_scenario_count") != 2:
        raise TrustEvidenceHandoffPackError("Trust Scenario Catalog scenario counts drifted.")
    if decision.get("allowed_case_count") != 2 or decision.get("blocked_case_count") != 5:
        raise TrustEvidenceHandoffPackError("Trust Scenario Decision Gate case counts drifted.")
    if case_pack.get("package_type") != "delivery_trust_case_pack" or not case_pack.get("archive", {}).get("sha256"):
        raise TrustEvidenceHandoffPackError("Delivery Trust Case Pack must be generated before handoff packaging.")

    decision_cases = decision.get("case_reports")
    if not isinstance(decision_cases, list):
        raise TrustEvidenceHandoffPackError("Trust Scenario Decision Gate missing case reports.")
    allowed = sorted(row["scenario_id"] for row in decision_cases if row.get("status") == "allowed")
    blocked = sorted(row["scenario_id"] for row in decision_cases if row.get("status") == "blocked")

    return {
        "delivery_class_count": registry["delivery_class_count"],
        "delivery_class_ids": delivery_class_ids,
        "trust_scenario_count": catalog["scenario_count"],
        "blocked_scenario_count": catalog["blocked_scenario_count"],
        "decision_case_count": decision["case_count"],
        "allowed_decision_cases": allowed,
        "blocked_decision_scenarios": blocked,
        "delivery_trust_case_pack_sha256": case_pack["archive"]["sha256"],
    }


def build_manifest(include_archive: bool = False, archive: bytes | None = None) -> dict[str, Any]:
    files = [file_record(item.path, item.role, item.purpose) for item in PACK_FILES]
    files.extend(fixture_records())
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "name": PACKAGE_NAME,
        "title": "Study Anything Trust Evidence Handoff Pack",
        "version": VERSION,
        "package_type": "trust_evidence_handoff_pack",
        "audience": ["external_operator", "customer_reviewer", "platform_agent"],
        "summary": (
            "Portable metadata-only evidence showing which AI delivery handoffs are "
            "currently allowed, which remain blocked, and which claim boundaries must "
            "survive before external handoff."
        ),
        "core_reports": validate_core_reports(),
        "entrypoints": {
            "inspect_decision_gate": "python3 scripts/verify_trust_scenario_decision_gate.py --check",
            "inspect_delivery_case_pack": "python3 scripts/verify_delivery_trust_case_pack_consumer_walkthrough.py --check",
        },
        "verification_commands": [
            "python3 scripts/generate_trust_evidence_handoff_pack.py --check",
            "python3 scripts/verify_trust_evidence_handoff_pack_consumer_walkthrough.py --check",
        ],
        "trust_rules": {
            "both_dual_loop_sides_required": True,
            "active_reconstruction_required": True,
            "delivery_class_must_be_registered": True,
            "scenario_decision_must_allow": True,
            "delivery_trust_case_pack_must_be_current": True,
            "ai_review_only_rejected": True,
            "automatic_customer_sending_blocked": True,
            "production_mutation_blocked": True,
            "truth_certification_blocked": True,
        },
        "claim_boundary": {
            "current_claim": (
                "This pack proves a portable metadata-only handoff evidence bundle "
                "exists for currently supported delivery scenarios."
            ),
            "not_claimed": [
                "production approval",
                "automatic customer sending",
                "external publication",
                "truth certification",
                "legal or financial certification",
                "security certification",
                "customer outcome guarantee",
                "general model correctness",
            ],
        },
        "privacy_boundaries": {
            "metadata_only": True,
            "model_calls_performed": False,
            "daemon_or_hosted_service_started": False,
            "production_mutation_performed": False,
            "automatic_customer_sending_performed": False,
            "external_publication_performed": False,
            "raw_source_text_included": False,
            "raw_report_text_included": False,
            "raw_review_text_included": False,
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
            raise TrustEvidenceHandoffPackError("archive metadata requested without archive bytes")
        manifest["archive"] = {
            "path": f"platform/generated/{PACKAGE_NAME}.zip",
            "root": ARCHIVE_ROOT,
            "bytes": len(archive),
            "sha256": sha256_bytes(archive),
        }
    return manifest


def readme_text(manifest: Mapping[str, Any]) -> str:
    commands = "\n".join(f"- `{command}`" for command in manifest["verification_commands"])
    return f"""# {manifest["title"]}

{manifest["summary"]}

## What To Inspect

- Delivery classes: {", ".join(manifest["core_reports"]["delivery_class_ids"])}
- Allowed scenarios: {", ".join(manifest["core_reports"]["allowed_decision_cases"])}
- Blocked scenario decisions: {len(manifest["core_reports"]["blocked_decision_scenarios"])}

## Verify

{commands}

## Boundary

This pack is local-first and metadata-only. It does not call models, start a
daemon, mutate production, send customer messages, publish externally, or include
raw source text, raw customer payloads, artifact bodies, screenshots, attention
streams, secrets, cookies, bearer tokens, signed URLs, or user-owned Agent
credentials.
"""


def markdown_report(manifest: Mapping[str, Any]) -> str:
    return f"""# Trust Evidence Handoff Pack

- Schema: `{manifest["schema_version"]}`
- Package: `{manifest["name"]}`
- Version: `{manifest["version"]}`
- Delivery classes: `{manifest["core_reports"]["delivery_class_count"]}`
- Trust scenarios: `{manifest["core_reports"]["trust_scenario_count"]}`
- Decision cases: `{manifest["core_reports"]["decision_case_count"]}`
- File count: `{len(manifest["files"])}`
- Archive SHA-256: `{manifest.get("archive", {}).get("sha256", "pending")}`

## Claim

{manifest["claim_boundary"]["current_claim"]}

## Not Claimed

{chr(10).join(f"- {item}" for item in manifest["claim_boundary"]["not_claimed"])}

## Privacy

The pack is metadata-only and excludes raw source text, raw report text, customer
payloads, screenshots, attention streams, secrets, bearer tokens, signed URLs,
and user-owned Agent credentials.
"""


def build_archive(manifest_without_archive: Mapping[str, Any]) -> bytes:
    readme = readme_text(manifest_without_archive).encode("utf-8")
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:

        def write_bytes(name: str, data: bytes) -> None:
            info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{name}")
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)

        write_bytes("HANDOFF_PACK_README.md", readme)
        for record in manifest_without_archive["files"]:
            write_bytes(record["path"], require_file(record["path"]).read_bytes())
        manifest_for_archive = dict(manifest_without_archive)
        manifest_for_archive["files"] = list(manifest_without_archive["files"]) + [
            {
                "path": "HANDOFF_PACK_README.md",
                "archive_path": f"{ARCHIVE_ROOT}/HANDOFF_PACK_README.md",
                "role": "pack_readme",
                "purpose": "Beginner-readable Trust Evidence Handoff Pack entrypoint.",
                "bytes": len(readme),
                "sha256": sha256_bytes(readme),
            }
        ]
        write_bytes("manifest.json", dump_json(manifest_for_archive).encode("utf-8"))
    return archive_buffer.getvalue()


def generated_outputs() -> tuple[str, str, bytes, str]:
    manifest_without_archive = build_manifest()
    archive = build_archive(manifest_without_archive)
    manifest = build_manifest(include_archive=True, archive=archive)
    return dump_json(manifest), markdown_report(manifest), archive, (
        f"{sha256_bytes(archive)}  {ARCHIVE_PATH.name}\n"
    )


def write_outputs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_text, markdown_text, archive, checksum = generated_outputs()
    SIDECAR_PATH.write_text(manifest_text, encoding="utf-8")
    MARKDOWN_PATH.write_text(markdown_text, encoding="utf-8")
    ARCHIVE_PATH.write_bytes(archive)
    SHA256_PATH.write_text(checksum, encoding="utf-8")


def check_outputs() -> None:
    expected_manifest, expected_markdown, expected_archive, expected_checksum = generated_outputs()
    checks = {
        SIDECAR_PATH: expected_manifest.encode("utf-8"),
        MARKDOWN_PATH: expected_markdown.encode("utf-8"),
        ARCHIVE_PATH: expected_archive,
        SHA256_PATH: expected_checksum.encode("utf-8"),
    }
    stale = [path.relative_to(ROOT).as_posix() for path, expected in checks.items() if not path.is_file() or path.read_bytes() != expected]
    if stale:
        raise TrustEvidenceHandoffPackError(
            "Trust Evidence Handoff Pack is stale. Run: "
            "python3 scripts/generate_trust_evidence_handoff_pack.py --write "
            f"(stale={stale})"
        )
    print("ok    generated Trust Evidence Handoff Pack is up to date")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.write:
        write_outputs()
        print(f"wrote {SIDECAR_PATH.relative_to(ROOT)}")
        print(f"wrote {MARKDOWN_PATH.relative_to(ROOT)}")
        print(f"wrote {ARCHIVE_PATH.relative_to(ROOT)}")
        print(f"wrote {SHA256_PATH.relative_to(ROOT)}")
        return
    if args.check:
        check_outputs()
        return
    manifest_text, _, _, _ = generated_outputs()
    print(manifest_text, end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        raise SystemExit(f"generate_trust_evidence_handoff_pack failed: {exc}") from exc
