#!/usr/bin/env python3
"""Verify a metadata-only release stack intake candidate from PR summary data."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from verify_release_stack_readiness import (
    MANIFEST,
    REQUIRED_CHECKS,
    SHA_RE,
    VERSION,
    load_json,
    stack_groups,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "fixtures" / "release-stack" / "pr-326-intake-candidate.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-release-stack-intake-candidate.json"
REPORT_SCHEMA_VERSION = "release-stack-intake-candidate-v1"
SOURCE_SCHEMA_VERSION = "release-stack-intake-source-v1"
GENERATED_AT = "2026-01-01T00:00:00Z"
SAFE_OPERATOR_COMMANDS = {
    "python3 scripts/verify_release_stack_intake_candidate.py --check",
    "python3 scripts/verify_release_stack_readiness.py",
    "python3 scripts/verify_release_stack_manifest_fixtures.py --check",
    "python3 scripts/verify_release_stack_candidate_promotion.py --check",
}
EVIDENCE_REFS = [
    "platform/generated/study-anything-release-stack-manifest-fixtures.json",
    "platform/generated/study-anything-platform-bundle.json",
    "platform/generated/study-anything-platform-adoption-pack.json",
    "platform/generated/study-anything-release-asset-adoption.json",
    "platform/generated/study-anything-dual-loop-trust-scenario-pack.json",
    "platform/generated/study-anything-dual-loop-trust-pack-consumer-walkthrough.json",
    "platform/generated/study-anything-product-loop-harness.json",
    "platform/generated/study-anything-delivery-trust-case-harness.json",
    "platform/generated/study-anything-delivery-trust-case-pack.json",
    "platform/generated/study-anything-delivery-trust-case-pack-consumer-walkthrough.json",
    "platform/generated/study-anything-delivery-class-registry.json",
    "platform/generated/study-anything-delivery-class-registry.html",
    "docs/delivery-class-registry.md",
    "scripts/verify_delivery_class_registry.py",
    "platform/generated/study-anything-trust-scenario-catalog.json",
    "platform/generated/study-anything-trust-scenario-catalog.html",
    "docs/trust-scenario-catalog.md",
    "scripts/verify_trust_scenario_catalog.py",
    "platform/generated/study-anything-trust-scenario-decision-gate.json",
    "platform/generated/study-anything-trust-scenario-decision-gate.html",
    "docs/trust-scenario-decision-gate.md",
    "scripts/trust_scenario_decision_gate.py",
    "scripts/verify_trust_scenario_decision_gate.py",
    "docs/code-review-delivery-class.md",
    "docs/client-report-delivery-class.md",
    "platform/generated/study-anything-code-review-delivery-class.json",
    "platform/generated/study-anything-code-review-delivery-class.html",
    "platform/generated/study-anything-client-report-delivery-class.json",
    "platform/generated/study-anything-client-report-delivery-class.html",
    "platform/schemas/delivery-trust/code-review-handoff-case-v1.schema.json",
    "platform/schemas/delivery-trust/client-report-handoff-case-v1.schema.json",
    "scripts/code_review_delivery_class_handoff.py",
    "scripts/verify_code_review_delivery_class_handoff.py",
    "scripts/client_report_delivery_class_handoff.py",
    "scripts/verify_client_report_delivery_class_handoff.py",
    "docs/trust-evidence-handoff-pack.md",
    "platform/generated/study-anything-trust-evidence-handoff-pack.json",
    "platform/generated/study-anything-trust-evidence-handoff-pack.md",
    "platform/generated/study-anything-trust-evidence-handoff-pack.sha256",
    "platform/generated/study-anything-trust-evidence-handoff-pack.zip",
    "platform/generated/study-anything-trust-evidence-handoff-pack-consumer-walkthrough.json",
    "docs/trust-evidence-acceptance-drill.md",
    "platform/generated/study-anything-trust-evidence-acceptance-drill.json",
    "platform/generated/study-anything-trust-evidence-acceptance-drill.md",
    "docs/controlled-handoff-runbook.md",
    "platform/generated/study-anything-controlled-handoff-runbook.json",
    "platform/generated/study-anything-controlled-handoff-runbook.md",
    "docs/customer-delivery-trust-envelope.md",
    "platform/generated/study-anything-customer-delivery-trust-envelope.json",
    "platform/generated/study-anything-customer-delivery-trust-envelope.md",
    "docs/customer-delivery-rehearsal.md",
    "platform/generated/study-anything-customer-delivery-rehearsal.json",
    "platform/generated/study-anything-customer-delivery-rehearsal.md",
    "docs/code-review-operator-handoff-rehearsal.md",
    "platform/generated/study-anything-code-review-operator-handoff-rehearsal.json",
    "platform/generated/study-anything-code-review-operator-handoff-rehearsal.md",
    "docs/client-report-operator-handoff-rehearsal.md",
    "platform/generated/study-anything-client-report-operator-handoff-rehearsal.json",
    "platform/generated/study-anything-client-report-operator-handoff-rehearsal.md",
    "docs/operator-handoff-rehearsal-contract.md",
    "platform/schemas/delivery-trust/operator-handoff-rehearsal-contract-v1.schema.json",
    "platform/generated/study-anything-operator-handoff-rehearsal-contract.json",
    "platform/generated/study-anything-operator-handoff-rehearsal-contract.md",
    "scripts/verify_operator_handoff_rehearsal_contract.py",
    "scripts/generate_trust_evidence_handoff_pack.py",
    "scripts/verify_trust_evidence_handoff_pack_consumer_walkthrough.py",
    "scripts/verify_trust_evidence_acceptance_drill.py",
    "scripts/verify_controlled_handoff_runbook.py",
    "scripts/verify_customer_delivery_trust_envelope.py",
    "scripts/verify_customer_delivery_rehearsal.py",
    "scripts/verify_code_review_operator_handoff_rehearsal.py",
    "scripts/verify_client_report_operator_handoff_rehearsal.py",
    "platform/generated/study-anything-client-report-delivery-class.json",
    "platform/generated/study-anything-client-report-delivery-class.html",
    "platform/schemas/delivery-trust/client-report-handoff-case-v1.schema.json",
]
FALSE_PRIVACY_FLAGS = {
    "github_tokens_included": False,
    "job_logs_included": False,
    "check_annotations_included": False,
    "artifacts_included": False,
    "live_check_payloads_included": False,
    "source_mutation_performed": False,
    "raw_source_text_included": False,
    "learner_answers_included": False,
    "agent_endpoint_secrets_included": False,
    "real_model_keys_included": False,
}
PRIVATE_NEEDLES = (
    "gho_",
    "ghp_",
    "github_pat_",
    "sk-proj-",
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "raw log:",
    "raw logs:",
    "job log:",
    "artifact:",
    "annotation:",
    "raw source text:",
    "learner answer:",
    "agent endpoint:",
)
RAW_PAYLOAD_KEYS = {
    "annotation",
    "annotations",
    "artifact",
    "artifacts",
    "job_log",
    "job_logs",
    "log",
    "logs",
    "raw_log",
    "raw_logs",
    "raw_output",
    "step_log",
    "step_logs",
    "stderr",
    "stdout",
}
UNSAFE_COMMAND_PATTERNS = (
    re.compile(r"\bgh\s+api\b.*(?:logs|artifacts)"),
    re.compile(r"\bgh\s+run\s+download\b"),
    re.compile(r"\bgh\s+pr\s+merge\b"),
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bgit\s+reset\s+--hard\b"),
    re.compile(r"\bcurl\b.*\|\s*(?:sh|bash)"),
    re.compile(r"\bwget\b.*\|\s*(?:sh|bash)"),
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"\bsudo\b"),
)


class ReleaseStackIntakeError(RuntimeError):
    """Readable release stack intake-candidate failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def redact(text: str) -> str:
    redacted = text
    for needle in PRIVATE_NEEDLES:
        redacted = re.sub(re.escape(needle), "<redacted>", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._-]+", r"\1<redacted>", redacted)
    redacted = re.sub(r"github_pat_[A-Za-z0-9_]+", "<redacted>", redacted)
    redacted = re.sub(r"gh[op]_[A-Za-z0-9_]+", "<redacted>", redacted)
    redacted = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "<redacted>", redacted)
    return redacted


