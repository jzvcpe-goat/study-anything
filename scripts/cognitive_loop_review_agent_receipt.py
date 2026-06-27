#!/usr/bin/env python3
"""Build and validate metadata-only Cognitive Loop Review Agent CI receipts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
REPORT_VERIFIER_PATH = ROOT / "scripts" / "verify_cognitive_loop_review_agent_report.py"

RECEIPT_SCHEMA_VERSION = "cognitive-loop-review-agent-ci-receipt-v1"
REPORT_SCHEMA_PATH = "platform/schemas/cognitive-loop-review-agent-report.schema.json"
DEFAULT_VALIDATION_COMMAND = "python3 scripts/cognitive_loop_review_agent_handoff.py validate --report REVIEW_AGENT_REPORT.json"

SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"https?://[^/\s:]+:[^@\s]+@"),
)
FORBIDDEN_LITERALS = (
    "diff --git",
    "@@ ",
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "Private learner answer",
    "Private source text",
    "raw source text",
    "hidden chain-of-thought",
    "http://private-agent.local",
    "subprocess.run(user_command",
)


class ReviewAgentReceiptError(RuntimeError):
    """Readable Review Agent receipt failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewAgentReceiptError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewAgentReceiptError(f"JSON object expected: {path}")
    return value


def load_report_verifier() -> Any:
    spec = importlib.util.spec_from_file_location(
        "study_anything_review_agent_report_verifier",
        REPORT_VERIFIER_PATH,
    )
    if spec is None or spec.loader is None:
        raise ReviewAgentReceiptError(f"Cannot load report verifier: {REPORT_VERIFIER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def reject_private_text(value: Any, *, label: str) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    leaked_literals = [needle for needle in FORBIDDEN_LITERALS if needle in serialized]
    leaked_patterns = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(serialized)]
    if leaked_literals or leaked_patterns:
        raise ReviewAgentReceiptError(
            f"{label} contains private report, raw diff, or secret text: "
            f"literals={leaked_literals} patterns={leaked_patterns}"
        )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentReceiptError(message)


def require_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReviewAgentReceiptError(f"Expected non-empty string field: {key}")
    return value


def require_bool(mapping: Mapping[str, Any], key: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ReviewAgentReceiptError(f"Expected boolean field: {key}")
    return value


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def human_action_for(decision: str) -> str:
    if decision == "needs-fix":
        return "fix_required_before_merge"
    if decision == "needs-review":
        return "maintainer_review_required"
    return "merge_allowed_after_required_checks"


def build_receipt_payload(
    report_payload: Mapping[str, Any],
    *,
    report_sha256: str,
    source_report_name: str,
    provider_id: str,
    provider_label: str,
    execution_surface: str,
    pr_ref: str,
    commit_sha: str,
    base_ref: str,
    head_ref: str,
    generated_at: str,
    validation_command: str = DEFAULT_VALIDATION_COMMAND,
) -> dict[str, Any]:
    verifier = load_report_verifier()
    summary = verifier.validate_report(report_payload, fixture_name=source_report_name)
    verifier.reject_private_text(report_payload, label=f"{source_report_name} source report")

    metrics = report_payload.get("metrics", {})
    ci = report_payload.get("ci_instructions", {})
    receipt_basis = "\n".join(
        [
            provider_id,
            execution_surface,
            pr_ref,
            commit_sha,
            report_sha256,
            str(summary["decision"]),
            str(summary["overall_risk"]),
        ]
    )
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "status": "pass",
        "receipt_id": f"review-agent-ci-{sha256_text(receipt_basis)[:16]}",
        "generated_at": generated_at,
        "review_agent": {
            "provider_id": provider_id,
            "provider_label": provider_label,
            "execution_surface": execution_surface,
            "user_owned_agent": True,
            "study_anything_executed_real_model": False,
        },
        "source": {
            "pr_ref": pr_ref,
            "commit_sha": commit_sha,
            "base_ref": base_ref,
            "head_ref": head_ref,
        },
        "validated_report": {
            "source_report_name": source_report_name,
            "report_sha256": report_sha256,
            "report_schema": REPORT_SCHEMA_PATH,
            "report_version": report_payload.get("report_version"),
            "decision": summary["decision"],
            "overall_risk": summary["overall_risk"],
            "finding_count": summary["finding_count"],
            "suppressed_count": summary["suppressed_count"],
            "critical_count": summary["critical_count"],
            "warn_count": summary["warn_count"],
            "info_count": summary["info_count"],
            "total_files_changed": metrics.get("total_files_changed"),
            "total_lines_changed": metrics.get("total_lines_changed"),
            "review_dimensions_covered": metrics.get("review_dimensions_covered", []),
        },
        "ci": {
            "validation_command": validation_command,
            "receipt_validation_command": "python3 scripts/cognitive_loop_review_agent_receipt.py validate --receipt RECEIPT.json",
            "release_gate": "python3 scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check",
            "should_block_merge": ci.get("should_block_merge"),
            "required_human_review": ci.get("required_human_review"),
            "labels_to_add": ci.get("labels_to_add", []),
            "human_action": human_action_for(str(summary["decision"])),
        },
        "privacy": {
            "raw_diff_included": False,
            "file_bodies_included": False,
            "finding_evidence_included": False,
            "report_summary_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "hidden_chain_of_thought_included": False,
            "only_report_hash_persisted": True,
            "safe_to_attach_to_pr": True,
        },
    }
    validate_receipt_payload(receipt)
    return receipt


