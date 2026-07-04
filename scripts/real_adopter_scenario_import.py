#!/usr/bin/env python3
"""Import a real-adopter issue summary into the Product Loop as metadata only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

from study_anything.core import dual_loop  # noqa: E402
import external_feedback_receipt  # noqa: E402
import external_feedback_backlog_bridge  # noqa: E402
import product_owner_prioritization_gate  # noqa: E402
import product_spec_eval_authoring_gate  # noqa: E402
import product_loop_brief_intake  # noqa: E402


SUMMARY_SCHEMA_VERSION = "real-adopter-issue-summary-v1"
REPORT_SCHEMA_VERSION = "real-adopter-scenario-import-v1"
CLI_SCHEMA_VERSION = "real-adopter-scenario-import-cli-result-v1"

REPORT = ROOT / "platform" / "generated" / "study-anything-real-adopter-scenario-import.json"
MARKDOWN_REPORT = ROOT / "platform" / "generated" / "study-anything-real-adopter-scenario-import.md"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-real-adopter-scenario-import.html"
DEFAULT_SUMMARY = (
    ROOT
    / "fixtures"
    / "real-adopter-scenario-import"
    / "pass"
    / "real-adopter-issue-summary.json"
)

ALLOWED_PLATFORMS = {"workbuddy", "kimi", "codex", "hermes", "generic-http-tools"}
ALLOWED_SOURCE_CHANNELS = {"workbuddy_field_report", "kimi_work_session", "codex_session", "support_ticket"}
ALLOWED_DELIVERY_CLASSES = {"support_response_handoff", "client_report_handoff", "code_review_handoff"}
ALLOWED_TAGS = {
    "deterministic_quality_gap",
    "real_agent_not_invoked",
    "version_drift",
    "proxy_env_workaround",
    "onboarding_confusion",
    "plugin_pack_import_gap",
    "documentation_gap",
    "field_rehearsal_gap",
}
FORBIDDEN_FIELDS = {
    "raw_issue_text",
    "raw_feedback_text",
    "raw_customer_message",
    "raw_ticket_payload",
    "raw_report_text",
    "requester_identity",
    "customer_identity",
    "user_identity",
    "personal_profile",
    "screenshot",
    "screenshots",
    "browser_history",
    "keystrokes",
    "mouse_coordinates",
    "eye_tracking",
    "biometrics",
    "cookie",
    "cookies",
    "bearer_token",
    "signed_url",
    "agent_endpoint_secret",
    "model_api_key",
    "agent_credentials",
    "production_payload",
}

PRIVACY = {
    **external_feedback_backlog_bridge.PRIVACY,
    "real_adopter_summary_metadata_only": True,
    "raw_issue_text_included": False,
    "requester_identity_included": False,
    "platform_logs_included": False,
    "agent_trace_included": False,
    "real_model_keys_included": False,
    "agent_endpoint_secrets_included": False,
    "automatic_issue_reply_created": False,
}
RUNTIME = {
    **external_feedback_backlog_bridge.RUNTIME,
    "model_calls_performed": False,
    "daemon_or_hosted_service_started": False,
    "production_mutation_performed": False,
    "customer_visible_action_performed": False,
    "external_publication_performed": False,
}
CLAIM_BOUNDARY = {
    "current_claim": (
        "A bounded real-adopter issue summary can re-enter the Product Loop as "
        "metadata-only evidence and produce a Product Spec/Eval brief candidate."
    ),
    "not_claimed": [
        "raw adopter feedback import",
        "requester identity import",
        "automatic product-owner prioritization",
        "automatic implementation",
        "customer-visible reply",
        "external publication",
        "production mutation",
        "proof that the reported issue is globally representative",
    ],
}


class RealAdopterScenarioImportError(RuntimeError):
    """Readable real-adopter scenario import failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RealAdopterScenarioImportError(f"Expected JSON object: {path}")
    return payload


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


