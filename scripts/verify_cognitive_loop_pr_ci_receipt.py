#!/usr/bin/env python3
"""Generate and verify a metadata-only Cognitive Loop PR CI receipt."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-pr-ci-receipt.json"
SCHEMA_VERSION = "cognitive-loop-pr-ci-receipt-v1"
SOURCE_SCHEMA_VERSION = "cognitive-loop-pr-ci-source-v1"
GH_JSON_SCHEMA_VERSION = "cognitive-loop-gh-pr-checks-json-v1"
REQUIRED_CHECKS = ("api-tests", "compose-smoke")
GENERATED_AT = "2026-01-01T00:00:00Z"
SAFE_COMMANDS = (
    "python3 scripts/verify_cognitive_loop_pr_ci_receipt.py --check",
    "python3 scripts/verify_cognitive_loop_maintainer_acceptance_ledger.py --check",
    "gh pr checks <PR> --watch --interval 10",
)
SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bdiff --git\b"),
    re.compile(r"/Users/[^\s\"']+"),
)
PRIVATE_NEEDLES = (
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "raw log:",
    "raw logs:",
    "raw source text:",
    "learner answer:",
    "agent endpoint:",
    "prompt:",
)
POLICY_WEAKENING_PHRASES = (
    "disable privacy",
    "skip privacy",
    "weaken privacy",
    "disable audit",
    "skip audit",
    "disable tests",
    "skip tests",
    "bypass human gate",
    "loosen permissions",
)
UNSAFE_COMMAND_PATTERNS = (
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"\bsudo\b"),
    re.compile(r"\bcurl\b.*\|\s*(?:sh|bash)"),
    re.compile(r"\bwget\b.*\|\s*(?:sh|bash)"),
    re.compile(r"\bgh\s+pr\s+merge\b"),
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bgit\s+reset\s+--hard\b"),
)
PASS_STATUSES = {"pass", "success", "completed", "successful"}
PENDING_STATUSES = {"pending", "queued", "in_progress", "waiting", "unknown", "not_run"}
FAIL_STATUSES = {"fail", "failed", "failure", "cancelled", "canceled", "timed_out", "action_required", "skipped"}
RAW_LOG_KEYS = {"log", "logs", "raw_log", "raw_logs", "raw_output", "stdout", "stderr"}


class PrCiReceiptError(RuntimeError):
    """Readable PR CI receipt failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def assert_public_payload(payload: Any, *, label: str) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lowered = text.lower()
    needles = [needle for needle in PRIVATE_NEEDLES if needle.lower() in lowered]
    patterns = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
    weakening = [phrase for phrase in POLICY_WEAKENING_PHRASES if phrase in lowered]
    if needles or patterns or weakening:
        raise PrCiReceiptError(f"{label} is not public-safe: needles={needles} patterns={patterns} policy={weakening}")


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


def assert_no_raw_logs(payload: Any) -> None:
    hits: list[str] = []
    for mapping in walk_mappings(payload):
        for key, value in mapping.items():
            if str(key).lower() in RAW_LOG_KEYS and value not in (None, False, ""):
                hits.append(str(key))
        if mapping.get("raw_logs_included") is True:
            hits.append("raw_logs_included")
    if hits:
        raise PrCiReceiptError(f"PR CI receipt must not include raw logs: {sorted(set(hits))}")


def validate_safe_commands(commands: list[str]) -> None:
    unknown = [command for command in commands if command not in SAFE_COMMANDS]
    unsafe = [command for command in commands if any(pattern.search(command) for pattern in UNSAFE_COMMAND_PATTERNS)]
    if unknown or unsafe:
        raise PrCiReceiptError(f"Unsafe or unknown PR CI commands: unknown={unknown} unsafe={unsafe}")


def default_source(statuses: Mapping[str, str] | None = None) -> dict[str, Any]:
    status_map = {name: "pass" for name in REQUIRED_CHECKS}
    if statuses:
        status_map.update(statuses)
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "source": "fixture",
        "pr_number": 179,
        "head_sha": "a" * 40,
        "expected_head_sha": "a" * 40,
        "checks": [
            {
                "name": name,
                "status": status_map[name],
                "url": f"https://github.com/jzvcpe-goat/study-anything/actions/runs/redacted-{name}",
            }
            for name in REQUIRED_CHECKS
        ],
        "raw_logs_included": False,
        "operator_next_commands": list(SAFE_COMMANDS),
    }


