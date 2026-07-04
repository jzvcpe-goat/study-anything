#!/usr/bin/env python3
"""Build a metadata-only end-to-end Cognitive Black Box trust-chain report.

The harness proves that the current product/delivery trust protocol can connect
these layers without raw payloads, model calls, customer-visible sends, or
production mutation:

External Feedback -> Backlog -> Product Owner -> Spec/Eval -> Product Loop
Brief Intake -> Product Loop Run -> Delivery Trust Case -> Customer Delivery
Envelope -> Customer Delivery Rehearsal.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from study_anything.core import delivery_trust_case, dual_loop, product_loop_harness  # noqa: E402
import external_feedback_backlog_bridge as backlog_bridge  # noqa: E402
import external_feedback_receipt  # noqa: E402
import product_loop_brief_intake  # noqa: E402
import product_owner_prioritization_gate as owner_gate  # noqa: E402
import product_spec_eval_authoring_gate as spec_eval_gate  # noqa: E402
import verify_customer_delivery_rehearsal as customer_rehearsal  # noqa: E402
import verify_customer_delivery_trust_envelope as customer_envelope  # noqa: E402


REPORT_SCHEMA_VERSION = "end-to-end-trust-chain-harness-v1"
CLI_SCHEMA_VERSION = "end-to-end-trust-chain-harness-cli-result-v1"

REPORT = ROOT / "platform" / "generated" / "study-anything-end-to-end-trust-chain-harness.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-end-to-end-trust-chain-harness.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-end-to-end-trust-chain-harness.html"

PASS_PATHS = {
    "external_feedback_receipt": ROOT
    / "fixtures"
    / "external-feedback-receipt"
    / "pass"
    / "external-feedback-receipt.json",
    "external_feedback_backlog_bridge": ROOT
    / "fixtures"
    / "external-feedback-backlog-bridge"
    / "pass"
    / "external-feedback-backlog-bridge.json",
    "product_loop_backlog_item": ROOT
    / "fixtures"
    / "external-feedback-backlog-bridge"
    / "pass"
    / "product-loop-backlog-item.json",
    "product_owner_receipt": ROOT
    / "fixtures"
    / "product-owner-prioritization-gate"
    / "pass"
    / "product-owner-prioritization-receipt.json",
    "product_spec_eval_candidate": ROOT
    / "fixtures"
    / "product-owner-prioritization-gate"
    / "pass"
    / "product-spec-eval-candidate.json",
    "product_spec_eval_authoring_receipt": ROOT
    / "fixtures"
    / "product-spec-eval-authoring-gate"
    / "pass"
    / "product-spec-eval-authoring-receipt.json",
    "product_spec_eval_brief": ROOT
    / "fixtures"
    / "product-spec-eval-authoring-gate"
    / "pass"
    / "product-spec-eval-brief.json",
    "product_loop_brief_intake_receipt": ROOT
    / "fixtures"
    / "product-loop-brief-intake"
    / "pass"
    / "product-loop-brief-intake-receipt.json",
    "product_loop_run": ROOT
    / "fixtures"
    / "product-loop-brief-intake"
    / "pass"
    / "product-loop-run.json",
    "dual_loop_gate_receipt": ROOT
    / "fixtures"
    / "delivery-trust-case"
    / "pass"
    / "dual-loop-gate-receipt.json",
    "delivery_trust_receipt": ROOT
    / "fixtures"
    / "delivery-trust-case"
    / "pass"
    / "delivery-trust-receipt.json",
    "customer_handoff_package": ROOT
    / "fixtures"
    / "delivery-trust-case"
    / "pass"
    / "customer-handoff-package.json",
    "customer_delivery_trust_envelope": customer_envelope.REPORT,
    "customer_delivery_rehearsal": customer_rehearsal.REPORT,
}

PRIVACY = {
    **dual_loop.PRIVACY_FLAGS,
    "metadata_only": True,
    "raw_feedback_text_included": False,
    "raw_spec_body_included": False,
    "raw_eval_body_included": False,
    "raw_diff_included": False,
    "raw_customer_payload_included": False,
    "attention_streams_included": False,
    "agent_endpoint_secrets_included": False,
    "customer_visible_effect_performed": False,
    "production_mutation_performed": False,
}
RUNTIME = {
    "deterministic_fixture": True,
    "daemon_or_hosted_service_started": False,
    "model_calls_performed": False,
    "automatic_customer_send_performed": False,
    "customer_visible_effect_performed": False,
    "production_mutation_performed": False,
    "external_publication_performed": False,
}
CLAIM_BOUNDARY = {
    "current_claim": (
        "The repository can build a metadata-only evidence chain from external "
        "feedback through product and delivery trust gates to a customer-delivery "
        "rehearsal boundary."
    ),
    "not_claimed": [
        "customer send approval",
        "production approval",
        "truth certification",
        "customer outcome guarantee",
        "full release_check.sh completion",
        "general model correctness",
    ],
}


class EndToEndTrustChainError(RuntimeError):
    """Readable end-to-end trust-chain failure."""


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EndToEndTrustChainError(f"Expected JSON object: {path}")
    return payload


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def artifact_hash(payload: Mapping[str, Any]) -> str:
    return dual_loop.sha256_text(dual_loop.dump_json(payload))


def metadata_ref(step_id: str, path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "path": path.relative_to(ROOT).as_posix(),
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "decision": payload.get("decision"),
        "sha256": artifact_hash(payload),
        "raw_body_included": False,
    }


def _validate_step(
    step_id: str,
    path: Path,
    validator: Callable[[Mapping[str, Any]], Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = load_json(path)
    validated = validator(payload)
    if isinstance(validated, Mapping):
        payload = dict(validated)
    dual_loop.assert_metadata_only(payload, label=f"end-to-end-trust-chain:{step_id}")
    return payload, metadata_ref(step_id, path, payload)


def validate_customer_envelope(payload: Mapping[str, Any]) -> dict[str, Any]:
    customer_envelope.validate_envelope(payload)
    return dict(payload)


def validate_customer_rehearsal(payload: Mapping[str, Any]) -> dict[str, Any]:
    customer_rehearsal.validate_rehearsal(payload)
    return dict(payload)


def _validate_pass_chain() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    validators: list[tuple[str, Callable[[Mapping[str, Any]], Any]]] = [
        ("external_feedback_receipt", external_feedback_receipt.validate_case),
        ("external_feedback_backlog_bridge", backlog_bridge.validate_bridge),
        ("product_loop_backlog_item", backlog_bridge.validate_backlog_item),
        ("product_owner_receipt", owner_gate.validate_receipt),
        ("product_spec_eval_candidate", owner_gate.validate_candidate),
        ("product_spec_eval_authoring_receipt", spec_eval_gate.validate_receipt),
        ("product_spec_eval_brief", spec_eval_gate.validate_brief),
        ("product_loop_brief_intake_receipt", product_loop_brief_intake.validate_receipt),
        ("product_loop_run", product_loop_harness.validate_product_loop_run),
        ("dual_loop_gate_receipt", dual_loop.validate_gate_receipt),
        ("customer_delivery_trust_envelope", validate_customer_envelope),
        ("customer_delivery_rehearsal", validate_customer_rehearsal),
    ]
    payloads: dict[str, dict[str, Any]] = {}
    refs: list[dict[str, Any]] = []
    for step_id, validator in validators:
        payload, ref = _validate_step(step_id, PASS_PATHS[step_id], validator)
        payloads[step_id] = payload
        refs.append(ref)

    delivery_case = delivery_trust_case.build_delivery_trust_case(
        payloads["product_loop_run"],
        payloads["dual_loop_gate_receipt"],
        load_json(PASS_PATHS["delivery_trust_receipt"]),
        load_json(PASS_PATHS["customer_handoff_package"]),
        case_id="end-to-end-trust-chain",
    )
    delivery_case = delivery_trust_case.validate_delivery_trust_case(delivery_case)
    payloads["assembled_delivery_trust_case"] = delivery_case
    refs.insert(
        10,
        {
            "step_id": "assembled_delivery_trust_case",
            "path": "generated-in-memory",
            "schema_version": delivery_case["schema_version"],
            "status": delivery_case["status"],
            "decision": delivery_case["decision"],
            "sha256": artifact_hash(delivery_case),
            "raw_body_included": False,
        },
    )
    return payloads, refs


def continuity_checks(payloads: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    backlog_item_hash = artifact_hash(payloads["product_loop_backlog_item"])
    candidate_hash = artifact_hash(payloads["product_spec_eval_candidate"])
    brief_hash = artifact_hash(payloads["product_spec_eval_brief"])
    checks = [
        {
            "check_id": "feedback_receipt_to_backlog_bridge",
            "status": "pass"
            if payloads["external_feedback_backlog_bridge"].get("source_receipt_id")
            == payloads["external_feedback_receipt"].get("receipt_id")
            else "fail",
        },
        {
            "check_id": "backlog_item_to_product_owner_receipt",
            "status": "pass"
            if payloads["product_owner_receipt"].get("source_backlog_item_hash") == backlog_item_hash
            else "fail",
        },
        {
            "check_id": "product_owner_candidate_to_spec_eval_authoring",
            "status": "pass"
            if payloads["product_spec_eval_authoring_receipt"].get("source_candidate_hash") == candidate_hash
            else "fail",
        },
        {
            "check_id": "spec_eval_brief_to_product_loop_intake",
            "status": "pass"
            if payloads["product_loop_brief_intake_receipt"].get("source_brief_hash") == brief_hash
            else "fail",
        },
        {
            "check_id": "product_loop_run_to_delivery_trust_case",
            "status": "pass"
            if payloads["assembled_delivery_trust_case"]["layer_statuses"].get("product_loop") == "allowed"
            else "fail",
        },
        {
            "check_id": "delivery_case_to_customer_envelope_boundary",
            "status": "pass"
            if payloads["customer_delivery_trust_envelope"]["delivery_gate"].get(
                "automatic_customer_send_allowed"
            )
            is False
            else "fail",
        },
        {
            "check_id": "customer_envelope_to_rehearsal_boundary",
            "status": "pass"
            if payloads["customer_delivery_rehearsal"]["rehearsal"].get("ready_count") == 1
            and payloads["customer_delivery_rehearsal"]["rehearsal"].get("blocked_count", 0) >= 5
            else "fail",
        },
    ]
    failed = [check["check_id"] for check in checks if check["status"] != "pass"]
    if failed:
        raise EndToEndTrustChainError(f"end-to-end continuity checks failed: {failed}")
    return checks


def build_case_reports(payloads: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    blocked_product_run = product_loop_harness.validate_product_loop_run(
        load_json(ROOT / "fixtures" / "product-loop-harness" / "blocked-ai-review-only" / "product-loop-run.json")
    )
    blocked_case = delivery_trust_case.build_delivery_trust_case(
        blocked_product_run,
        payloads["dual_loop_gate_receipt"],
        load_json(PASS_PATHS["delivery_trust_receipt"]),
        load_json(PASS_PATHS["customer_handoff_package"]),
        case_id="blocked-product-loop-run",
    )
    blocked_case = delivery_trust_case.validate_delivery_trust_case(blocked_case)
    rehearsal_cases = payloads["customer_delivery_rehearsal"]["rehearsal"]["cases"]
    automatic_send = next(
        case for case in rehearsal_cases if case["case_id"] == "block-automatic-customer-send"
    )
    missing_scope = next(
        case for case in rehearsal_cases if case["case_id"] == "block-missing-human-scope"
    )
    return [
        {
            "case_id": "pass",
            "status": "ready_for_customer_delivery_rehearsal",
            "decision": "chain_ready_for_manual_rehearsal_boundary",
            "blocked_reasons": [],
        },
        {
            "case_id": "blocked-product-loop-run",
            "status": blocked_case["status"],
            "decision": blocked_case["decision"],
            "blocked_reasons": blocked_case["reasons"],
        },
        {
            "case_id": "blocked-automatic-customer-send",
            "status": automatic_send["status"],
            "decision": automatic_send["decision"],
            "blocked_reasons": automatic_send["reasons"],
        },
        {
            "case_id": "blocked-missing-human-scope",
            "status": missing_scope["status"],
            "decision": missing_scope["decision"],
            "blocked_reasons": missing_scope["reasons"],
        },
    ]


def build_report() -> dict[str, Any]:
    payloads, refs = _validate_pass_chain()
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "purpose": (
            "Prove the Cognitive Black Box product-to-delivery trust chain is "
            "connected end to end by metadata-only receipts before any customer "
            "send or production mutation."
        ),
        "chain_steps": refs,
        "continuity_checks": continuity_checks(payloads),
        "case_reports": build_case_reports(payloads),
        "gate_rules": {
            "all_handoffs_use_structured_artifact_refs": True,
            "raw_bodies_are_never_required": True,
            "ai_review_only_blocks": True,
            "active_human_boundary_reconstruction_required": True,
            "automatic_customer_send_blocked": True,
            "production_mutation_blocked": True,
            "delivery_rehearsal_required_before_customer_send": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
    }
    return validate_report(report)


def validate_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    dual_loop.assert_metadata_only(payload, label=REPORT_SCHEMA_VERSION)
    if payload.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise EndToEndTrustChainError("end-to-end trust chain schema_version drifted")
    if payload.get("status") != "pass":
        raise EndToEndTrustChainError("end-to-end trust chain report must pass")
    for key in ("chain_steps", "continuity_checks", "case_reports", "privacy", "runtime"):
        if key not in payload:
            raise EndToEndTrustChainError(f"end-to-end trust chain report missing {key}")
    for key, expected in PRIVACY.items():
        if payload["privacy"].get(key) is not expected:
            raise EndToEndTrustChainError(f"privacy.{key} must be {expected!r}")
    for key, expected in RUNTIME.items():
        if payload["runtime"].get(key) is not expected:
            raise EndToEndTrustChainError(f"runtime.{key} must be {expected!r}")
    steps = payload["chain_steps"]
    if not isinstance(steps, list) or len(steps) < 12:
        raise EndToEndTrustChainError("end-to-end trust chain must include all chain steps")
    for step in steps:
        if not isinstance(step, Mapping):
            raise EndToEndTrustChainError("chain step must be an object")
        if step.get("raw_body_included") is not False:
            raise EndToEndTrustChainError(f"chain step {step.get('step_id')} includes raw body")
        if not step.get("sha256"):
            raise EndToEndTrustChainError(f"chain step {step.get('step_id')} missing sha256")
    checks = payload["continuity_checks"]
    if not isinstance(checks, list) or any(check.get("status") != "pass" for check in checks):
        raise EndToEndTrustChainError("all end-to-end continuity checks must pass")
    cases = payload["case_reports"]
    if not isinstance(cases, list):
        raise EndToEndTrustChainError("case_reports must be a list")
    case_map = {case.get("case_id"): case for case in cases if isinstance(case, Mapping)}
    for case_id in (
        "pass",
        "blocked-product-loop-run",
        "blocked-automatic-customer-send",
        "blocked-missing-human-scope",
    ):
        if case_id not in case_map:
            raise EndToEndTrustChainError(f"missing end-to-end case report: {case_id}")
    if case_map["pass"].get("blocked_reasons") != []:
        raise EndToEndTrustChainError("pass case must not include blocked reasons")
    for case_id in ("blocked-product-loop-run", "blocked-automatic-customer-send", "blocked-missing-human-scope"):
        if not case_map[case_id].get("blocked_reasons"):
            raise EndToEndTrustChainError(f"{case_id} must include blocked reasons")
    claim = payload.get("claim_boundary")
    if not isinstance(claim, Mapping) or not claim.get("current_claim"):
        raise EndToEndTrustChainError("claim_boundary.current_claim is required")
    return dict(payload)


def render_markdown(report: Mapping[str, Any]) -> str:
    step_lines = [
        f"- `{step['step_id']}`: `{step['schema_version']}` / `{step.get('status')}` / `{step.get('decision')}`"
        for step in report["chain_steps"]
    ]
    case_lines = [
        f"- `{case['case_id']}`: `{case['status']}` / `{case['decision']}`"
        for case in report["case_reports"]
    ]
    return "\n".join(
        [
            "# End-to-End Trust Chain Harness",
            "",
            "Metadata-only proof that the Cognitive Black Box trust chain connects product intake to customer-delivery rehearsal without raw payloads or customer-visible effects.",
            "",
            f"- status: `{report['status']}`",
            f"- chain steps: `{len(report['chain_steps'])}`",
            f"- continuity checks: `{len(report['continuity_checks'])}`",
            "- customer send: `blocked`",
            "- production mutation: `blocked`",
            "",
            "## Chain Steps",
            "",
            *step_lines,
            "",
            "## Cases",
            "",
            *case_lines,
            "",
            "## Boundary",
            "",
            report["claim_boundary"]["current_claim"],
            "",
        ]
    )


def write_report(output: Path) -> dict[str, Any]:
    report = build_report()
    dual_loop.write_json(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT)
    parser.add_argument("--markdown-output", type=Path, default=MARKDOWN_REPORT)
    parser.add_argument("--html-output", type=Path, default=HTML_REPORT)
    args = parser.parse_args()

    report = write_report(args.output)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    dual_loop.write_html_report(
        args.html_output,
        "End-to-End Trust Chain Harness",
        report,
    )
    print(
        dump_json(
            {
                "schema_version": CLI_SCHEMA_VERSION,
                "status": "ok",
                "report": str(args.output.relative_to(ROOT) if args.output.is_relative_to(ROOT) else args.output),
                "chain_step_count": len(report["chain_steps"]),
                "case_count": len(report["case_reports"]),
                "model_calls_performed": False,
                "customer_visible_effect_performed": False,
                "production_mutation_performed": False,
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
