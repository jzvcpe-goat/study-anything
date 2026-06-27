#!/usr/bin/env python3
"""Verify the live stacked PR lineage reaches the target branch."""

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
SCHEMA_VERSION = "release-stack-lineage-v1"
REQUIRED_CHECKS = {"api-tests", "compose-smoke"}
SECRET_PATTERNS = (
    re.compile(r"gho_[A-Za-z0-9_]+"),
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._-]+"),
)


class ReleaseStackLineageError(RuntimeError):
    """Readable release stack lineage verification failure."""


def redact(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}<redacted>" if match.groups() else "<redacted>", redacted)
    return redacted


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReleaseStackLineageError(f"Cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseStackLineageError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ReleaseStackLineageError("Release stack manifest must contain a JSON object.")
    return manifest


def run_gh(args: list[str]) -> Any:
    completed = subprocess.run(["gh", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        stderr = redact(completed.stderr.strip() or completed.stdout.strip())
        raise ReleaseStackLineageError(f"gh {' '.join(args[:3])} failed: {stderr}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ReleaseStackLineageError(f"gh returned invalid JSON: {exc}") from exc


def view_pr(number: int) -> dict[str, Any]:
    payload = run_gh(
        [
            "pr",
            "view",
            str(number),
            "--json",
            "number,headRefName,baseRefName,state,isDraft,mergeCommit,statusCheckRollup",
        ]
    )
    if not isinstance(payload, dict):
        raise ReleaseStackLineageError(f"PR #{number} payload must be an object.")
    return payload


def find_pr_by_head(branch: str) -> dict[str, Any]:
    payload = run_gh(
        [
            "pr",
            "list",
            "--state",
            "all",
            "--head",
            branch,
            "--limit",
            "20",
            "--json",
            "number,headRefName,baseRefName,state,isDraft,mergeCommit,statusCheckRollup",
        ]
    )
    if not isinstance(payload, list):
        raise ReleaseStackLineageError(f"PR list for {branch} must be an array.")
    matches = [item for item in payload if isinstance(item, dict) and item.get("headRefName") == branch]
    if not matches:
        raise ReleaseStackLineageError(f"No GitHub PR found for branch {branch}.")
    open_matches = [item for item in matches if item.get("state") == "OPEN"]
    if len(open_matches) == 1:
        return open_matches[0]
    if len(matches) == 1:
        return matches[0]
    matches.sort(key=lambda item: int(item.get("number", 0)), reverse=True)
    return matches[0]


def summarize_checks(payload: dict[str, Any], required_checks: set[str] = REQUIRED_CHECKS) -> tuple[dict[str, str], list[str]]:
    rollup = payload.get("statusCheckRollup", [])
    if not isinstance(rollup, list):
        raise ReleaseStackLineageError(f"PR #{payload.get('number')} statusCheckRollup must be a list.")
    by_name = {str(item.get("name")): item for item in rollup if isinstance(item, dict)}
    checks: dict[str, str] = {}
    failures: list[str] = []
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


def summarize_pr(
    payload: dict[str, Any],
    expected_head: str | None = None,
    expected_base: str | None = None,
    required_checks: set[str] = REQUIRED_CHECKS,
) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    pr_number = payload.get("number")
    head = payload.get("headRefName")
    base = payload.get("baseRefName")
    state = payload.get("state")
    if expected_head and head != expected_head:
        failures.append(f"PR #{pr_number} head must be {expected_head}.")
    if expected_base and base != expected_base:
        failures.append(f"PR #{pr_number} base must be {expected_base}.")
    if state not in {"OPEN", "MERGED"}:
        failures.append(f"PR #{pr_number} state must be OPEN or MERGED.")
    checks, check_failures = summarize_checks(payload, required_checks)
    failures.extend(check_failures)
    merge_commit = payload.get("mergeCommit") or {}
    return (
        {
            "pr": pr_number,
            "branch": head,
            "base": base,
            "state": state,
            "is_draft": bool(payload.get("isDraft")) if state == "OPEN" else None,
            "merge_commit": merge_commit.get("oid") if isinstance(merge_commit, dict) else None,
            "required_checks": checks,
            "merge_ready": not failures,
        },
        failures,
    )


def verify_lineage(manifest: dict[str, Any], allow_missing_top_pr: bool, max_depth: int) -> dict[str, Any]:
    group = current_group(manifest)
    stack = group.get("stack")
    if not isinstance(stack, list) or not stack:
        raise ReleaseStackLineageError("Release stack manifest must include a non-empty stack.")
    required_checks = required_checks_from(group, str(group.get("group_id")))
    if required_checks != REQUIRED_CHECKS:
        raise ReleaseStackLineageError("Release stack required checks drifted.")
    policy = manifest.get("release_policy")
    if not isinstance(policy, dict):
        raise ReleaseStackLineageError("release_policy must be an object.")
    target_branch = str(policy.get("target_branch"))
    group_status = str(group.get("status"))

    if group_status == "completed":
        lineage: list[dict[str, Any]] = []
        blockers: list[str] = []
        for row in stack:
            if not isinstance(row, dict):
                raise ReleaseStackLineageError("Release stack rows must be objects.")
            pr_number = row.get("pr")
            branch = row.get("branch")
            base = row.get("base")
            expected_merge_commit = row.get("merge_commit")
            if not isinstance(pr_number, int) or not isinstance(branch, str) or not isinstance(base, str):
                raise ReleaseStackLineageError("Completed stack rows must include int pr and string branch/base.")
            payload = view_pr(pr_number)
            summary, failures = summarize_pr(
                payload,
                expected_head=branch,
                expected_base=base,
                required_checks=required_checks,
            )
            if payload.get("state") != "MERGED":
                failures.append(f"PR #{pr_number} must be MERGED in a completed stack group.")
            if summary.get("merge_commit") != expected_merge_commit:
                failures.append(f"PR #{pr_number} merge commit must match the release stack manifest.")
            if base != target_branch:
                failures.append(f"PR #{pr_number} completed base must be {target_branch}.")
            lineage.append(summary)
            blockers.extend(failures)
        reached_target = all(item.get("base") == target_branch for item in lineage)
        status = "pass" if not blockers and reached_target else "blocked"
        return {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "version": manifest.get("version"),
            "current_group": group.get("group_id"),
            "current_group_status": group_status,
            "target_branch": target_branch,
            "top_branch": stack[-1].get("branch") if isinstance(stack[-1], dict) else None,
            "lineage_reaches_target": reached_target,
            "lineage_length": len(lineage),
            "lineage": lineage,
            "blocker_count": len(blockers),
            "blockers": [redact(item) for item in blockers[:10]],
            "privacy": {
                "github_tokens_stored": False,
                "live_check_payloads_stored": False,
                "raw_source_text_included": False,
                "learner_answers_included": False,
                "agent_endpoint_secrets_included": False,
                "real_model_keys_included": False,
            },
        }

    top = stack[-1]
    if not isinstance(top, dict):
        raise ReleaseStackLineageError("Top stack row must be an object.")
    top_pr = top.get("pr")
    top_branch = top.get("branch")
    top_base = top.get("base")
    if not isinstance(top_pr, int) or not isinstance(top_branch, str) or not isinstance(top_base, str):
        raise ReleaseStackLineageError("Top stack row must include int pr and string branch/base.")

    lineage: list[dict[str, Any]] = []
    blockers: list[str] = []
    visited: set[str] = set()
    current_branch = top_branch
    current_base = top_base
    pending_top = False

    try:
        top_payload = view_pr(top_pr)
        top_summary, top_failures = summarize_pr(
            top_payload,
            expected_head=top_branch,
            expected_base=top_base,
            required_checks=required_checks,
        )
        lineage.append(top_summary)
        blockers.extend(top_failures)
        current_base = str(top_payload.get("baseRefName"))
    except ReleaseStackLineageError as exc:
        if not allow_missing_top_pr:
            raise
        pending_top = True
        lineage.append(
            {
                "pr": top_pr,
                "branch": top_branch,
                "base": top_base,
                "state": "pending_pr_creation",
                "is_draft": None,
                "required_checks": {check: "pending_pr_creation" for check in sorted(REQUIRED_CHECKS)},
                "merge_ready": False,
            }
        )
        blockers.append(str(exc))

    for _ in range(max_depth):
        if current_base == target_branch:
            break
        if current_base in visited:
            raise ReleaseStackLineageError(f"Cycle detected while walking lineage at {current_base}.")
        visited.add(current_base)
        payload = find_pr_by_head(current_base)
        summary, failures = summarize_pr(payload, expected_head=current_base, required_checks=required_checks)
        lineage.append(summary)
        blockers.extend(failures)
        current_base = str(payload.get("baseRefName"))
    else:
        raise ReleaseStackLineageError(f"Lineage exceeded max depth {max_depth}.")

    status = "pass"
    if blockers and pending_top:
        status = "pending_top_pr"
    elif blockers:
        status = "blocked"
    reached_target = current_base == target_branch
    if not reached_target and status == "pass":
        status = "blocked"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "version": manifest.get("version"),
        "current_group": group.get("group_id"),
        "current_group_status": group_status,
        "target_branch": target_branch,
        "top_branch": top_branch,
        "lineage_reaches_target": reached_target,
        "lineage_length": len(lineage),
        "lineage": lineage,
        "blocker_count": len(blockers),
        "blockers": [redact(item) for item in blockers[:10]],
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
    parser.add_argument("--allow-missing-top-pr", action="store_true")
    parser.add_argument("--max-depth", type=int, default=80)
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Return exit code 0 even when lineage is blocked, for maintainer diagnostics.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    report = verify_lineage(
        manifest,
        allow_missing_top_pr=args.allow_missing_top_pr,
        max_depth=args.max_depth,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if report["status"] in {"blocked", "pending_top_pr"} and not args.report_only:
        raise ReleaseStackLineageError("Release stack lineage is blocked.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_release_stack_lineage failed: {redact(str(exc))}", file=sys.stderr)
        sys.exit(1)
