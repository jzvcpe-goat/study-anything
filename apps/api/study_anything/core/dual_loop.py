"""Dual-Loop MVP contracts and deterministic local artifact builders.

The Dual-Loop MVP is intentionally metadata-only. It does not call models,
start daemons, mutate production systems, inspect raw source/report bodies, or
collect fine-grained human attention streams. The only bridge between the AI
failure sandbox and the human reconstruction layer is structured JSON
artifacts.
"""

from __future__ import annotations

from html import escape
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


FAILURE_CONTRACT_SCHEMA_VERSION = "failure-contract-v1"
SANDBOX_RECEIPT_SCHEMA_VERSION = "sandbox-receipt-v1"
ATTENTION_TRACE_SCHEMA_VERSION = "attention-reconstruction-trace-v1"
ATTENTION_SUMMARY_SCHEMA_VERSION = "attention-reconstruction-summary-v1"
DUAL_LOOP_GATE_RECEIPT_SCHEMA_VERSION = "dual-loop-gate-receipt-v1"

DUAL_LOOP_CONTRACTS_REPORT_SCHEMA_VERSION = "dual-loop-contracts-verification-v1"
FAILURE_SANDBOX_LITE_REPORT_SCHEMA_VERSION = "failure-sandbox-lite-verification-v1"
ATTENTION_RECONSTRUCTION_LITE_REPORT_SCHEMA_VERSION = (
    "attention-reconstruction-lite-verification-v1"
)
DUAL_LOOP_GATE_REPORT_SCHEMA_VERSION = "dual-loop-gate-verification-v1"

RELEASE_VERSION = "v0.3.31-alpha"
DETERMINISTIC_TIMESTAMP = "2026-06-28T00:00:00Z"

ALLOWED_RISK_LEVELS = ("low", "medium", "high", "blocked")
ALLOWED_SANDBOX_STATUSES = ("passed", "failed", "blocked")
ALLOWED_ATTENTION_STATUSES = ("passed", "failed", "missing")
ALLOWED_GATE_STATUSES = ("allowed", "blocked")

PRIVACY_FLAGS = {
    "raw_source_text_included": False,
    "raw_report_text_included": False,
    "screenshots_included": False,
    "keystrokes_included": False,
    "mouse_coordinates_included": False,
    "eye_tracking_included": False,
    "biometrics_included": False,
    "real_secrets_included": False,
    "cookies_included": False,
    "bearer_tokens_included": False,
    "signed_urls_included": False,
    "user_owned_agent_credentials_included": False,
    "model_calls_performed": False,
}

ISOLATION_BOUNDARY = {
    "physical_isolation": True,
    "structured_artifact_bridge_only": True,
    "ai_sandbox_has_attention_stream_access": False,
    "attention_layer_has_execution_authority": False,
    "production_mutation_allowed": False,
    "daemon_or_hosted_service_started": False,
}

FORBIDDEN_EXACT_KEYS = {
    "api_key",
    "apikey",
    "bearer_token",
    "bearer_tokens",
    "biometric",
    "biometrics",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "eye_tracking",
    "eye_tracking_sample",
    "file_contents",
    "keystroke",
    "keystrokes",
    "model_api_key",
    "mouse_coordinate",
    "mouse_coordinates",
    "password",
    "prompt",
    "prompt_text",
    "raw",
    "raw_attention_stream",
    "raw_diff",
    "raw_report_text",
    "raw_source_text",
    "report_text",
    "screenshot",
    "screenshots",
    "secret",
    "signed_url",
    "signed_urls",
    "source_text",
    "token",
    "user_owned_agent_credentials",
}

SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"https?://[^\s?]+[?&](?:X-Amz-Signature|signature|sig|token)="),
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/private/(?:tmp|var/folders)/[^\s\"']+"),
)

FORBIDDEN_TEXT = (
    "raw private source text",
    "private source text:",
    "raw report text:",
    "learner answer:",
    "screenshot pixels",
    "keystroke log",
    "mouse coordinate",
    "eye tracking sample",
    "biometric sample",
    "cookie:",
    "signed url:",
    "agent credential:",
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "AGENT_LLM_API_KEY=",
)


