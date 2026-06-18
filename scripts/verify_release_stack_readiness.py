#!/usr/bin/env python3
"""Verify the offline GitHub release stack merge-readiness manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "platform" / "release-stack.json"
RELEASE_CHECK = ROOT / "scripts" / "release_check.sh"
SCHEMA_VERSION = "study-anything-release-stack-v1"
VERSION = "v0.3.30-alpha"
REQUIRED_CHECKS = {"api-tests", "compose-smoke"}
REQUIRED_BEFORE_TAG = {
    "python3 scripts/verify_release_stack_readiness.py",
    "./scripts/release_check.sh",
    "python3 scripts/verify_launch_acceptance_ledger.py --check",
    "python3 scripts/verify_github_launch_operator_guide.py --check",
    "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree",
}
EXPECTED_STACK = [
    (134, "codex/v0.3.53-cognitive-loop-extracted-pack-smoke"),
    (135, "codex/v0.3.54-platform-handoff-checklist"),
    (136, "codex/v0.3.55-launch-acceptance-ledger"),
    (137, "codex/v0.3.56-github-launch-operator-guide"),
    (138, "codex/v0.3.57-release-stack-readiness"),
    (139, "codex/v0.3.58-live-release-stack-status"),
    (140, "codex/v0.3.59-full-stack-lineage"),
    (141, "codex/v0.3.60-merge-runbook-safety-gate"),
]
PRIVATE_NEEDLES = (
    "gho_",
    "ghp_",
    "github_pat_",
    "sk-proj-",
    "secret_access_key",
    "bearer ",
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "Private source text:",
    "Private answer:",
)
RELEASE_CHECK_COMMAND = "verify_release_stack_readiness.py"


class ReleaseStackReadinessError(RuntimeError):
    """Readable release stack readiness verification failure."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReleaseStackReadinessError(f"Cannot read {path.relative_to(ROOT)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseStackReadinessError(f"{path.relative_to(ROOT)} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseStackReadinessError(f"{path.relative_to(ROOT)} must contain a JSON object.")
    return payload


def reject_private_text(payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).lower()
    leaked = [needle for needle in PRIVATE_NEEDLES if needle.lower() in serialized]
    if leaked:
        raise ReleaseStackReadinessError(f"Release stack manifest contains private or secret-like text: {leaked}")


def verify_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ReleaseStackReadinessError("Release stack schema_version drifted.")
    if manifest.get("version") != VERSION:
        raise ReleaseStackReadinessError("Release stack version drifted.")

    policy = manifest.get("release_policy")
    if not isinstance(policy, dict):
        raise ReleaseStackReadinessError("release_policy must be an object.")
    if policy.get("target_branch") != "main":
        raise ReleaseStackReadinessError("Release stack target_branch must be main.")
    if policy.get("merge_order") != "oldest_to_newest":
        raise ReleaseStackReadinessError("Release stack must merge oldest to newest.")
    before_tag = set(str(item) for item in policy.get("before_tag", []))
    missing_tag_gates = REQUIRED_BEFORE_TAG - before_tag
    if missing_tag_gates:
        raise ReleaseStackReadinessError(f"Release stack missing before_tag gates: {sorted(missing_tag_gates)}")

    checks = set(str(item) for item in manifest.get("required_checks", []))
    if checks != REQUIRED_CHECKS:
        raise ReleaseStackReadinessError(f"Release stack required checks drifted: {sorted(checks)}")

    stack = manifest.get("stack")
    if not isinstance(stack, list) or len(stack) != len(EXPECTED_STACK):
        raise ReleaseStackReadinessError("Release stack must contain the current stacked PR rows.")
    expected_orders = list(range(1, len(stack) + 1))
    orders = [row.get("order") for row in stack if isinstance(row, dict)]
    if orders != expected_orders:
        raise ReleaseStackReadinessError(f"Release stack order must be contiguous: {orders}")

    observed = []
    previous_branch = None
    for index, row in enumerate(stack):
        if not isinstance(row, dict):
            raise ReleaseStackReadinessError("Release stack rows must be objects.")
        expected_pr, expected_branch = EXPECTED_STACK[index]
        if row.get("pr") != expected_pr or row.get("branch") != expected_branch:
            raise ReleaseStackReadinessError(
                f"Release stack row {index + 1} drifted: expected PR {expected_pr} {expected_branch}."
            )
        if index > 0 and row.get("base") != previous_branch:
            raise ReleaseStackReadinessError(
                f"Release stack row {index + 1} base must equal previous branch {previous_branch}."
            )
        if row.get("status_expected_before_merge") != "checks_pass":
            raise ReleaseStackReadinessError(f"Release stack row {index + 1} must require checks_pass.")
        previous_branch = str(row.get("branch"))
        observed.append({"order": row["order"], "pr": row["pr"], "branch": row["branch"], "base": row["base"]})

    privacy = manifest.get("privacy_assertions")
    if not isinstance(privacy, dict):
        raise ReleaseStackReadinessError("privacy_assertions must be an object.")
    for key in (
        "github_tokens_included",
        "live_check_payloads_included",
        "raw_source_text_included",
        "learner_answers_included",
        "agent_endpoint_secrets_included",
        "real_model_keys_included",
    ):
        if privacy.get(key) is not False:
            raise ReleaseStackReadinessError(f"privacy_assertions.{key} must be false.")

    reject_private_text(manifest)
    release_check_text = RELEASE_CHECK.read_text(encoding="utf-8")
    if RELEASE_CHECK_COMMAND not in release_check_text:
        raise ReleaseStackReadinessError("release_check.sh must run verify_release_stack_readiness.py.")
    return {
        "schema_version": "release-stack-readiness-v1",
        "status": "pass",
        "version": VERSION,
        "target_branch": policy["target_branch"],
        "merge_order": policy["merge_order"],
        "stack_prs": [item["pr"] for item in observed],
        "top_branch": observed[-1]["branch"],
        "required_checks": sorted(REQUIRED_CHECKS),
        "before_tag_gate_count": len(before_tag),
        "release_check_includes_verifier": True,
        "privacy_assertions": privacy,
    }


def main() -> None:
    manifest = load_json(MANIFEST)
    report = verify_manifest(manifest)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_release_stack_readiness failed: {exc}", file=sys.stderr)
        sys.exit(1)
