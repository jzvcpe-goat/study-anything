#!/usr/bin/env python3
"""Verify the metadata-only Delivery Class registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.core import dual_loop  # noqa: E402


REPORT = ROOT / "platform" / "generated" / "study-anything-delivery-class-registry.json"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-delivery-class-registry.html"
RELEASE_CHECK = ROOT / "scripts" / "release_check.sh"
SCHEMA_VERSION = "delivery-class-registry-v1"
VERSION = "v0.3.31-alpha"

DELIVERY_CLASSES = (
    {
        "id": "code_review_handoff",
        "display_name": "Code Review Handoff",
        "verifier_command": "python3 scripts/verify_code_review_delivery_class_handoff.py --check",
        "report": "platform/generated/study-anything-code-review-delivery-class.json",
        "html_report": "platform/generated/study-anything-code-review-delivery-class.html",
        "doc": "docs/code-review-delivery-class.md",
        "schema": "platform/schemas/delivery-trust/code-review-handoff-case-v1.schema.json",
        "fixture_root": "fixtures/code-review-delivery-class",
        "allowed_decision": "allow_controlled_code_review_handoff",
        "blocked_decision": "block_code_review_handoff",
        "required_negative_checks": (
            "automatic_pr_commenting_rejected",
            "eval_sufficient_alone_rejected",
            "production_mutation_rejected",
            "raw_diff_rejected",
        ),
    },
    {
        "id": "client_report_handoff",
        "display_name": "Client Report Handoff",
        "verifier_command": "python3 scripts/verify_client_report_delivery_class_handoff.py --check",
        "report": "platform/generated/study-anything-client-report-delivery-class.json",
        "html_report": "platform/generated/study-anything-client-report-delivery-class.html",
        "doc": "docs/client-report-delivery-class.md",
        "schema": "platform/schemas/delivery-trust/client-report-handoff-case-v1.schema.json",
        "fixture_root": "fixtures/client-report-delivery-class",
        "allowed_decision": "allow_controlled_client_report_handoff",
        "blocked_decision": "block_client_report_handoff",
        "required_negative_checks": (
            "automatic_customer_sending_rejected",
            "eval_sufficient_alone_rejected",
            "external_publication_rejected",
            "raw_customer_payload_rejected",
            "raw_report_text_rejected",
        ),
    },
)

PRIVACY = {
    "metadata_only": True,
    "raw_diff_included": False,
    "raw_source_text_included": False,
    "raw_report_text_included": False,
    "raw_review_text_included": False,
    "raw_customer_payload_included": False,
    "screenshots_included": False,
    "keystrokes_included": False,
    "mouse_coordinates_included": False,
    "eye_tracking_included": False,
    "biometrics_included": False,
    "real_secrets_included": False,
    "cookies_included": False,
    "bearer_tokens_included": False,
    "cookies_or_bearer_tokens_included": False,
    "signed_urls_included": False,
    "model_calls_performed": False,
    "user_owned_agent_credentials_included": False,
    "production_mutation_performed": False,
    "external_publication_performed": False,
}


class DeliveryClassRegistryError(RuntimeError):
    """Readable Delivery Class registry verification failure."""


def load_json(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DeliveryClassRegistryError(f"Cannot read {relative_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DeliveryClassRegistryError(f"{relative_path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise DeliveryClassRegistryError(f"{relative_path} must contain a JSON object")
    return payload


def require_file(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    if not path.is_file():
        raise DeliveryClassRegistryError(f"Missing Delivery Class registry asset: {relative_path}")
    return {
        "path": relative_path,
        "sha256": dual_loop.sha256_text(path.read_text(encoding="utf-8", errors="replace")),
    }


def privacy_from_report(report: Mapping[str, Any], class_id: str) -> dict[str, bool]:
    privacy = report.get("privacy")
    if not isinstance(privacy, Mapping):
        raise DeliveryClassRegistryError(f"{class_id} report missing privacy object")
    runtime = report.get("runtime")
    if not isinstance(runtime, Mapping):
        raise DeliveryClassRegistryError(f"{class_id} report missing runtime object")
    expected_false = {
        "raw_source_text_included",
        "raw_report_text_included",
        "screenshots_included",
        "keystrokes_included",
        "mouse_coordinates_included",
        "eye_tracking_included",
        "biometrics_included",
        "real_secrets_included",
        "signed_urls_included",
        "model_calls_performed",
        "user_owned_agent_credentials_included",
    }
    for key in expected_false:
        if privacy.get(key) is not False:
            raise DeliveryClassRegistryError(f"{class_id}.privacy.{key} must stay false")
    for key in (
        "model_calls_performed",
        "production_mutation_performed",
        "external_publication_performed",
    ):
        if runtime.get(key, False) is not False:
            raise DeliveryClassRegistryError(f"{class_id}.runtime.{key} must stay false")
    return {
        "metadata_only": privacy.get("metadata_only") is True,
        "raw_source_text_included": False,
        "raw_report_text_included": False,
        "model_calls_performed": False,
        "production_mutation_performed": False,
        "external_publication_performed": False,
        "user_owned_agent_credentials_included": False,
    }


def validate_delivery_class(definition: Mapping[str, Any], release_check_text: str) -> dict[str, Any]:
    class_id = str(definition["id"])
    report_ref = require_file(str(definition["report"]))
    html_ref = require_file(str(definition["html_report"]))
    doc_ref = require_file(str(definition["doc"]))
    schema_ref = require_file(str(definition["schema"]))
    fixture_root = ROOT / str(definition["fixture_root"])
    if not fixture_root.is_dir():
        raise DeliveryClassRegistryError(f"{class_id} fixture root is missing")

    report = load_json(str(definition["report"]))
    dual_loop.assert_metadata_only(report, label=f"{class_id}-delivery-class-report")
    if report.get("status") != "pass":
        raise DeliveryClassRegistryError(f"{class_id} report status must pass")
    if report.get("delivery_class") != class_id:
        raise DeliveryClassRegistryError(f"{class_id} report delivery_class drifted")

    case_reports = report.get("case_reports")
    if not isinstance(case_reports, list) or len(case_reports) < 2:
        raise DeliveryClassRegistryError(f"{class_id} must include pass and blocked case reports")
    allowed = [row for row in case_reports if isinstance(row, Mapping) and row.get("decision") == definition["allowed_decision"]]
    blocked = [row for row in case_reports if isinstance(row, Mapping) and row.get("decision") == definition["blocked_decision"]]
    if len(allowed) != 1 or not blocked:
        raise DeliveryClassRegistryError(f"{class_id} must have exactly one allowed case and at least one blocked case")

    negative_checks = report.get("negative_checks")
    if not isinstance(negative_checks, Mapping):
        raise DeliveryClassRegistryError(f"{class_id} report missing negative_checks")
    missing_negative = sorted(set(definition["required_negative_checks"]) - set(negative_checks))
    if missing_negative:
        raise DeliveryClassRegistryError(f"{class_id} missing negative checks: {missing_negative}")

    claim_boundary = report.get("claim_boundary")
    if not isinstance(claim_boundary, Mapping) or not claim_boundary.get("current_claim"):
        raise DeliveryClassRegistryError(f"{class_id} report missing claim boundary")
    fixture_count = len(list(fixture_root.glob("*/**/*.json")))
    if fixture_count < len(case_reports):
        raise DeliveryClassRegistryError(f"{class_id} fixture count is lower than case count")

    verifier_command = str(definition["verifier_command"])
    verifier_script = verifier_command.split()[1]
    if verifier_script not in release_check_text:
        raise DeliveryClassRegistryError(f"{class_id} verifier is not wired into release_check.sh")

    return {
        "id": class_id,
        "display_name": definition["display_name"],
        "schema_version": report.get("schema_version"),
        "case_count": len(case_reports),
        "allowed_case_count": len(allowed),
        "blocked_case_count": len(blocked),
        "negative_check_ids": sorted(negative_checks),
        "release_check_integrated": True,
        "verifier_command": verifier_command,
        "claim_boundary_hash": dual_loop.sha256_text(str(claim_boundary.get("current_claim"))),
        "assets": {
            "report": report_ref,
            "html_report": html_ref,
            "doc": doc_ref,
            "schema": schema_ref,
            "fixture_root": str(definition["fixture_root"]),
        },
        "privacy": privacy_from_report(report, class_id),
    }


def build_report() -> dict[str, Any]:
    release_check_text = RELEASE_CHECK.read_text(encoding="utf-8")
    classes = [validate_delivery_class(definition, release_check_text) for definition in DELIVERY_CLASSES]
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": VERSION,
        "delivery_class_count": len(classes),
        "delivery_classes": classes,
        "claim_boundary": {
            "current_claim": (
                "The registry proves delivery classes are wired into metadata-only "
                "Dual Loop / Delivery Trust evidence. It does not prove production "
                "customer delivery, legal certification, or complete factual correctness."
            ),
            "not_claimed": [
                "automatic customer delivery",
                "production trust without external adoption",
                "legal or financial certification",
                "replacement for customer-specific review",
                "general model correctness",
            ],
        },
        "privacy": dict(PRIVACY),
        "acceptance": {
            "minimum_command": "python3 scripts/verify_delivery_class_registry.py --check",
            "registry_report": REPORT.relative_to(ROOT).as_posix(),
        },
    }
    dual_loop.assert_metadata_only(report, label=SCHEMA_VERSION)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check and args.write:
        raise SystemExit("Use only one of --check or --write.")

    report = build_report()
    serialized = dual_loop.dump_json(report)
    html = dual_loop.render_html_report("Delivery Class Registry", report)

    if args.write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(serialized, encoding="utf-8")
        HTML_REPORT.write_text(html, encoding="utf-8")

    if args.check:
        if not REPORT.is_file():
            raise SystemExit(f"Delivery Class registry report is missing: {REPORT.relative_to(ROOT)}")
        if REPORT.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Delivery Class registry report is out of date. "
                "Run: python3 scripts/verify_delivery_class_registry.py --write"
            )
        if not HTML_REPORT.is_file():
            raise SystemExit(f"Delivery Class registry HTML report is missing: {HTML_REPORT.relative_to(ROOT)}")
        if HTML_REPORT.read_text(encoding="utf-8") != html:
            raise SystemExit(
                "Delivery Class registry HTML report is out of date. "
                "Run: python3 scripts/verify_delivery_class_registry.py --write"
            )

    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