def load_source(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PrCiReceiptError(f"Cannot read {relative(path)}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PrCiReceiptError(f"{relative(path)} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PrCiReceiptError("PR CI source fixture must be a JSON object.")
    return payload


def normalize_status(status: Any) -> str:
    value = str(status or "").strip().lower().replace("-", "_")
    if value in PASS_STATUSES:
        return "pass"
    if value in PENDING_STATUSES:
        return "pending"
    if value in FAIL_STATUSES:
        return "fail"
    return "unknown"


def normalize_gh_json(payload: Any) -> dict[str, Any]:
    if isinstance(payload, Mapping) and payload.get("schema_version") == GH_JSON_SCHEMA_VERSION:
        checks = payload.get("checks")
        pr_number = payload.get("pr_number", 0)
        head_sha = payload.get("head_sha", "0" * 40)
        expected = payload.get("expected_head_sha", head_sha)
    elif isinstance(payload, list):
        checks = payload
        pr_number = 0
        head_sha = "0" * 40
        expected = head_sha
    elif isinstance(payload, Mapping) and isinstance(payload.get("checks"), list):
        checks = payload.get("checks")
        pr_number = payload.get("pr_number", 0)
        head_sha = payload.get("head_sha", "0" * 40)
        expected = payload.get("expected_head_sha", head_sha)
    else:
        raise PrCiReceiptError("Malformed gh_json input for PR CI receipt.")
    if not isinstance(checks, list):
        raise PrCiReceiptError("gh_json checks must be a list.")
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "source": "gh_json",
        "pr_number": pr_number,
        "head_sha": head_sha,
        "expected_head_sha": expected,
        "checks": [
            {
                "name": str(row.get("name") or row.get("workflowName") or ""),
                "status": normalize_status(row.get("status") or row.get("state") or row.get("conclusion")),
                "url": str(row.get("url") or row.get("link") or ""),
            }
            for row in checks
            if isinstance(row, Mapping)
        ],
        "raw_logs_included": False,
        "operator_next_commands": list(SAFE_COMMANDS),
    }


def validate_source(source: Mapping[str, Any]) -> None:
    if source.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise PrCiReceiptError("PR CI source fixture schema drifted.")
    if source.get("source") not in {"fixture", "gh_json"}:
        raise PrCiReceiptError(f"Unsupported PR CI source: {source.get('source')}")
    head = str(source.get("head_sha") or "")
    expected = str(source.get("expected_head_sha") or head)
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise PrCiReceiptError("PR CI head_sha must be a 40-character lowercase hex SHA.")
    if expected != head:
        raise PrCiReceiptError("PR CI source head_sha does not match expected_head_sha.")
    checks = source.get("checks")
    if not isinstance(checks, list):
        raise PrCiReceiptError("PR CI checks must be a list.")
    commands = list(source.get("operator_next_commands") or SAFE_COMMANDS)
    validate_safe_commands([str(command) for command in commands])
    assert_no_raw_logs(source)
    assert_public_payload(source, label="pr ci source")


def decision_from_checks(checks: list[Mapping[str, Any]]) -> tuple[str, list[str], list[str], list[dict[str, str]]]:
    by_name = {str(row.get("name")): row for row in checks}
    blocking: list[str] = []
    manual: list[str] = []
    rows: list[dict[str, str]] = []
    for check in REQUIRED_CHECKS:
        row = by_name.get(check)
        if row is None:
            blocking.append(f"missing_required_check:{check}")
            continue
        status = normalize_status(row.get("status"))
        rows.append({"name": check, "status": status, "url": str(row.get("url") or "")})
        if status == "pass":
            continue
        if status == "pending" or status == "unknown":
            manual.append(f"ci:{check}:{status}")
        else:
            blocking.append(f"ci:{check}:{status}")
    decision = "blocked" if blocking else "manual_review" if manual else "ready"
    return decision, blocking, manual, rows


def build_receipt(source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    data = dict(source or default_source())
    validate_source(data)
    checks = data.get("checks")
    if not isinstance(checks, list):
        raise PrCiReceiptError("PR CI checks must be a list.")
    decision, blocking, manual, rows = decision_from_checks([row for row in checks if isinstance(row, Mapping)])
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "generated_at": GENERATED_AT,
        "source": data["source"],
        "source_sha256": sha256_text(dump_json(data)),
        "pr_number": int(data.get("pr_number") or 0),
        "head_sha": str(data["head_sha"]),
        "required_checks": list(REQUIRED_CHECKS),
        "checks": rows,
        "decision": decision,
        "blocking_reasons": blocking,
        "manual_review_reasons": manual,
        "privacy_flags": {
            "metadata_only": True,
            "raw_logs_included": False,
            "github_tokens_included": False,
            "job_logs_included": False,
            "model_called": False,
            "source_files_modified": False,
        },
        "operator_next_commands": list(SAFE_COMMANDS),
    }
    assert_public_payload(receipt, label="pr ci receipt")
    return receipt


def expect_failure(name: str, builder: Any) -> bool:
    try:
        builder()
    except PrCiReceiptError:
        return True
    raise RuntimeError(f"Unsafe PR CI receipt fixture was not rejected: {name}")


def verify_failure_modes() -> dict[str, bool]:
    ready = build_receipt(default_source())
    pending = build_receipt(default_source({"api-tests": "pending"}))
    failed = build_receipt(default_source({"compose-smoke": "failed"}))
    if ready["decision"] != "ready" or pending["decision"] != "manual_review" or failed["decision"] != "blocked":
        raise PrCiReceiptError("Ready/manual/blocked fixture decisions are wrong.")

    def missing_required_check() -> None:
        source = default_source()
        source["checks"] = source["checks"][:1]
        receipt = build_receipt(source)
        if receipt["decision"] != "blocked":
            raise PrCiReceiptError("Missing required check did not block.")

    def stale_head_sha() -> None:
        source = default_source()
        source["expected_head_sha"] = "b" * 40
        build_receipt(source)

    def malformed_gh_json() -> None:
        normalize_gh_json({"bad": "shape"})

    def secret_like_url() -> None:
        source = default_source()
        source["checks"][0]["url"] = "https://github.com/?token=abc123456789"
        build_receipt(source)

    def raw_logs() -> None:
        source = default_source()
        source["raw_logs"] = "raw log: failing test output"
        build_receipt(source)

    def unsafe_command() -> None:
        source = default_source()
        source["operator_next_commands"] = ["gh pr merge 123 --merge"]
        build_receipt(source)

    def policy_weakening() -> None:
        source = default_source()
        source["operator_next_commands"] = ["skip tests"]
        build_receipt(source)

    return {
        "ready_fixture_decision": ready["decision"] == "ready",
        "pending_fixture_manual_review": pending["decision"] == "manual_review",
        "failed_fixture_blocked": failed["decision"] == "blocked",
        "missing_required_check_blocks": missing_required_check() is None,
        "stale_head_sha_rejected": expect_failure("stale_head_sha", stale_head_sha),
        "malformed_gh_json_rejected": expect_failure("malformed_gh_json", malformed_gh_json),
        "secret_like_text_rejected": expect_failure("secret_like_url", secret_like_url),
        "raw_logs_rejected": expect_failure("raw_logs", raw_logs),
        "unsafe_command_rejected": expect_failure("unsafe_command", unsafe_command),
        "policy_weakening_rejected": expect_failure("policy_weakening", policy_weakening),
    }


def build_report(source: Mapping[str, Any] | None = None) -> dict[str, Any]:
    receipt = build_receipt(source)
    report = copy.deepcopy(receipt)
    report["failure_modes"] = verify_failure_modes()
    if not all(report["failure_modes"].values()):
        raise PrCiReceiptError(f"Not all PR CI receipt failure modes passed: {report['failure_modes']}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-fixture", help="Read a redacted PR CI fixture or gh-json output.")
    parser.add_argument("--write", action="store_true", help="Write generated PR CI receipt.")
    parser.add_argument("--check", action="store_true", help="Require generated PR CI receipt to be current.")
    parser.add_argument("--output", default=str(REPORT), help="Report path for --write/--check.")
    args = parser.parse_args()
    if args.write and args.check:
        raise PrCiReceiptError("Use only one of --write or --check.")
    try:
        source: Mapping[str, Any] | None = None
        if args.from_fixture:
            loaded = load_source(Path(args.from_fixture))
            source = normalize_gh_json(loaded) if loaded.get("schema_version") == GH_JSON_SCHEMA_VERSION else loaded
        report = build_report(source)
        rendered = dump_json(report)
        output = Path(args.output)
        if not output.is_absolute():
            output = ROOT / output
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            print(f"wrote {relative(output)}")
            return 0
        if args.check:
            current = output.read_text(encoding="utf-8") if output.is_file() else ""
            if current != rendered:
                raise PrCiReceiptError(
                    f"{relative(output)} is stale. Run python3 scripts/verify_cognitive_loop_pr_ci_receipt.py --write."
                )
            print("ok    Cognitive Loop PR CI receipt is up to date")
            return 0
        print(rendered, end="")
        return 0
    except PrCiReceiptError as exc:
        print(f"verify_cognitive_loop_pr_ci_receipt failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