def reject_forbidden_fields(payload: Mapping[str, Any], *, label: str) -> None:
    dual_loop.assert_metadata_only(payload, label=label)
    hits: list[str] = []
    for mapping in walk_mappings(payload):
        for key, value in mapping.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in FORBIDDEN_FIELDS and value not in (None, False, "", []):
                hits.append(str(key))
    if hits:
        raise RealAdopterScenarioImportError(
            f"{label} contains forbidden fields: {sorted(set(hits))}"
        )


def artifact_hash(payload: Mapping[str, Any]) -> str:
    return dual_loop.sha256_text(dual_loop.dump_json(payload))


def default_summary() -> dict[str, Any]:
    issue_seed = "workbuddy-field-report:v0.3.31:quality-version-proxy"
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "summary_id": "workbuddy-field-report-2026-07-04",
        "platform_id": "workbuddy",
        "source_channel": "workbuddy_field_report",
        "source_delivery_class": "support_response_handoff",
        "source_handoff_ref": "workbuddy-field-report:metadata-only-summary",
        "issue_ref": {
            "issue_ref_hash": dual_loop.sha256_text(issue_seed)[:24],
            "body_included": False,
            "requester_identity_included": False,
            "platform_logs_included": False,
        },
        "bounded_tags": [
            "deterministic_quality_gap",
            "real_agent_not_invoked",
            "version_drift",
            "proxy_env_workaround",
        ],
        "feedback_kind": "adoption_friction",
        "sentiment": "negative",
        "severity": "high",
        "operator_reconstruction": {
            "active_reconstruction_present": True,
            "checkpoint_ids": [
                "raw_feedback_excluded",
                "platform_scope_reconstructed",
                "next_spec_eval_boundary_reconstructed",
            ],
            "passive_attention_only": False,
            "understands_no_customer_reply": True,
        },
        "requested_product_loop_outcome": {
            "next_action": "product_loop_backlog",
            "target_spec_eval_theme": "real_agent_quality_and_version_drift_gate",
            "automatic_priority_requested": False,
            "automatic_execution_requested": False,
            "customer_visible_action_requested": False,
            "production_mutation_requested": False,
        },
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
        "claim_boundary": dict(CLAIM_BOUNDARY),
    }


def validate_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    reject_forbidden_fields(summary, label=SUMMARY_SCHEMA_VERSION)
    if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        raise RealAdopterScenarioImportError("real-adopter summary schema_version drifted")
    if summary.get("platform_id") not in ALLOWED_PLATFORMS:
        raise RealAdopterScenarioImportError("real-adopter summary platform is unsupported")
    if summary.get("source_channel") not in ALLOWED_SOURCE_CHANNELS:
        raise RealAdopterScenarioImportError("real-adopter summary source_channel is unsupported")
    if summary.get("source_delivery_class") not in ALLOWED_DELIVERY_CLASSES:
        raise RealAdopterScenarioImportError("real-adopter summary delivery class is unsupported")
    issue_ref = summary.get("issue_ref")
    if not isinstance(issue_ref, Mapping) or not issue_ref.get("issue_ref_hash"):
        raise RealAdopterScenarioImportError("real-adopter summary missing issue_ref hash")
    for key in ("body_included", "requester_identity_included", "platform_logs_included"):
        if issue_ref.get(key) is not False:
            raise RealAdopterScenarioImportError(f"issue_ref.{key} must be False")
    tags = summary.get("bounded_tags")
    if not isinstance(tags, list) or not tags:
        raise RealAdopterScenarioImportError("real-adopter summary requires bounded_tags")
    unknown_tags = sorted(set(str(tag) for tag in tags) - ALLOWED_TAGS)
    if unknown_tags:
        raise RealAdopterScenarioImportError(f"unsupported real-adopter tags: {unknown_tags}")
    reconstruction = summary.get("operator_reconstruction")
    if not isinstance(reconstruction, Mapping):
        raise RealAdopterScenarioImportError("real-adopter summary missing operator reconstruction")
    if reconstruction.get("active_reconstruction_present") is not True:
        raise RealAdopterScenarioImportError("active operator reconstruction is required")
    if reconstruction.get("passive_attention_only") is not False:
        raise RealAdopterScenarioImportError("passive attention alone is insufficient")
    outcome = summary.get("requested_product_loop_outcome")
    if not isinstance(outcome, Mapping):
        raise RealAdopterScenarioImportError("real-adopter summary missing requested outcome")
    if outcome.get("next_action") != "product_loop_backlog":
        raise RealAdopterScenarioImportError("real-adopter summary must stop at product_loop_backlog")
    for key in (
        "automatic_priority_requested",
        "automatic_execution_requested",
        "customer_visible_action_requested",
        "production_mutation_requested",
    ):
        if outcome.get(key) is not False:
            raise RealAdopterScenarioImportError(f"requested outcome {key} must be False")
    privacy = summary.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise RealAdopterScenarioImportError("real-adopter summary privacy must be metadata-only")
    runtime = summary.get("runtime")
    if not isinstance(runtime, Mapping):
        raise RealAdopterScenarioImportError("real-adopter summary missing runtime")
    for key, expected in RUNTIME.items():
        if runtime.get(key) is not expected:
            raise RealAdopterScenarioImportError(f"runtime.{key} must be {expected!r}")
    return dict(summary)