def build_receipt(args: argparse.Namespace) -> dict[str, Any]:
    report_path = Path(args.report).resolve()
    report_text = report_path.read_text(encoding="utf-8")
    report_payload = json.loads(report_text)
    if not isinstance(report_payload, dict):
        raise ReviewAgentReceiptError(f"JSON object expected: {report_path}")
    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return build_receipt_payload(
        report_payload,
        report_sha256=hashlib.sha256(report_text.encode("utf-8")).hexdigest(),
        source_report_name=report_path.name,
        provider_id=args.provider_id,
        provider_label=args.provider_label,
        execution_surface=args.execution_surface,
        pr_ref=args.pr_ref,
        commit_sha=args.commit_sha,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        generated_at=generated_at,
        validation_command=args.validation_command,
    )


def validate_receipt_payload(receipt: Mapping[str, Any]) -> dict[str, Any]:
    require(receipt.get("schema_version") == RECEIPT_SCHEMA_VERSION, "Receipt schema_version drifted.")
    require(receipt.get("status") == "pass", "Receipt status must be pass.")
    require_string(receipt, "receipt_id")
    require_string(receipt, "generated_at")
    agent = receipt.get("review_agent")
    source = receipt.get("source")
    report = receipt.get("validated_report")
    ci = receipt.get("ci")
    privacy = receipt.get("privacy")
    require(isinstance(agent, Mapping), "review_agent must be an object.")
    require(isinstance(source, Mapping), "source must be an object.")
    require(isinstance(report, Mapping), "validated_report must be an object.")
    require(isinstance(ci, Mapping), "ci must be an object.")
    require(isinstance(privacy, Mapping), "privacy must be an object.")

    require_string(agent, "provider_id")
    require_string(agent, "execution_surface")
    require(agent.get("user_owned_agent") is True, "Receipt must state the Agent is user-owned.")
    require(agent.get("study_anything_executed_real_model") is False, "Study Anything must not execute real model calls.")
    require_string(source, "pr_ref")
    require_string(source, "commit_sha")
    require_string(report, "source_report_name")
    report_sha = require_string(report, "report_sha256")
    require(re.fullmatch(r"[0-9a-f]{64}", report_sha) is not None, "report_sha256 must be lowercase sha256.")
    decision = require_string(report, "decision")
    risk = require_string(report, "overall_risk")
    require(decision in {"approved", "needs-review", "needs-fix"}, f"Invalid receipt decision: {decision}")
    require(risk in {"low", "medium", "high"}, f"Invalid receipt risk: {risk}")
    for key in ("finding_count", "suppressed_count", "critical_count", "warn_count", "info_count"):
        value = report.get(key)
        require(isinstance(value, int) and value >= 0, f"validated_report.{key} must be a non-negative integer.")
    require(
        report["finding_count"] == report["critical_count"] + report["warn_count"] + report["info_count"],
        "finding_count must equal severity counts.",
    )
    require_bool(ci, "should_block_merge")
    require_bool(ci, "required_human_review")
    require_string(ci, "validation_command")
    require_string(ci, "receipt_validation_command")
    require_string(ci, "release_gate")
    expected_action = human_action_for(decision)
    require(ci.get("human_action") == expected_action, f"human_action must be {expected_action}.")
    if decision == "needs-fix":
        require(ci.get("should_block_merge") is True, "needs-fix receipts must block merge.")
        require(report.get("critical_count", 0) > 0, "needs-fix receipts need a critical finding count.")
    if decision == "needs-review":
        require(ci.get("required_human_review") is True, "needs-review receipts must require human review.")

    for key in (
        "raw_diff_included",
        "file_bodies_included",
        "finding_evidence_included",
        "report_summary_included",
        "agent_endpoint_secrets_included",
        "real_model_keys_included",
        "hidden_chain_of_thought_included",
    ):
        require(privacy.get(key) is False, f"privacy.{key} must be false.")
    require(privacy.get("only_report_hash_persisted") is True, "Receipt must persist only report hash.")
    require(privacy.get("safe_to_attach_to_pr") is True, "Receipt must be safe to attach to PR evidence.")
    reject_private_text(receipt, label="Review Agent CI receipt")
    return {
        "receipt_id": receipt["receipt_id"],
        "decision": decision,
        "overall_risk": risk,
        "finding_count": report["finding_count"],
        "critical_count": report["critical_count"],
        "safe_to_attach_to_pr": privacy["safe_to_attach_to_pr"],
    }


