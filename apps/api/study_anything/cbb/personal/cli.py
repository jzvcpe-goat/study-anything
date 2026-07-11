"""Command-line entrypoint for personal-local Delivery Clearance."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from study_anything.cbb.personal.audit import (
    ARTIFACT_RELATIVE_DIR,
    CONFIG_RELATIVE_PATH,
    PersonalClearanceError,
    audit_project,
    initialize_project,
    verify_project_clearance,
    write_audit_artifacts,
)


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _init(args: argparse.Namespace) -> int:
    initialize_project(args.project, force=args.force)
    _print(
        {
            "schema_version": "delivery-clearance.personal-init-result.v1",
            "status": "initialized",
            "config_ref": CONFIG_RELATIVE_PATH.as_posix(),
            "next_steps": [
                "Replace every TODO boundary in the config.",
                "Add project-specific read-only checks.",
                "Run audit with --execute-checks --accept-responsibility.",
            ],
            "claim_boundary": "Initialization does not grant clearance.",
        }
    )
    return 0


def _audit(args: argparse.Namespace) -> int:
    root, artifacts = audit_project(
        args.project,
        execute_checks=args.execute_checks,
        accept_responsibility=args.accept_responsibility,
    )
    write_audit_artifacts(root, artifacts)
    receipt = artifacts.receipt
    _print(
        {
            "schema_version": "delivery-clearance.personal-audit-result.v1",
            "status": receipt.status,
            "approved_scope": receipt.approved_scope.value,
            "receipt_id": receipt.receipt_id,
            "artifact_dir": ARTIFACT_RELATIVE_DIR.as_posix(),
            "report_ref": (
                ARTIFACT_RELATIVE_DIR / "personal-clearance-report.html"
            ).as_posix(),
            "missing_evidence_types": receipt.missing_evidence_types,
            "reasons": receipt.reasons,
            "claim_boundary": receipt.claim_boundary.current_claim,
        }
    )
    if receipt.status == "allow":
        return 0
    if receipt.status == "needs_evidence":
        return 2
    return 3


def _verify(args: argparse.Namespace) -> int:
    _print(verify_project_clearance(args.project))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit one local Git project for personal-local Delivery Clearance."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a local clearance contract")
    init_parser.add_argument("--project", default=".")
    init_parser.add_argument("--force", action="store_true")
    init_parser.set_defaults(func=_init)

    audit_parser = subparsers.add_parser("audit", help="build a scoped personal receipt")
    audit_parser.add_argument("--project", default=".")
    audit_parser.add_argument(
        "--execute-checks",
        action="store_true",
        help="explicitly authorize configured argv checks with current-user permissions",
    )
    audit_parser.add_argument(
        "--accept-responsibility",
        action="store_true",
        help="self-attest the configured boundaries for this run only",
    )
    audit_parser.set_defaults(func=_audit)

    verify_parser = subparsers.add_parser(
        "verify", help="verify receipt integrity, freshness, and current Git state"
    )
    verify_parser.add_argument("--project", default=".")
    verify_parser.set_defaults(func=_verify)

    args = parser.parse_args()
    try:
        return int(args.func(args))
    except PersonalClearanceError as exc:
        print(f"personal clearance error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