def build_external_feedback_receipt(summary: Mapping[str, Any]) -> dict[str, Any]:
    source = validate_summary(summary)
    receipt = external_feedback_receipt.base_case(source["summary_id"])
    receipt["receipt_id"] = f"external-feedback-real-adopter-{source['platform_id']}"
    receipt["source_delivery_class"] = source["source_delivery_class"]
    receipt["source_handoff_ref"] = source["source_handoff_ref"]
    receipt["feedback_ref"] = {
        "feedback_hash": source["issue_ref"]["issue_ref_hash"],
        "source_channel": source["source_channel"],
        "feedback_kind": source["feedback_kind"],
        "sentiment": source["sentiment"],
        "severity": source["severity"],
        "bounded_tags": list(source["bounded_tags"]),
    }
    receipt["human_reconstruction"] = {
        "active_triage_checkpoint_ids": list(source["operator_reconstruction"]["checkpoint_ids"]),
        "active_human_triage_recorded": True,
        "passive_attention_only": False,
        "operator_understands_no_customer_reply": True,
    }
    return external_feedback_receipt.validate_case(receipt)


def build_chain(summary: Mapping[str, Any]) -> dict[str, Any]:
    source = validate_summary(summary)
    external_receipt = build_external_feedback_receipt(source)
    backlog_bridge = external_feedback_backlog_bridge.build_bridge(external_receipt)
    backlog_item = backlog_bridge.get("backlog_item")
    if not isinstance(backlog_item, Mapping):
        raise RealAdopterScenarioImportError("accepted real-adopter feedback did not create backlog item")
    owner_receipt = product_owner_prioritization_gate.build_receipt(
        backlog_item=backlog_item,
        source_bridge=backlog_bridge,
        active_owner_reconstruction=True,
    )
    candidate = owner_receipt.get("candidate")
    if not isinstance(candidate, Mapping):
        raise RealAdopterScenarioImportError("Product Owner gate did not create spec/eval candidate")
    spec_eval_receipt = product_spec_eval_authoring_gate.build_receipt(
        candidate=candidate,
        active_authoring_reconstruction=True,
    )
    brief = spec_eval_receipt.get("brief")
    if not isinstance(brief, Mapping):
        raise RealAdopterScenarioImportError("Spec/Eval authoring gate did not create a brief")
    brief_intake_receipt = product_loop_brief_intake.build_receipt(
        brief=brief,
        active_developer_vision=True,
    )
    scenario = brief_intake_receipt.get("scenario")
    run = brief_intake_receipt.get("run")
    if not isinstance(scenario, Mapping) or not isinstance(run, Mapping):
        raise RealAdopterScenarioImportError("Product Loop brief intake did not create scenario/run")
    return {
        "summary": source,
        "external_feedback_receipt": external_receipt,
        "external_feedback_backlog_bridge": backlog_bridge,
        "product_loop_backlog_item": dict(backlog_item),
        "product_owner_prioritization_receipt": owner_receipt,
        "product_spec_eval_candidate": dict(candidate),
        "product_spec_eval_authoring_receipt": spec_eval_receipt,
        "product_spec_eval_brief": dict(brief),
        "product_loop_brief_intake_receipt": brief_intake_receipt,
        "product_loop_scenario": dict(scenario),
        "product_loop_run": dict(run),
    }


