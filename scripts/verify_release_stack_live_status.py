#!/usr/bin/env python3
"""Verify live GitHub PR status for the release stack without persisting payloads."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from verify_release_stack_readiness import current_group, required_checks_from


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "platform" / "release-stack.json"
SCHEMA_VERSION = "release-stack-live-status-v1"
REQUIRED_CHECKS = {"api-tests", "compose-smoke"}
SECRET_PATTERNS = (
    re.compile(r"gho_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._-]+"),
)


class LiveStackStatusError(RuntimeError):
    """Readable release stack live-status failure."""


def redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}<redacted>" if match.groups() else "<redacted>", redacted)
    return redacted


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LiveStackStatusError(f"Cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LiveStackStatusError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise LiveStackStatusError("Release stack manifest must contain a JSON object.")
    return manifest


def run_gh_pr_view(number: int) -> dict[str, Any]:
    command = [
        "gh",
        "pr",
        "view",
        str(number),
        "--json",
        "number,headRefName,baseRefName,state,isDraft,mergeCommit,statusCheckRollup,url",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        stderr = redact(completed.stderr.strip() or completed.stdout.strip())
        raise LiveStackStatusError(f"Cannot inspect PR #{number}: {stderr}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LiveStackStatusError(f"gh returned invalid JSON for PR #{number}: {exc}") from exc
    if not isinstance(payload, dict):
        raise LiveStackStatusError(f"gh returned a non-object payload for PR #{number}.")
    return payload


def summarize_checks(payload: dict[str, Any], required_checks: set[str]) -> tuple[dict[str, str], list[str]]:
    checks: dict[str, str] = {}
    failures: list[str] = []
    rollup = payload.get("statusCheckRollup", [])
    if not isinstance(rollup, list):
        raise LiveStackStatusError(f"PR #{payload.get('number')} statusCheckRollup must be a list.")
    by_name = {str(item.get("name")): item for item in rollup if isinstance(item, dict)}
    for check_name in sorted(required_checks):
        item = by_name.get(check_name)
        if not item:
            checks[check_name] = "missing"
            failures.append(f"PR #{payload.get('number')} missing required check {check_name}.")
            continue
        status = str(item.get("status"))
        conclusion = str(item.get("conclusion"))
        if status == "COMPLETED" and conclusion == "SUCCESS":
            checks[check_name] = "pass"
        else:
            checks[check_name] = f"{status.lower()}:{conclusion.lower()}"
            failures.append(f"PR #{payload.get('number')} required check {check_name} is {checks[check_name]}.")
    return checks, failures


def verify_live_stack(manifest: dict[str, Any], allow_missing_top_pr: bool) -> dict[str, Any]:
    group = current_group(manifest)
    stack = group.get("stack")
    if not isinstance(stack, list) or not stack:
        raise LiveStackStatusError("Release stack manifest must include a non-empty stack.")
    required_checks = required_checks_from(group, str(group.get("group_id")))
    if required_checks != REQUIRED_CHECKS:
        raise LiveStackStatusError(f"Release stack required checks drifted: {sorted(required_checks)}")
    group_status = str(group.get("status"))
    target_branch = str(group.get("target_branch") or manifest.get("release_policy", {}).get("target_branch"))

    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    missing_allowed = False
    previous_branch = None
    for index, row in enumerate(stack):
        if not isinstance(row, dict):
            raise LiveStackStatusError("Release stack rows must be objects.")
        pr_number = row.get("pr")
        branch = row.get("branch")
        base = row.get("base")
        if not isinstance(pr_number, int) or not isinstance(branch, str) or not isinstance(base, str):
            raise LiveStackStatusError(f"Release stack row {index + 1} must include int pr and string branch/base.")
        if group_status == "open" and index > 0 and base != previous_branch:
            raise LiveStackStatusError(f"Release stack row {index + 1} base must equal previous branch {previous_branch}.")
        previous_branch = branch

        try:
            payload = run_gh_pr_view(pr_number)
        except LiveStackStatusError as exc:
            if allow_missing_top_pr and index == len(stack) - 1:
                missing_allowed = True
                rows.append(
                    {
                        "order": row.get("order"),
                        "pr": pr_number,
                        "branch": branch,
                        "base": base,
                        "state": "pending_pr_creation",
                        "is_draft": None,
                        "required_checks": {check: "pending_pr_creation" for check in sorted(required_checks)},
                        "merge_ready": False,
                    }
                )
                failures.append(str(exc))
                continue
            raise

        row_failures: list[str] = []
        if payload.get("number") != pr_number:
            row_failures.append(f"PR #{pr_number} returned mismatched number {payload.get('number')}.")
        if payload.get("headRefName") != branch:
            row_failures.append(f"PR #{pr_number} head must be {branch}.")
        if payload.get("baseRefName") != base:
            row_failures.append(f"PR #{pr_number} base must be {base}.")
        if group_status == "completed":
            if payload.get("state") != "MERGED":
                row_failures.append(f"PR #{pr_number} must be MERGED in a completed stack group.")
            merge_commit = payload.get("mergeCommit") or {}
            expected_merge_commit = row.get("merge_commit")
            if not isinstance(merge_commit, dict) or merge_commit.get("oid") != expected_merge_commit:
                row_failures.append(f"PR #{pr_number} merge commit must match the release stack manifest.")
            if base != target_branch:
                row_failures.append(f"PR #{pr_number} completed base must be {target_branch}.")
        elif payload.get("state") != "OPEN":
            row_failures.append(f"PR #{pr_number} must be OPEN before stack merge.")
        checks, check_failures = summarize_checks(payload, required_checks)
        row_failures.extend(check_failures)
        failures.extend(row_failures)
        rows.append(
            {
                "order": row.get("order"),
                "pr": pr_number,
                "branch": branch,
                "base": base,
                "state": payload.get("state"),
                "merge_commit": (payload.get("mergeCommit") or {}).get("oid")
                if isinstance(payload.get("mergeCommit"), dict)
                else None,
                "is_draft": bool(payload.get("isDraft")),
                "required_checks": checks,
                "merge_ready": not row_failures,
            }
        )

    status = "pass"
    if failures and missing_allowed:
        status = "pending_top_pr"
    elif failures:
        status = "fail"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "version": manifest.get("version"),
        "current_group": group.get("group_id"),
        "current_group_status": group_status,
        "target_branch": manifest.get("release_policy", {}).get("target_branch"),
        "merge_order": manifest.get("release_policy", {}).get("merge_order"),
        "required_checks": sorted(required_checks),
        "stack": rows,
        "privacy": {
            "github_tokens_stored": False,
            "live_check_payloads_stored": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--allow-missing-top-pr",
        action="store_true",
        help="Exit successfully when the final manifest row is the PR being prepared but not created yet.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    report = verify_live_stack(manifest, allow_missing_top_pr=args.allow_missing_top_pr)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report["status"] == "fail":
        raise LiveStackStatusError("Release stack live status is not merge-ready.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_release_stack_live_status failed: {redact(str(exc))}", file=sys.stderr)
        sys.exit(1)
