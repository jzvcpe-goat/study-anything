#!/usr/bin/env python3
"""Verify time-bounded dependency advisory risk acceptances."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_FILE = ROOT / "security/advisory-acceptances/GHSA-866g-f22w-33x8.json"
PACKAGE_LOCK = ROOT / "platform/mastra-runtime/package-lock.json"
RUNTIME_SOURCE = ROOT / "platform/mastra-runtime/src"
SECURITY_WORKFLOW = ROOT / ".github/workflows/security.yml"
RELEASE_CHECK = ROOT / "scripts/release_check.sh"
SCHEMA_VERSION = "dependency-risk-acceptance-verification-v1"


class DependencyRiskAcceptanceError(RuntimeError):
    """Readable dependency-risk acceptance failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DependencyRiskAcceptanceError(message)


def read_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DependencyRiskAcceptanceError(f"Cannot read {label}") from exc
    require(isinstance(payload, dict), f"{label} must contain an object")
    return payload


def verify(
    *,
    today: date | None = None,
    acceptance_file: Path = ACCEPTANCE_FILE,
    package_lock: Path = PACKAGE_LOCK,
    runtime_source: Path = RUNTIME_SOURCE,
) -> dict[str, Any]:
    observed_on = today or date.today()
    acceptance = read_object(acceptance_file, label="dependency risk acceptance")
    require(
        acceptance.get("schema_version") == "dependency-risk-acceptance-v1",
        "Dependency risk acceptance schema is invalid",
    )
    require(acceptance.get("advisory_id") == "GHSA-866g-f22w-33x8", "Advisory id changed")
    require(acceptance.get("severity") == "low", "Acceptance is limited to the low advisory")
    require(
        acceptance.get("decision") == "tolerable_risk",
        "Dependency risk decision must be tolerable_risk",
    )
    review_by = date.fromisoformat(str(acceptance.get("review_by")))
    require(observed_on <= review_by, f"Dependency risk acceptance expired on {review_by.isoformat()}")

    package = acceptance.get("package")
    require(isinstance(package, Mapping), "Accepted package metadata is missing")
    lock = read_object(package_lock, label="Mastra package lock")
    packages = lock.get("packages")
    require(isinstance(packages, Mapping), "Mastra package lock packages are missing")
    alias = str(package.get("locked_alias"))
    locked = packages.get(alias)
    require(isinstance(locked, Mapping), "Accepted vulnerable package alias is no longer locked")
    require(
        locked.get("name") == package.get("name")
        and locked.get("version") == package.get("locked_version"),
        "Accepted package identity or version changed; perform a new risk review",
    )

    source_files = sorted(runtime_source.rglob("*.ts"))
    require(bool(source_files), "Mastra runtime source files are missing")
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
    forbidden_runtime_markers = (
        "@ai-sdk/provider-utils",
        "createJsonResponseHandler",
        "createJsonErrorResponseHandler",
        "fetch(",
    )
    matches = [marker for marker in forbidden_runtime_markers if marker in source_text]
    require(not matches, f"Accepted dependency became reachable through runtime source: {matches}")

    reachability = acceptance.get("reachability")
    require(isinstance(reachability, Mapping), "Reachability record is missing")
    for field in (
        "direct_import",
        "affected_response_handlers_called",
        "external_http_response_parsing",
        "model_calls_performed",
        "production_daemon",
    ):
        require(reachability.get(field) is False, f"Reachability field must remain false: {field}")

    workflow_text = SECURITY_WORKFLOW.read_text(encoding="utf-8")
    release_text = RELEASE_CHECK.read_text(encoding="utf-8")
    marker = "verify_dependency_risk_acceptance.py --check"
    require(marker in workflow_text, "Scheduled security workflow is missing the acceptance gate")
    require(marker in release_text, "Release check is missing the acceptance gate")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "advisory_id": acceptance["advisory_id"],
        "severity": acceptance["severity"],
        "decision": acceptance["decision"],
        "review_by": review_by.isoformat(),
        "days_until_review": (review_by - observed_on).days,
        "locked_package": {
            "name": package["name"],
            "version": package["locked_version"],
            "direct_dependency": False,
        },
        "reachability": {
            "direct_import": False,
            "affected_handlers_called": False,
            "external_response_parsing": False,
            "model_calls_performed": False,
            "production_daemon": False,
        },
        "automation": {
            "scheduled_review_gate": True,
            "release_gate": True,
        },
        "privacy": {
            "metadata_only": True,
            "local_absolute_paths_included": False,
            "environment_values_included": False,
            "secrets_included": False,
            "raw_source_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": acceptance["claim_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    try:
        report = verify()
    except (DependencyRiskAcceptanceError, ValueError) as exc:
        print(f"verify_dependency_risk_acceptance failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