def artifact_ref(name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "schema_version": payload.get("schema_version"),
        "artifact_hash": artifact_hash(payload),
        "body_included": False,
    }


def diagnostic_code(exc: Exception) -> str:
    message = str(exc).lower()
    if "private-looking data" in message:
        return "private_like_value_rejected"
    if "forbidden fields" in message:
        return "forbidden_private_field_rejected"
    if "active operator reconstruction" in message or "passive attention" in message:
        return "active_reconstruction_missing"
    if "product_loop_backlog" in message or "production" in message:
        return "requested_scope_outside_product_loop_budget"
    if "identity" in message:
        return "identity_scope_rejected"
    return "real_adopter_summary_invalid"


def build_case_report(case_id: str, summary: Mapping[str, Any]) -> dict[str, Any]:
    try:
        chain = build_chain(summary)
    except Exception as exc:  # noqa: BLE001
        return {
            "case_id": case_id,
            "status": "blocked",
            "decision": "block_real_adopter_import",
            "blocked_reasons": [diagnostic_code(exc)],
            "artifact_refs": [],
        }
    artifact_order = [
        "summary",
        "external_feedback_receipt",
        "external_feedback_backlog_bridge",
        "product_loop_backlog_item",
        "product_owner_prioritization_receipt",
        "product_spec_eval_candidate",
        "product_spec_eval_authoring_receipt",
        "product_spec_eval_brief",
        "product_loop_brief_intake_receipt",
        "product_loop_scenario",
        "product_loop_run",
    ]
    return {
        "case_id": case_id,
        "status": "allowed",
        "decision": "create_product_loop_harness_candidate",
        "blocked_reasons": [],
        "platform_id": chain["summary"]["platform_id"],
        "bounded_tags": list(chain["summary"]["bounded_tags"]),
        "target_spec_eval_theme": chain["summary"]["requested_product_loop_outcome"][
            "target_spec_eval_theme"
        ],
        "artifact_refs": [artifact_ref(name, chain[name]) for name in artifact_order],
        "next_boundary": "product_loop_harness_candidate",
    }


def blocked_summaries() -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}

    raw = default_summary()
    raw["raw_issue_text"] = "raw private source text from adopter"
    cases["blocked-raw-issue-text"] = raw

    identity = default_summary()
    identity["requester_identity"] = "private adopter identity"
    cases["blocked-identity"] = identity

    ai_only = default_summary()
    ai_only["operator_reconstruction"]["active_reconstruction_present"] = False
    ai_only["operator_reconstruction"]["passive_attention_only"] = True
    cases["blocked-ai-review-only"] = ai_only

    production = default_summary()
    production["requested_product_loop_outcome"]["next_action"] = "production_mutation"
    production["requested_product_loop_outcome"]["production_mutation_requested"] = True
    cases["blocked-production-mutation"] = production

    return cases


