#!/usr/bin/env python3
"""Verify deterministic and live GitHub repository security posture."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "github-security-posture-v1"
DEFAULT_REQUIRED_CHECKS = (
    "CodeQL",
    "api-tests",
    "compose-smoke",
    "codeql (python)",
    "container policy",
    "dependency review",
)


class GithubSecurityPostureError(RuntimeError):
    """Readable GitHub security posture failure."""


def require_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise GithubSecurityPostureError(f"{key} must be an object")
    return value


def enabled_status(payload: Mapping[str, Any], key: str) -> bool:
    value = payload.get(key)
    return isinstance(value, Mapping) and value.get("status") == "enabled"


def assess_posture(
    *,
    repository: Mapping[str, Any],
    actions_permissions: Mapping[str, Any],
    branch_protection: Mapping[str, Any],
    dependency_graph_enabled: bool,
    dependabot_alerts_enabled: bool,
    dependabot_security_updates_enabled: bool,
    required_checks: Sequence[str] = DEFAULT_REQUIRED_CHECKS,
    mode: str,
) -> dict[str, Any]:
    security = require_mapping(repository, "security_and_analysis")
    required_status = require_mapping(branch_protection, "required_status_checks")
    observed_checks = {
        str(item.get("context"))
        for item in required_status.get("checks", [])
        if isinstance(item, Mapping) and item.get("context")
    }
    expected_checks = set(required_checks)
    checks = {
        "secret_scanning_enabled": enabled_status(security, "secret_scanning"),
        "push_protection_enabled": enabled_status(
            security,
            "secret_scanning_push_protection",
        ),
        "actions_full_sha_required": actions_permissions.get("sha_pinning_required") is True,
        "branch_protection_enabled": bool(branch_protection),
        "required_checks_strict": required_status.get("strict") is True,
        "required_checks_present": expected_checks.issubset(observed_checks),
        "force_pushes_disabled": branch_protection.get("allow_force_pushes", {}).get("enabled") is False,
        "branch_deletions_disabled": branch_protection.get("allow_deletions", {}).get("enabled") is False,
        "conversation_resolution_required": branch_protection.get(
            "required_conversation_resolution",
            {},
        ).get("enabled")
        is True,
        "stale_branches_deleted_after_merge": repository.get("delete_branch_on_merge") is True,
        "dependency_graph_enabled": dependency_graph_enabled,
        "dependabot_alerts_enabled": dependabot_alerts_enabled,
        "dependabot_security_updates_enabled": dependabot_security_updates_enabled,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not failed else "fail",
        "mode": mode,
        "checks": checks,
        "required_status_checks": sorted(expected_checks),
        "failed_checks": failed,
        "privacy": {
            "metadata_only": True,
            "github_token_included": False,
            "api_response_payloads_included": False,
            "workflow_logs_included": False,
            "repository_secrets_included": False,
            "model_calls_performed": False,
            "production_mutation_performed": False,
        },
        "claim_boundary": (
            "This report proves only the evaluated GitHub repository settings. It does not prove "
            "application correctness, vulnerability absence, production security, or independent audit completion."
        ),
    }


def deterministic_fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    repository = {
        "delete_branch_on_merge": True,
        "security_and_analysis": {
            "secret_scanning": {"status": "enabled"},
            "secret_scanning_push_protection": {"status": "enabled"},
        },
    }
    actions = {"sha_pinning_required": True}
    protection = {
        "required_status_checks": {
            "strict": True,
            "checks": [{"context": name} for name in DEFAULT_REQUIRED_CHECKS],
        },
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "required_conversation_resolution": {"enabled": True},
    }
    return repository, actions, protection


def verify_contract() -> dict[str, Any]:
    repository, actions, protection = deterministic_fixture()
    report = assess_posture(
        repository=repository,
        actions_permissions=actions,
        branch_protection=protection,
        dependency_graph_enabled=True,
        dependabot_alerts_enabled=True,
        dependabot_security_updates_enabled=True,
        mode="deterministic",
    )
    if report["status"] != "pass":
        raise GithubSecurityPostureError("Passing posture fixture was rejected")

    negative_actions = dict(actions)
    negative_actions["sha_pinning_required"] = False
    negative = assess_posture(
        repository=repository,
        actions_permissions=negative_actions,
        branch_protection=protection,
        dependency_graph_enabled=True,
        dependabot_alerts_enabled=True,
        dependabot_security_updates_enabled=True,
        mode="deterministic-negative",
    )
    if negative["status"] != "fail" or "actions_full_sha_required" not in negative["failed_checks"]:
        raise GithubSecurityPostureError("Unpinned Actions posture was not rejected")

    missing_check = json.loads(json.dumps(protection))
    missing_check["required_status_checks"]["checks"] = missing_check["required_status_checks"]["checks"][:-1]
    negative = assess_posture(
        repository=repository,
        actions_permissions=actions,
        branch_protection=missing_check,
        dependency_graph_enabled=True,
        dependabot_alerts_enabled=True,
        dependabot_security_updates_enabled=True,
        mode="deterministic-negative",
    )
    if negative["status"] != "fail" or "required_checks_present" not in negative["failed_checks"]:
        raise GithubSecurityPostureError("Missing required status check was not rejected")
    return report


def gh_json(path: str) -> Mapping[str, Any]:
    completed = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        raise GithubSecurityPostureError(f"GitHub setting read failed for {path.rsplit('/', 1)[-1]}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise GithubSecurityPostureError("GitHub setting read returned invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise GithubSecurityPostureError("GitHub setting read must return an object")
    return payload


def gh_feature_enabled(path: str) -> bool:
    completed = subprocess.run(
        ["gh", "api", path, "--include"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return completed.returncode == 0 and " 204 " in completed.stdout.split("\r\n", 1)[0]


def gh_endpoint_available(path: str) -> bool:
    completed = subprocess.run(
        ["gh", "api", path, "--silent"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return completed.returncode == 0


def verify_live(*, repo: str, branch: str, required_checks: Sequence[str]) -> dict[str, Any]:
    repository = gh_json(f"repos/{repo}")
    actions = gh_json(f"repos/{repo}/actions/permissions")
    protection = gh_json(f"repos/{repo}/branches/{branch}/protection")
    security = require_mapping(repository, "security_and_analysis")
    return assess_posture(
        repository=repository,
        actions_permissions=actions,
        branch_protection=protection,
        dependency_graph_enabled=gh_endpoint_available(f"repos/{repo}/dependency-graph/sbom"),
        dependabot_alerts_enabled=gh_feature_enabled(f"repos/{repo}/vulnerability-alerts"),
        dependabot_security_updates_enabled=enabled_status(security, "dependabot_security_updates"),
        required_checks=required_checks,
        mode="live-read-only",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--repo")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--required-check", action="append", dest="required_checks")
    args = parser.parse_args()
    if args.check == args.live:
        parser.error("choose exactly one of --check or --live")
    try:
        if args.live:
            if not args.repo:
                parser.error("--live requires --repo OWNER/REPO")
            report = verify_live(
                repo=args.repo,
                branch=args.branch,
                required_checks=args.required_checks or DEFAULT_REQUIRED_CHECKS,
            )
        else:
            report = verify_contract()
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        if report["status"] != "pass":
            raise SystemExit(1)
    except GithubSecurityPostureError as exc:
        print(f"verify_github_security_posture failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