def reject_private_text(payload: Any, label: str) -> None:
    serialized = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lowered = serialized.lower()
    hits = [needle for needle in PRIVATE_NEEDLES if needle.lower() in lowered]
    if hits:
        raise ReleaseStackIntakeError(f"{label} contains private or unsafe text: {hits}")


def walk_mappings(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        found.append(value)
        for child in value.values():
            found.extend(walk_mappings(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(walk_mappings(child))
    return found


def reject_raw_payloads(payload: Any) -> None:
    hits: list[str] = []
    for mapping in walk_mappings(payload):
        for key, value in mapping.items():
            key_text = str(key).lower()
            if key_text in RAW_PAYLOAD_KEYS and value not in (None, False, "", []):
                hits.append(str(key))
            if key_text.endswith("_included") and key_text in {
                "raw_logs_included",
                "job_logs_included",
                "artifacts_included",
                "check_annotations_included",
                "github_tokens_included",
            } and value is not False:
                hits.append(str(key))
    if hits:
        raise ReleaseStackIntakeError(f"Release stack intake source must not include raw CI payloads: {sorted(set(hits))}")


def sanitize_url(value: Any) -> str:
    if value in (None, ""):
        return ""
    url = str(value)
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ReleaseStackIntakeError("Release stack intake URLs must be github.com HTTPS URLs.")
    if parsed.query or parsed.fragment:
        raise ReleaseStackIntakeError("Release stack intake URLs must not include query strings or fragments.")
    if any(part in parsed.path.lower() for part in ("/logs", "/artifacts")):
        raise ReleaseStackIntakeError("Release stack intake URLs must not point to logs or artifacts.")
    reject_private_text(url, "release stack intake url")
    return url


def default_operator_commands(pr_number: int) -> list[str]:
    return [
        "python3 scripts/verify_release_stack_intake_candidate.py --check",
        f"python3 scripts/verify_release_stack_intake_candidate.py --from-gh-pr {pr_number} --report-only",
        "python3 scripts/verify_release_stack_readiness.py",
        "python3 scripts/verify_release_stack_manifest_fixtures.py --check",
        "python3 scripts/verify_release_stack_candidate_promotion.py --check",
    ]


def validate_operator_commands(commands: Any, *, pr_number: int) -> list[str]:
    if not isinstance(commands, list) or not commands:
        raise ReleaseStackIntakeError("operator_commands must be a non-empty list.")
    normalized = [str(command) for command in commands]
    allowed_commands = set(SAFE_OPERATOR_COMMANDS)
    allowed_commands.add(f"python3 scripts/verify_release_stack_intake_candidate.py --from-gh-pr {pr_number} --report-only")
    unknown = [command for command in normalized if command not in allowed_commands]
    unsafe = [command for command in normalized if any(pattern.search(command) for pattern in UNSAFE_COMMAND_PATTERNS)]
    if unknown or unsafe:
        raise ReleaseStackIntakeError(f"Unsafe release stack intake commands: unknown={unknown} unsafe={unsafe}")
    return normalized


def represented_prs(manifest: dict[str, Any]) -> set[int]:
    seen: set[int] = set()
    for group in stack_groups(manifest):
        for row in group.get("stack", []):
            if isinstance(row, dict) and isinstance(row.get("pr"), int):
                seen.add(row["pr"])
    return seen


def normalize_merge_commit(source: Mapping[str, Any]) -> str:
    value = source.get("merge_commit")
    if isinstance(value, str):
        commit = value
    else:
        merge = source.get("mergeCommit")
        commit = str(merge.get("oid")) if isinstance(merge, Mapping) else ""
    if not SHA_RE.match(commit):
        raise ReleaseStackIntakeError("Release stack intake merge commit must be a 40-character lowercase SHA.")
    return commit


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        return str(value.get("name") or value.get("id") or "")
    return str(value)


def normalize_status(row: Mapping[str, Any]) -> str:
    status = scalar(row.get("status") or row.get("state") or row.get("bucket")).upper()
    conclusion = scalar(row.get("conclusion")).upper()
    if status in {"COMPLETED", "SUCCESS"} and conclusion in {"", "SUCCESS"}:
        return "pass"
    if status in {"PASS", "PASSED", "SUCCESS", "SUCCESSFUL"}:
        return "pass"
    if conclusion == "SUCCESS":
        return "pass"
    if status or conclusion:
        return f"{status.lower() or 'unknown'}:{conclusion.lower() or 'unknown'}"
    return "missing"


def normalize_checks(source: Mapping[str, Any]) -> dict[str, str]:
    rows = source.get("checks") or source.get("statusCheckRollup")
    if not isinstance(rows, list):
        raise ReleaseStackIntakeError("Release stack intake source checks must be a list.")
    checks: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ReleaseStackIntakeError("Release stack intake check rows must be objects.")
        name = scalar(row.get("name") or row.get("workflowName") or row.get("workflow"))
        if not name:
            continue
        sanitize_url(row.get("details_url") or row.get("url") or row.get("link") or "")
        checks[name] = normalize_status(row)
    missing = sorted(REQUIRED_CHECKS - set(checks))
    if missing:
        raise ReleaseStackIntakeError(f"Release stack intake missing required checks: {missing}")
    failed = {name: checks[name] for name in sorted(REQUIRED_CHECKS) if checks[name] != "pass"}
    if failed:
        raise ReleaseStackIntakeError(f"Release stack intake required checks must pass: {failed}")
    return {name: checks[name] for name in sorted(REQUIRED_CHECKS)}


def load_source(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if payload.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise ReleaseStackIntakeError("Release stack intake source schema_version drifted.")
    return payload


def run_gh_pr_view(pr_number: int) -> dict[str, Any]:
    command = [
        "gh",
        "pr",
        "view",
        str(pr_number),
        "--json",
        "number,title,headRefName,baseRefName,state,mergeCommit,statusCheckRollup,url",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise ReleaseStackIntakeError(redact(completed.stderr.strip() or completed.stdout.strip()))
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ReleaseStackIntakeError(f"gh returned invalid JSON for PR #{pr_number}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseStackIntakeError(f"gh returned a non-object payload for PR #{pr_number}.")
    return payload


def privacy_flags() -> dict[str, bool]:
    return {"metadata_only": True, **FALSE_PRIVACY_FLAGS}


def group_slug(branch: str) -> str:
    slug = branch
    if slug.startswith("codex/"):
        slug = slug[len("codex/") :]
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", slug).strip("-").lower()
    return slug or "unknown"


def validate_evidence_refs(refs: list[str]) -> None:
    for ref in refs:
        path = Path(ref)
        if path.is_absolute() or ".." in path.parts:
            raise ReleaseStackIntakeError(f"Release stack intake evidence ref is unsafe: {ref}")
        if not (ROOT / path).exists():
            raise ReleaseStackIntakeError(f"Release stack intake evidence ref is missing: {ref}")


def build_report(
    source: Mapping[str, Any],
    manifest: dict[str, Any],
    *,
    include_negative_fixtures: bool = True,
    allow_represented: bool = True,
) -> dict[str, Any]:
    reject_private_text(source, "release stack intake source")
    reject_raw_payloads(source)

    pr_number = source.get("pr_number") or source.get("number")
    if not isinstance(pr_number, int):
        raise ReleaseStackIntakeError("Release stack intake source must include int pr_number.")
    is_represented = pr_number in represented_prs(manifest)
    if is_represented and not allow_represented:
        raise ReleaseStackIntakeError(f"PR #{pr_number} is already represented in release-stack manifest.")

    branch = scalar(source.get("head_branch") or source.get("headRefName"))
    base = scalar(source.get("base_branch") or source.get("baseRefName"))
    title = scalar(source.get("title"))
    state = scalar(source.get("state")).upper()
    if not branch or not base:
        raise ReleaseStackIntakeError("Release stack intake source must include head/base branch.")
    target_branch = scalar(manifest.get("release_policy", {}).get("target_branch"))
    if base != target_branch:
        raise ReleaseStackIntakeError(f"Release stack intake base must be {target_branch}.")
    if state != "MERGED":
        raise ReleaseStackIntakeError("Release stack intake source must be a merged PR.")

    merge_commit = normalize_merge_commit(source)
    checks = normalize_checks(source)
    commands = validate_operator_commands(source.get("operator_commands") or default_operator_commands(pr_number), pr_number=pr_number)
    validate_evidence_refs(EVIDENCE_REFS)

    current_group = manifest.get("current_group")
    candidate_group = {
        "group_id": f"release-stack-intake-pr-{pr_number}-{group_slug(branch)}",
        "role": "candidate",
        "status": "completed",
        "summary": f"Candidate release stack group for PR #{pr_number}: {title or branch}.",
        "target_branch": target_branch,
        "required_checks": sorted(REQUIRED_CHECKS),
        "privacy_assertions": privacy_flags(),
        "operator_commands": commands,
        "post_merge_evidence_refs": list(EVIDENCE_REFS),
        "stack": [
            {
                "order": 1,
                "pr": pr_number,
                "branch": branch,
                "base": base,
                "status_expected_before_merge": "checks_pass",
                "final_state": "MERGED",
                "merge_commit": merge_commit,
                "required_checks": checks,
                "evidence_refs": list(EVIDENCE_REFS),
            }
        ],
    }
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": manifest.get("version", VERSION),
        "generated_at": GENERATED_AT,
        "source": scalar(source.get("source") or "gh_pr_view"),
        "manifest": {
            "current_group": current_group,
            "candidate_is_not_applied": not is_represented,
            "candidate_is_represented": is_represented,
            "represented_pr_count": len(represented_prs(manifest)),
        },
        "candidate_group": candidate_group,
        "negative_fixtures": run_negative_fixtures(source, manifest, pr_number) if include_negative_fixtures else [],
        "privacy": {
            "metadata_only": True,
            "github_tokens_stored": False,
            "job_logs_stored": False,
            "check_annotations_stored": False,
            "artifacts_stored": False,
            "live_check_payloads_stored": False,
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "source_mutation_performed": False,
            "manifest_mutated": False,
        },
    }
    reject_private_text(report, "release stack intake report")
    return report


def run_negative_case(case_id: str, source: Mapping[str, Any], manifest: dict[str, Any]) -> str:
    try:
        build_report(
            source,
            manifest,
            include_negative_fixtures=False,
            allow_represented=case_id != "already_represented_pr",
        )
    except ReleaseStackIntakeError as exc:
        return str(exc)
    raise ReleaseStackIntakeError(f"Negative release stack intake fixture was not rejected: {case_id}")


def run_negative_fixtures(source: Mapping[str, Any], manifest: dict[str, Any], pr_number: int) -> list[dict[str, str]]:
    cases: list[tuple[str, dict[str, Any]]] = []

    missing_merge = copy.deepcopy(dict(source))
    missing_merge["merge_commit"] = "not-a-sha"
    if "mergeCommit" in missing_merge:
        missing_merge["mergeCommit"] = {"oid": "not-a-sha"}
    cases.append(("missing_merge_commit", missing_merge))

    failed_check = copy.deepcopy(dict(source))
    failed_check["checks"] = [
        {"name": "api-tests", "status": "COMPLETED", "conclusion": "FAILURE"},
        {"name": "compose-smoke", "status": "COMPLETED", "conclusion": "SUCCESS"},
    ]
    failed_check.pop("statusCheckRollup", None)
    cases.append(("failed_required_check", failed_check))

    missing_check = copy.deepcopy(dict(source))
    missing_check["checks"] = [{"name": "api-tests", "status": "COMPLETED", "conclusion": "SUCCESS"}]
    missing_check.pop("statusCheckRollup", None)
    cases.append(("missing_required_check", missing_check))

    unsafe_command = copy.deepcopy(dict(source))
    unsafe_command["operator_commands"] = ["gh api repos/jzvcpe-goat/study-anything/actions/jobs/1/logs"]
    cases.append(("unsafe_command", unsafe_command))

    secret_payload = copy.deepcopy(dict(source))
    secret_payload["job_logs"] = "github_pat_unsafe raw log: do not store"
    cases.append(("secret_log_artifact_payload", secret_payload))

    represented = copy.deepcopy(dict(source))
    represented["pr_number"] = 180
    represented["number"] = 180
    cases.append(("already_represented_pr", represented))

    results = []
    for case_id, fixture in cases:
        error = run_negative_case(case_id, fixture, manifest)
        results.append({"case_id": case_id, "status": "rejected", "error": redact(error)})
    expected = {
        "missing_merge_commit",
        "failed_required_check",
        "missing_required_check",
        "unsafe_command",
        "secret_log_artifact_payload",
        "already_represented_pr",
    }
    observed = {item["case_id"] for item in results}
    if observed != expected:
        raise ReleaseStackIntakeError(f"Release stack intake negative fixture coverage drifted for PR #{pr_number}.")
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--write", action="store_true", help="Write the generated fixture-mode intake report.")
    parser.add_argument("--check", action="store_true", help="Require the generated fixture-mode intake report to be current.")
    parser.add_argument("--report-only", action="store_true", help="Print the report without writing or checking.")
    parser.add_argument("--from-gh-pr", type=int, help="Build the report from live gh PR summary metadata.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_json(args.manifest)
    source = run_gh_pr_view(args.from_gh_pr) if args.from_gh_pr else load_source(args.source)
    report = build_report(source, manifest)

    if args.from_gh_pr and (args.write or args.check):
        raise ReleaseStackIntakeError("Live gh intake mode is report-only; use fixture mode for --write or --check.")
    if args.write:
        REPORT.write_text(dump_json(report), encoding="utf-8")
        return
    if args.check:
        expected = dump_json(report)
        try:
            actual = REPORT.read_text(encoding="utf-8")
        except OSError as exc:
            raise ReleaseStackIntakeError(f"Cannot read {REPORT.relative_to(ROOT)}: {exc}") from exc
        if actual != expected:
            raise ReleaseStackIntakeError(
                "Release stack intake candidate report is stale. Run: "
                "python3 scripts/verify_release_stack_intake_candidate.py --write"
            )
        print("ok    release stack intake candidate report is up to date")
        return
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"verify_release_stack_intake_candidate failed: {redact(str(exc))}", file=sys.stderr)
        sys.exit(1)