def build_report(summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = default_summary() if summary is None else validate_summary(summary)
    pass_report = build_case_report("pass", source)
    if pass_report["status"] != "allowed":
        raise RealAdopterScenarioImportError("pass case failed to import")
    case_reports = [pass_report]
    for case_id, blocked_summary in blocked_summaries().items():
        case = build_case_report(case_id, blocked_summary)
        if case["status"] != "blocked":
            raise RealAdopterScenarioImportError(f"negative case unexpectedly passed: {case_id}")
        case_reports.append(case)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "version": dual_loop.RELEASE_VERSION,
        "purpose": (
            "Prove one bounded real-adopter issue summary can enter the Product "
            "Loop as metadata-only evidence and reach a concrete spec/eval brief "
            "without raw customer content or production effects."
        ),
        "summary_schema": SUMMARY_SCHEMA_VERSION,
        "case_reports": case_reports,
        "chain_rules": {
            "external_feedback_receipt_required": True,
            "backlog_bridge_required": True,
            "product_owner_reconstruction_required": True,
            "spec_eval_authoring_reconstruction_required": True,
            "product_loop_brief_intake_required": True,
            "raw_issue_text_rejected": True,
            "requester_identity_rejected": True,
            "ai_review_only_rejected": True,
            "production_mutation_blocked": True,
            "customer_visible_action_blocked": True,
        },
        "claim_boundary": dict(CLAIM_BOUNDARY),
        "privacy": dict(PRIVACY),
        "runtime": dict(RUNTIME),
    }
    return validate_report(report)


def validate_report(report: Mapping[str, Any]) -> dict[str, Any]:
    reject_forbidden_fields(report, label=REPORT_SCHEMA_VERSION)
    if report.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise RealAdopterScenarioImportError("real-adopter import report schema_version drifted")
    if report.get("status") != "pass":
        raise RealAdopterScenarioImportError("real-adopter import report must pass")
    case_reports = report.get("case_reports")
    if not isinstance(case_reports, list) or len(case_reports) < 5:
        raise RealAdopterScenarioImportError("real-adopter import report missing case coverage")
    case_by_id = {case.get("case_id"): case for case in case_reports if isinstance(case, Mapping)}
    required_cases = {
        "pass",
        "blocked-raw-issue-text",
        "blocked-identity",
        "blocked-ai-review-only",
        "blocked-production-mutation",
    }
    if set(case_by_id) != required_cases:
        raise RealAdopterScenarioImportError("real-adopter import case coverage drifted")
    if case_by_id["pass"].get("status") != "allowed":
        raise RealAdopterScenarioImportError("real-adopter pass case must be allowed")
    if case_by_id["pass"].get("decision") != "create_product_loop_harness_candidate":
        raise RealAdopterScenarioImportError("real-adopter pass case must create harness candidate")
    for case_id in required_cases - {"pass"}:
        case = case_by_id[case_id]
        if case.get("status") != "blocked" or case.get("decision") != "block_real_adopter_import":
            raise RealAdopterScenarioImportError(f"{case_id} must be blocked")
        if not case.get("blocked_reasons"):
            raise RealAdopterScenarioImportError(f"{case_id} must include blocked reasons")
    rules = report.get("chain_rules")
    if not isinstance(rules, Mapping):
        raise RealAdopterScenarioImportError("real-adopter report missing chain rules")
    for key, expected in {
        "external_feedback_receipt_required": True,
        "backlog_bridge_required": True,
        "product_owner_reconstruction_required": True,
        "spec_eval_authoring_reconstruction_required": True,
        "product_loop_brief_intake_required": True,
        "raw_issue_text_rejected": True,
        "requester_identity_rejected": True,
        "ai_review_only_rejected": True,
        "production_mutation_blocked": True,
        "customer_visible_action_blocked": True,
    }.items():
        if rules.get(key) is not expected:
            raise RealAdopterScenarioImportError(f"chain_rules.{key} must be {expected!r}")
    privacy = report.get("privacy")
    if not isinstance(privacy, Mapping) or privacy.get("metadata_only") is not True:
        raise RealAdopterScenarioImportError("real-adopter report privacy must be metadata-only")
    runtime = report.get("runtime")
    if not isinstance(runtime, Mapping):
        raise RealAdopterScenarioImportError("real-adopter report missing runtime")
    for key, expected in RUNTIME.items():
        if runtime.get(key) is not expected:
            raise RealAdopterScenarioImportError(f"runtime.{key} must be {expected!r}")
    return dict(report)


