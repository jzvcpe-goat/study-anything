#!/usr/bin/env python3
"""Evaluate metadata-only Review Agent evidence against an operator policy."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_receipt.py"
BUNDLE_CLI_PATH = ROOT / "scripts" / "cognitive_loop_review_agent_acceptance_bundle.py"

POLICY_GATE_SCHEMA_VERSION = "cognitive-loop-review-agent-policy-gate-v1"
POLICIES = ("advisory", "soft", "strict")
DECISIONS = ("approved", "needs-review", "needs-fix")


class ReviewAgentPolicyGateError(RuntimeError):
    """Readable Review Agent policy gate failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewAgentPolicyGateError(f"Cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewAgentPolicyGateError(f"JSON object expected: {path}")
    return value


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReviewAgentPolicyGateError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentPolicyGateError(message)


def require_mapping(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, Mapping):
        raise ReviewAgentPolicyGateError(f"Expected object field: {key}")
    return value


def require_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReviewAgentPolicyGateError(f"Expected non-empty string field: {key}")
    return value


def exit_code_for(*, policy: str, decision: str) -> int:
    require(policy in POLICIES, f"Unsupported policy: {policy}")
    require(decision in DECISIONS, f"Unsupported decision: {decision}")
    if policy == "advisory":
        return 0
    if policy == "soft":
        return 2 if decision == "needs-fix" else 0
    return 2 if decision in {"needs-review", "needs-fix"} else 0


def status_for(*, policy: str, decision: str) -> str:
    code = exit_code_for(policy=policy, decision=decision)
    if code:
        return "blocked"
    if decision == "needs-review":
        return "needs_human_review"
    if decision == "needs-fix":
        return "advisory_block_recommended"
    return "pass"


def human_message_for(*, policy: str, decision: str) -> str:
    if decision == "approved":
        return "Review Agent evidence is approved; continue after required checks."
    if decision == "needs-review":
        if policy == "strict":
            return "Strict policy blocks until a maintainer records human review."
        return "Maintainer review is required, but this policy does not fail the command."
    if policy == "advisory":
        return "Fixes are required before merge, but advisory policy reports without failing."
    return "Fixes are required before merge; this policy fails the command."


def load_receipt_summary(path: Path) -> dict[str, Any]:
    receipt_cli = load_module(RECEIPT_CLI_PATH, "study_anything_review_agent_receipt")
    receipt = read_json(path)
    summary = receipt_cli.validate_receipt_payload(receipt)
    source = require_mapping(receipt, "source")
    agent = require_mapping(receipt, "review_agent")
    report = require_mapping(receipt, "validated_report")
    ci = require_mapping(receipt, "ci")
    return {
        "evidence_kind": "receipt",
        "evidence_path": str(path),
        "decision": summary["decision"],
        "overall_risk": summary["overall_risk"],
        "finding_count": summary["finding_count"],
        "critical_count": int(report.get("critical_count", 0)),
        "warn_count": int(report.get("warn_count", 0)),
        "info_count": int(report.get("info_count", 0)),
        "suppressed_count": int(report.get("suppressed_count", 0)),
        "should_block_merge": bool(ci.get("should_block_merge")),
        "required_human_review": bool(ci.get("required_human_review")),
        "human_action": ci.get("human_action"),
        "pr_ref": source.get("pr_ref"),
        "commit_sha": source.get("commit_sha"),
        "base_ref": source.get("base_ref"),
        "head_ref": source.get("head_ref"),
        "report_sha256": report.get("report_sha256"),
        "provider_id": agent.get("provider_id"),
        "provider_label": agent.get("provider_label", ""),
        "execution_surface": agent.get("execution_surface"),
    }


def load_bundle_summary(bundle_dir: Path) -> dict[str, Any]:
    bundle_cli = load_module(BUNDLE_CLI_PATH, "study_anything_review_agent_acceptance_bundle")
    bundle_summary = bundle_cli.validate_bundle_dir(bundle_dir)
    manifest = read_json(bundle_dir / "manifest.json")
    decision = require_mapping(manifest, "decision_summary")
    source = require_mapping(manifest, "source")
    agent = require_mapping(manifest, "review_agent")
    return {
        "evidence_kind": "acceptance_bundle",
        "evidence_path": str(bundle_dir),
        "decision": bundle_summary["decision"],
        "overall_risk": bundle_summary["overall_risk"],
        "finding_count": bundle_summary["finding_count"],
        "critical_count": int(decision.get("critical_count", 0)),
        "warn_count": int(decision.get("warn_count", 0)),
        "info_count": int(decision.get("info_count", 0)),
        "suppressed_count": int(decision.get("suppressed_count", 0)),
        "should_block_merge": bool(decision.get("should_block_merge")),
        "required_human_review": bool(decision.get("required_human_review")),
        "human_action": decision.get("human_action"),
        "pr_ref": source.get("pr_ref"),
        "commit_sha": source.get("commit_sha"),
        "base_ref": source.get("base_ref"),
        "head_ref": source.get("head_ref"),
        "report_sha256": source.get("report_sha256"),
        "provider_id": agent.get("provider_id"),
        "provider_label": agent.get("provider_label", ""),
        "execution_surface": agent.get("execution_surface"),
    }


def build_gate_payload(summary: Mapping[str, Any], *, policy: str, generated_at: str) -> dict[str, Any]:
    decision = require_string(summary, "decision")
    status = status_for(policy=policy, decision=decision)
    exit_code = exit_code_for(policy=policy, decision=decision)
    payload = {
        "schema_version": POLICY_GATE_SCHEMA_VERSION,
        "status": status,
        "policy": policy,
        "exit_code": exit_code,
        "generated_at": generated_at,
        "evidence": {
            "kind": summary.get("evidence_kind"),
            "path": summary.get("evidence_path"),
            "metadata_only": True,
        },
        "source": {
            "pr_ref": summary.get("pr_ref"),
            "commit_sha": summary.get("commit_sha"),
            "base_ref": summary.get("base_ref"),
            "head_ref": summary.get("head_ref"),
            "report_sha256": summary.get("report_sha256"),
        },
        "review_agent": {
            "provider_id": summary.get("provider_id"),
            "provider_label": summary.get("provider_label", ""),
            "execution_surface": summary.get("execution_surface"),
            "user_owned_agent": True,
            "study_anything_executed_real_model": False,
        },
        "decision_summary": {
            "decision": decision,
            "overall_risk": summary.get("overall_risk"),
            "finding_count": summary.get("finding_count"),
            "critical_count": summary.get("critical_count"),
            "warn_count": summary.get("warn_count"),
            "info_count": summary.get("info_count"),
            "suppressed_count": summary.get("suppressed_count"),
            "should_block_merge": summary.get("should_block_merge"),
            "required_human_review": summary.get("required_human_review"),
            "human_action": summary.get("human_action"),
        },
        "policy_result": {
            "failed": exit_code != 0,
            "blocks_merge": exit_code != 0,
            "human_message": human_message_for(policy=policy, decision=decision),
        },
        "privacy": {
            "raw_diff_included": False,
            "file_bodies_included": False,
            "finding_evidence_included": False,
            "report_summary_included": False,
            "agent_endpoint_secrets_included": False,
            "real_model_keys_included": False,
            "hidden_chain_of_thought_included": False,
            "metadata_only": True,
            "safe_to_attach_to_pr": True,
        },
        "commands": {
            "advisory": "python3 scripts/cognitive_loop_review_agent_policy_gate.py --bundle-dir REVIEW_AGENT_ACCEPTANCE_BUNDLE_DIR --policy advisory",
            "soft": "python3 scripts/cognitive_loop_review_agent_policy_gate.py --bundle-dir REVIEW_AGENT_ACCEPTANCE_BUNDLE_DIR --policy soft",
            "strict": "python3 scripts/cognitive_loop_review_agent_policy_gate.py --bundle-dir REVIEW_AGENT_ACCEPTANCE_BUNDLE_DIR --policy strict",
            "release_gate": "python3 scripts/verify_cognitive_loop_review_agent_policy_gate.py --check",
        },
    }
    validate_gate_payload(payload)
    return payload


def validate_gate_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    receipt_cli = load_module(RECEIPT_CLI_PATH, "study_anything_review_agent_receipt")
    require(payload.get("schema_version") == POLICY_GATE_SCHEMA_VERSION, "Policy gate schema_version drifted.")
    status = require_string(payload, "status")
    policy = require_string(payload, "policy")
    require(policy in POLICIES, f"Invalid policy: {policy}")
    evidence = require_mapping(payload, "evidence")
    decision = require_mapping(payload, "decision_summary")
    privacy = require_mapping(payload, "privacy")
    policy_result = require_mapping(payload, "policy_result")
    review_decision = require_string(decision, "decision")
    expected_exit = exit_code_for(policy=policy, decision=review_decision)
    require(payload.get("exit_code") == expected_exit, "Policy gate exit_code drifted.")
    require(status == status_for(policy=policy, decision=review_decision), "Policy gate status drifted.")
    require(evidence.get("metadata_only") is True, "Policy gate evidence must be metadata-only.")
    require(policy_result.get("failed") == (expected_exit != 0), "Policy gate failed flag drifted.")
    require(policy_result.get("blocks_merge") == (expected_exit != 0), "Policy gate blocks_merge flag drifted.")
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
    require(privacy.get("metadata_only") is True, "Policy gate must be metadata-only.")
    require(privacy.get("safe_to_attach_to_pr") is True, "Policy gate output must be safe to attach to PR.")
    receipt_cli.reject_private_text(payload, label="Review Agent policy gate")
    return {
        "policy": policy,
        "decision": review_decision,
        "status": status,
        "exit_code": expected_exit,
    }


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = args.generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if bool(args.bundle_dir) == bool(args.receipt):
        raise ReviewAgentPolicyGateError("Pass exactly one of --bundle-dir or --receipt.")
    if args.bundle_dir:
        summary = load_bundle_summary(Path(args.bundle_dir).resolve())
    else:
        summary = load_receipt_summary(Path(args.receipt).resolve())
    return build_gate_payload(summary, policy=args.policy, generated_at=generated_at)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", help="Metadata-only Review Agent acceptance bundle directory.")
    parser.add_argument("--receipt", help="Metadata-only Review Agent CI receipt JSON.")
    parser.add_argument("--policy", choices=POLICIES, default="soft")
    parser.add_argument("--output", help="Optional path to write the policy gate JSON.")
    parser.add_argument("--generated-at")
    args = parser.parse_args()

    payload = evaluate(args)
    serialized = dump_json(payload)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return int(payload["exit_code"])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewAgentPolicyGateError as exc:
        raise SystemExit(f"error: {exc}") from exc