def build_command(args: argparse.Namespace) -> int:
    receipt = build_receipt(args)
    serialized = dump_json(receipt)
    if args.output:
        output = Path(args.output).resolve(strict=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


def validate_command(args: argparse.Namespace) -> int:
    receipt = read_json(Path(args.receipt).resolve())
    summary = validate_receipt_payload(receipt)
    print(dump_json({"schema_version": RECEIPT_SCHEMA_VERSION, "status": "pass", "receipt_summary": summary}), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build a metadata-only CI/PR receipt from a validated Review Agent report.")
    build.add_argument("--report", required=True, help="External Review Agent JSON report.")
    build.add_argument("--provider-id", default="external-review-agent", help="Operator-visible provider id.")
    build.add_argument("--provider-label", default="User-owned external Review Agent", help="Human-readable provider label.")
    build.add_argument("--execution-surface", default="ci", choices=["ci", "platform-agent", "local"], help="Where the external Agent ran.")
    build.add_argument("--pr-ref", default="local", help="PR, branch, or run reference.")
    build.add_argument("--commit-sha", default="unknown", help="Commit SHA or immutable run ref.")
    build.add_argument("--base-ref", default="main", help="Base ref.")
    build.add_argument("--head-ref", default="HEAD", help="Head ref.")
    build.add_argument("--generated-at", help="Deterministic timestamp for tests.")
    build.add_argument("--validation-command", default=DEFAULT_VALIDATION_COMMAND, help="Command used to validate the source report.")
    build.add_argument("--output", help="Optional receipt output path.")
    build.set_defaults(func=build_command)

    validate = subparsers.add_parser("validate", help="Validate a metadata-only CI/PR receipt.")
    validate.add_argument("--receipt", required=True, help="Review Agent CI receipt JSON.")
    validate.set_defaults(func=validate_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentReceiptError as exc:
        raise SystemExit(f"error: {exc}") from exc
    except Exception as exc:
        if exc.__class__.__name__ == "ReviewAgentReportError":
            raise SystemExit(f"error: {exc}") from exc
        raise