def write_chain_artifacts(output_dir: Path, chain: Mapping[str, Mapping[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    names = {
        "summary": "real-adopter-issue-summary.json",
        "external_feedback_receipt": "external-feedback-receipt.json",
        "external_feedback_backlog_bridge": "external-feedback-backlog-bridge.json",
        "product_loop_backlog_item": "product-loop-backlog-item.json",
        "product_owner_prioritization_receipt": "product-owner-prioritization-receipt.json",
        "product_spec_eval_candidate": "product-spec-eval-candidate.json",
        "product_spec_eval_authoring_receipt": "product-spec-eval-authoring-receipt.json",
        "product_spec_eval_brief": "product-spec-eval-brief.json",
        "product_loop_brief_intake_receipt": "product-loop-brief-intake-receipt.json",
        "product_loop_scenario": "product-loop-scenario.json",
        "product_loop_run": "product-loop-run.json",
    }
    for key, filename in names.items():
        (output_dir / filename).write_text(dump_json(chain[key]), encoding="utf-8")


def render_markdown(report: Mapping[str, Any]) -> str:
    pass_case = next(case for case in report["case_reports"] if case["case_id"] == "pass")
    lines = [
        "# Real-Adopter Scenario Import",
        "",
        report["purpose"],
        "",
        "## Pass Case",
        "",
        f"- Platform: `{pass_case['platform_id']}`",
        f"- Tags: `{', '.join(pass_case['bounded_tags'])}`",
        f"- Target spec/eval theme: `{pass_case['target_spec_eval_theme']}`",
        f"- Next boundary: `{pass_case['next_boundary']}`",
        "",
        "## Blocked Cases",
        "",
    ]
    for case in report["case_reports"]:
        if case["case_id"] == "pass":
            continue
        lines.append(f"- `{case['case_id']}`: `{', '.join(case['blocked_reasons'])}`")
    lines.extend(
        [
            "",
            "## Privacy Boundary",
            "",
            "The importer keeps raw issue text, identities, logs, screenshots, Agent credentials, "
            "customer-visible replies, external publication, and production mutation out of the Product Loop.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_import(summary_path: Path, output_dir: Path, report_path: Path | None, markdown_path: Path | None, html_path: Path | None) -> dict[str, Any]:
    summary = load_json(summary_path)
    chain = build_chain(summary)
    report = build_report(summary)
    write_chain_artifacts(output_dir, chain)
    output_dir.joinpath("real-adopter-scenario-import-report.json").write_text(
        dump_json(report),
        encoding="utf-8",
    )
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(dump_json(report), encoding="utf-8")
    markdown = render_markdown(report)
    if markdown_path is not None:
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(markdown, encoding="utf-8")
    if html_path is not None:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(
            dual_loop.render_html_report("Real-Adopter Scenario Import", report),
            encoding="utf-8",
        )
    return {
        "schema_version": CLI_SCHEMA_VERSION,
        "status": "ok",
        "summary_id": chain["summary"]["summary_id"],
        "platform_id": chain["summary"]["platform_id"],
        "artifact_count": 11,
        "report": str(output_dir / "real-adopter-scenario-import-report.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "fixtures" / "real-adopter-scenario-import" / "pass",
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--html-output", type=Path)
    parser.add_argument("--print-default-summary", action="store_true")
    args = parser.parse_args()

    if args.print_default_summary:
        print(dump_json(default_summary()), end="")
        return 0

    result = run_import(
        args.summary,
        args.output_dir,
        args.report,
        args.markdown_output,
        args.html_output,
    )
    print(dump_json(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