class DualLoopContractError(ValueError):
    """Raised when a Dual-Loop artifact is unsafe or malformed."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DualLoopContractError(f"Expected object JSON at {path}")
    return payload


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump_json(dict(payload)), encoding="utf-8")


def _normalized_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


def assert_metadata_only(value: Any, *, label: str = "artifact") -> None:
    """Reject raw content, surveillance fields, local private paths, and secrets."""

    def walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                normalized = _normalized_key(key)
                if normalized in FORBIDDEN_EXACT_KEYS and child is not False:
                    raise DualLoopContractError(f"{label}:{path}.{key} uses forbidden field")
                walk(child, f"{path}.{key}")
            return
        if isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")
            return
        if isinstance(node, str):
            lowered = node.lower()
            forbidden = [needle for needle in FORBIDDEN_TEXT if needle.lower() in lowered]
            forbidden.extend(pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(node))
            if forbidden:
                raise DualLoopContractError(
                    f"{label}:{path} contains private-looking data: {forbidden}"
                )

    walk(value, "$")


def validate_privacy_flags(payload: Mapping[str, Any], *, label: str) -> None:
    privacy = payload.get("privacy")
    if not isinstance(privacy, Mapping):
        raise DualLoopContractError(f"{label} must include privacy flags")
    for key, expected in PRIVACY_FLAGS.items():
        if privacy.get(key) is not expected:
            raise DualLoopContractError(f"{label}.privacy.{key} must be {expected!r}")


def validate_isolation(payload: Mapping[str, Any], *, label: str) -> None:
    isolation = payload.get("isolation")
    if not isinstance(isolation, Mapping):
        raise DualLoopContractError(f"{label} must include isolation boundary")
    for key, expected in ISOLATION_BOUNDARY.items():
        if isolation.get(key) is not expected:
            raise DualLoopContractError(f"{label}.isolation.{key} must be {expected!r}")


def validate_failure_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    assert_metadata_only(payload, label=FAILURE_CONTRACT_SCHEMA_VERSION)
    if payload.get("schema_version") != FAILURE_CONTRACT_SCHEMA_VERSION:
        raise DualLoopContractError("Invalid failure contract schema_version")
    for key in ("contract_id", "project_id", "task_ref", "risk", "failure_boundaries"):
        if not payload.get(key):
            raise DualLoopContractError(f"failure contract missing {key}")
    risk = payload["risk"]
    if not isinstance(risk, Mapping):
        raise DualLoopContractError("failure contract risk must be an object")
    if risk.get("level") not in ALLOWED_RISK_LEVELS:
        raise DualLoopContractError("failure contract risk.level is invalid")
    if risk.get("budget_level") not in ALLOWED_RISK_LEVELS:
        raise DualLoopContractError("failure contract risk.budget_level is invalid")
    if risk.get("production_mutation_allowed") is not False:
        raise DualLoopContractError("failure contract must block production mutation")
    if risk.get("real_user_exposure_allowed") is not False:
        raise DualLoopContractError("failure contract must block real user exposure")
    if risk.get("irreversible_effects_allowed") is not False:
        raise DualLoopContractError("failure contract must block irreversible effects")
    boundaries = payload["failure_boundaries"]
    if not isinstance(boundaries, Mapping):
        raise DualLoopContractError("failure boundaries must be an object")
    if boundaries.get("rollback_required") is not True:
        raise DualLoopContractError("failure contract must require rollback")
    validate_privacy_flags(payload, label="failure_contract")
    validate_isolation(payload, label="failure_contract")
    return dict(payload)


def validate_sandbox_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    assert_metadata_only(payload, label=SANDBOX_RECEIPT_SCHEMA_VERSION)
    if payload.get("schema_version") != SANDBOX_RECEIPT_SCHEMA_VERSION:
        raise DualLoopContractError("Invalid sandbox receipt schema_version")
    if payload.get("status") not in ALLOWED_SANDBOX_STATUSES:
        raise DualLoopContractError("sandbox receipt status is invalid")
    if not payload.get("contract_id") or not payload.get("sandbox_run_id"):
        raise DualLoopContractError("sandbox receipt missing ids")
    risk_budget = payload.get("risk_budget")
    if not isinstance(risk_budget, Mapping):
        raise DualLoopContractError("sandbox receipt must include risk_budget")
    mutation_summary = payload.get("mutation_summary")
    if not isinstance(mutation_summary, Mapping):
        raise DualLoopContractError("sandbox receipt must include mutation_summary")
    if mutation_summary.get("production_mutation") is not False:
        raise DualLoopContractError("sandbox receipt must not mutate production")
    if mutation_summary.get("irreversible_external_effects") is not False:
        raise DualLoopContractError("sandbox receipt must not create irreversible effects")
    validate_privacy_flags(payload, label="sandbox_receipt")
    validate_isolation(payload, label="sandbox_receipt")
    return dict(payload)


def validate_attention_trace(payload: Mapping[str, Any]) -> dict[str, Any]:
    assert_metadata_only(payload, label=ATTENTION_TRACE_SCHEMA_VERSION)
    if payload.get("schema_version") != ATTENTION_TRACE_SCHEMA_VERSION:
        raise DualLoopContractError("Invalid attention trace schema_version")
    if not payload.get("trace_id") or not payload.get("contract_id"):
        raise DualLoopContractError("attention trace missing ids")
    if payload.get("data_collection_mode") != "active_reconstruction_metadata_only":
        raise DualLoopContractError("attention trace must be active metadata-only")
    checkpoints = payload.get("active_reconstruction_checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        raise DualLoopContractError("attention trace must include active checkpoints")
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, Mapping):
            raise DualLoopContractError("attention checkpoint must be object")
        if checkpoint.get("evidence_strength") != "strong":
            raise DualLoopContractError("attention checkpoint must be strong evidence")
        if checkpoint.get("status") != "passed":
            raise DualLoopContractError("attention checkpoint must pass")
    passive = payload.get("passive_attention")
    if not isinstance(passive, Mapping) or passive.get("evidence_strength") != "weak":
        raise DualLoopContractError("passive attention must be marked weak")
    validate_privacy_flags(payload, label="attention_trace")
    validate_isolation(payload, label="attention_trace")
    return dict(payload)


def validate_attention_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    assert_metadata_only(payload, label=ATTENTION_SUMMARY_SCHEMA_VERSION)
    if payload.get("schema_version") != ATTENTION_SUMMARY_SCHEMA_VERSION:
        raise DualLoopContractError("Invalid attention summary schema_version")
    if payload.get("status") not in ALLOWED_ATTENTION_STATUSES:
        raise DualLoopContractError("attention summary status is invalid")
    if not payload.get("summary_id") or not payload.get("contract_id"):
        raise DualLoopContractError("attention summary missing ids")
    if payload.get("passive_attention_only") is not False:
        raise DualLoopContractError("attention summary cannot rely on passive attention only")
    required_total = int(payload.get("required_mrus_total") or 0)
    required_passed = int(payload.get("required_mrus_passed") or 0)
    if payload.get("status") == "passed" and required_passed < required_total:
        raise DualLoopContractError("passed attention summary must pass all required MRUs")
    validate_privacy_flags(payload, label="attention_summary")
    validate_isolation(payload, label="attention_summary")
    return dict(payload)


def validate_gate_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    assert_metadata_only(payload, label=DUAL_LOOP_GATE_RECEIPT_SCHEMA_VERSION)
    if payload.get("schema_version") != DUAL_LOOP_GATE_RECEIPT_SCHEMA_VERSION:
        raise DualLoopContractError("Invalid dual-loop gate schema_version")
    if payload.get("status") not in ALLOWED_GATE_STATUSES:
        raise DualLoopContractError("dual-loop gate status is invalid")
    checks = payload.get("checks")
    if not isinstance(checks, Mapping):
        raise DualLoopContractError("dual-loop gate must include checks")
    if checks.get("neither_loop_dominates") is not True:
        raise DualLoopContractError("dual-loop gate must keep both loops equal weight")
    if payload.get("status") == "allowed":
        required_true = (
            "sandbox_within_budget",
            "sandbox_contained_failures",
            "attention_reconstruction_passed",
            "isolation_boundary_valid",
            "structured_artifact_bridge_only",
        )
        for key in required_true:
            if checks.get(key) is not True:
                raise DualLoopContractError(f"allowed dual-loop gate requires {key}")
    validate_privacy_flags(payload, label="dual_loop_gate")
    validate_isolation(payload, label="dual_loop_gate")
    return dict(payload)


def failure_contract_demo() -> dict[str, Any]:
    return {
        "schema_version": FAILURE_CONTRACT_SCHEMA_VERSION,
        "contract_id": "failure-contract-demo-001",
        "project_id": "study-anything",
        "task_ref": "task:dual-loop-demo",
        "candidate_artifact_ref": "artifact:metadata-only-demo-change",
        "created_at": DETERMINISTIC_TIMESTAMP,
        "risk": {
            "level": "medium",
            "budget_level": "medium",
            "score": 0.42,
            "production_mutation_allowed": False,
            "real_user_exposure_allowed": False,
            "irreversible_effects_allowed": False,
        },
        "failure_boundaries": {
            "allowed_failure_modes": [
                "fixture_validation_failed",
                "sandbox_command_failed",
                "rollback_rehearsal_failed",
            ],
            "forbidden_propagations": [
                "production_mutation",
                "real_user_exposure",
                "irreversible_external_effect",
                "knowledge_base_publication",
            ],
            "rollback_required": True,
            "rollback_strategy_ref": "rollback:metadata-only-revert-plan",
        },
        "minimum_reconstructable_units": [
            {
                "mru_id": "mru-failure-path",
                "kind": "Failure Path",
                "blocking": True,
                "prompt_ref": "prompt-ref:failure-path",
            },
            {
                "mru_id": "mru-rollback-trigger",
                "kind": "Rollback Trigger",
                "blocking": True,
                "prompt_ref": "prompt-ref:rollback-trigger",
            },
            {
                "mru_id": "mru-acceptance-boundary",
                "kind": "Acceptance Boundary",
                "blocking": True,
                "prompt_ref": "prompt-ref:acceptance-boundary",
            },
        ],
        "isolation": dict(ISOLATION_BOUNDARY),
        "privacy": dict(PRIVACY_FLAGS),
        "verification_commands": [
            "python3 scripts/verify_failure_sandbox_lite.py --check",
            "python3 scripts/verify_attention_reconstruction_lite.py --check",
            "python3 scripts/verify_dual_loop_gate.py --check",
        ],
    }


def sandbox_receipt_demo(*, within_budget: bool = True, status: str = "passed") -> dict[str, Any]:
    return {
        "schema_version": SANDBOX_RECEIPT_SCHEMA_VERSION,
        "receipt_id": "sandbox-receipt-demo-001",
        "contract_id": "failure-contract-demo-001",
        "sandbox_run_id": "sandbox-run-demo-001",
        "sandbox_level": "sandbox-lite",
        "status": status,
        "executed_at": DETERMINISTIC_TIMESTAMP,
        "observed_failures": [
            {
                "failure_id": "failure-demo-contained-001",
                "category": "fixture_validation_failed",
                "containment_status": "contained",
                "reversible": True,
                "propagated": False,
                "artifact_ref": "artifact:sandbox-lite-contained-failure",
            }
        ],
        "mutation_summary": {
            "production_mutation": False,
            "irreversible_external_effects": False,
            "file_mutations": [],
            "external_effects": [],
            "real_user_exposure": False,
        },
        "rollback": {
            "available": True,
            "rehearsed": True,
            "rollback_ref": "rollback:metadata-only-revert-plan",
        },
        "risk_budget": {
            "budget_level": "medium",
            "observed_level": "medium" if within_budget else "high",
            "within_budget": within_budget,
        },
        "isolation": dict(ISOLATION_BOUNDARY),
        "privacy": dict(PRIVACY_FLAGS),
    }


def attention_trace_demo() -> dict[str, Any]:
    return {
        "schema_version": ATTENTION_TRACE_SCHEMA_VERSION,
        "trace_id": "attention-trace-demo-001",
        "contract_id": "failure-contract-demo-001",
        "environment_id": "attention-reconstruction-lite",
        "created_at": DETERMINISTIC_TIMESTAMP,
        "data_collection_mode": "active_reconstruction_metadata_only",
        "passive_attention": {
            "section_seen_count": 3,
            "visible_time_bucket": "1-5m",
            "revisit_count_bucket": "1-2",
            "evidence_strength": "weak",
            "blocking": False,
        },
        "active_reconstruction_checkpoints": [
            {
                "checkpoint_id": "checkpoint-failure-path",
                "mru_id": "mru-failure-path",
                "mru_kind": "Failure Path",
                "response_kind": "selected_boundary_ref",
                "selected_boundary_ref": "boundary:production-mutation-forbidden",
                "status": "passed",
                "evidence_strength": "strong",
            },
            {
                "checkpoint_id": "checkpoint-rollback-trigger",
                "mru_id": "mru-rollback-trigger",
                "mru_kind": "Rollback Trigger",
                "response_kind": "selected_trigger_ref",
                "selected_trigger_ref": "rollback:metadata-only-revert-plan",
                "status": "passed",
                "evidence_strength": "strong",
            },
            {
                "checkpoint_id": "checkpoint-acceptance-boundary",
                "mru_id": "mru-acceptance-boundary",
                "mru_kind": "Acceptance Boundary",
                "response_kind": "confirmed_boundary_ref",
                "confirmed_boundary_ref": "risk-budget:medium",
                "status": "passed",
                "evidence_strength": "strong",
            },
        ],
        "forbidden_streams": {
            "screenshots": False,
            "keystrokes": False,
            "mouse_coordinates": False,
            "eye_tracking": False,
            "biometrics": False,
            "raw_report_text": False,
        },
        "isolation": dict(ISOLATION_BOUNDARY),
        "privacy": dict(PRIVACY_FLAGS),
    }


def attention_summary_demo(*, status: str = "passed") -> dict[str, Any]:
    required_total = 3
    required_passed = 3 if status == "passed" else 1
    return {
        "schema_version": ATTENTION_SUMMARY_SCHEMA_VERSION,
        "summary_id": "attention-summary-demo-001",
        "trace_id": "attention-trace-demo-001",
        "contract_id": "failure-contract-demo-001",
        "status": status,
        "created_at": DETERMINISTIC_TIMESTAMP,
        "required_mrus_total": required_total,
        "required_mrus_passed": required_passed,
        "missing_mrus": [] if status == "passed" else ["mru-acceptance-boundary"],
        "passive_attention_only": False,
        "strong_evidence_count": required_passed,
        "weak_evidence_count": 1,
        "reconstruction_level": "minimum_reconstructable_unit_passed",
        "autonomy_expansion_recommendation": status == "passed",
        "focus_queue_refs": [
            "mru:mru-failure-path",
            "mru:mru-rollback-trigger",
            "mru:mru-acceptance-boundary",
        ],
        "isolation": dict(ISOLATION_BOUNDARY),
        "privacy": dict(PRIVACY_FLAGS),
    }


def evaluate_dual_loop_gate(
    failure_contract: Mapping[str, Any],
    sandbox_receipt: Mapping[str, Any],
    attention_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    contract = validate_failure_contract(failure_contract)
    sandbox = validate_sandbox_receipt(sandbox_receipt)
    attention: dict[str, Any] | None = None
    attention_valid = False
    if attention_summary is not None:
        attention = validate_attention_summary(attention_summary)
        attention_valid = attention.get("status") == "passed"

    sandbox_within_budget = bool(sandbox["risk_budget"]["within_budget"])
    sandbox_passed = sandbox.get("status") == "passed"
    sandbox_contained = all(
        isinstance(item, Mapping)
        and item.get("containment_status") == "contained"
        and item.get("propagated") is False
        for item in sandbox.get("observed_failures", [])
    )
    isolation_valid = all(contract["isolation"].get(key) is expected for key, expected in ISOLATION_BOUNDARY.items())
    reasons: list[str] = []
    if not sandbox_passed or not sandbox_contained:
        reasons.append("sandbox_failures_not_contained")
    if not sandbox_within_budget:
        reasons.append("sandbox_risk_outside_budget")
    if attention_summary is None:
        reasons.append("attention_reconstruction_missing")
    elif not attention_valid:
        reasons.append("attention_reconstruction_failed")
    if not isolation_valid:
        reasons.append("isolation_boundary_invalid")

    allowed = not reasons
    receipt = {
        "schema_version": DUAL_LOOP_GATE_RECEIPT_SCHEMA_VERSION,
        "gate_id": "dual-loop-gate-demo-001",
        "contract_id": contract["contract_id"],
        "created_at": DETERMINISTIC_TIMESTAMP,
        "status": "allowed" if allowed else "blocked",
        "decision": "promote_to_next_sandbox" if allowed else "block_promotion",
        "reasons": reasons,
        "input_refs": {
            "failure_contract_ref": "failure-contract.json",
            "sandbox_receipt_ref": "sandbox-receipt.json",
            "attention_summary_ref": "attention-summary.json" if attention is not None else None,
        },
        "checks": {
            "sandbox_within_budget": sandbox_within_budget,
            "sandbox_contained_failures": sandbox_passed and sandbox_contained,
            "attention_reconstruction_passed": attention_valid,
            "attention_reconstruction_required": True,
            "isolation_boundary_valid": isolation_valid,
            "structured_artifact_bridge_only": True,
            "neither_loop_dominates": True,
        },
        "next_sandbox_level": "sandbox-1" if allowed else None,
        "isolation": dict(ISOLATION_BOUNDARY),
        "privacy": dict(PRIVACY_FLAGS),
    }
    return validate_gate_receipt(receipt)


def render_html_report(title: str, payload: Mapping[str, Any]) -> str:
    validate_privacy_flags(payload, label=title)
    assert_metadata_only(payload, label=f"{title}-html")
    body = escape(dump_json(payload))
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<meta charset=\"utf-8\">\n"
        f"<title>{escape(title)}</title>\n"
        "<body>\n"
        f"<h1>{escape(title)}</h1>\n"
        "<p>Metadata-only local artifact. No model calls, daemon, production mutation, raw source text, or surveillance streams.</p>\n"
        f"<pre>{body}</pre>\n"
        "</body>\n"
        "</html>\n"
    )


def write_html_report(path: str | Path, title: str, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html_report(title, payload), encoding="utf-8")


def output_ref(path: Path) -> str:
    return path.as_posix()
