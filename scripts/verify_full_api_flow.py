#!/usr/bin/env python3
"""Verify a running Study Anything API with the public learning flow."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import format_api_unreachable, resolve_api_base, verifier_name_from_file


API_BASE = resolve_api_base()
VERIFIER_NAME = verifier_name_from_file(__file__)
PRIVATE_SOURCE_TEXT = "A launch smoke test should create a quiz, grade an answer, and update mastery."
PRIVATE_ANSWER = "The system uses source evidence to update mastery."
PRIVATE_EXPORT_NOTE = "Smoke export note must not be included."
PRIVATE_USER = "smoke-user"
PRIVATE_REFERENCE = "demo://full-api-flow"
PRIVATE_TITLE = "Full API Flow"
FORBIDDEN_LITERALS = (
    PRIVATE_SOURCE_TEXT,
    PRIVATE_ANSWER,
    PRIVATE_EXPORT_NOTE,
    PRIVATE_USER,
    PRIVATE_REFERENCE,
    PRIVATE_TITLE,
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
)


def sanitize_text(value: str | bytes | None) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    replacements = {
        PRIVATE_SOURCE_TEXT: "<private-source-text>",
        PRIVATE_ANSWER: "<private-answer>",
        PRIVATE_EXPORT_NOTE: "<private-note>",
        PRIVATE_USER: "<private-user>",
        PRIVATE_REFERENCE: "<private-reference>",
        PRIVATE_TITLE: "<private-title>",
    }
    for literal, replacement in replacements.items():
        text = text.replace(literal, replacement)
    text = re.sub(r"(?i)launch smoke test", "<private-source-text>", text)
    text = re.sub(r"(?i)source evidence", "<private-answer>", text)
    text = re.sub(r"(?i)smoke export note", "<private-note>", text)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<uuid>", text)
    text = re.sub(r"/Users/[^\s\"'?&]+", "<local-path>", text)
    text = re.sub(r"/private/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"/var/folders/[^\s\"'?&]+", "<temp-path>", text)
    text = re.sub(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}", r"\1=<redacted>", text)
    text = re.sub(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", "sk-<redacted>", text)
    text = re.sub(r"([?&](?:api[_-]?key|token|secret)=)[^&\s\"']+", r"\1<redacted>", text, flags=re.IGNORECASE)
    return text.strip()[:1600]


def classify_failure(message: str) -> str:
    lowered = message.lower()
    if (
        "runner appears to block localhost sockets" in lowered
        or "blocks localhost" in lowered
        or "operation not permitted" in lowered
        or "permission denied" in lowered
        or "localhost_socket_blocked" in lowered
    ):
        return "localhost_socket_blocked"
    if "cannot reach study anything" in lowered or "connection refused" in lowered or "urlopen error" in lowered:
        return "api_unreachable"
    if "api health is not ok" in lowered:
        return "api_health_not_ok"
    if "agent eval required gates failed" in lowered or "agent eval artifact is not ready" in lowered:
        return "agent_eval_failed"
    if "agent audit did not verify" in lowered or "agent audit schema" in lowered:
        return "agent_audit_failed"
    if "leaked private" in lowered or "leaked local path" in lowered or "leaked private smoke data" in lowered:
        return "privacy_leak"
    if "schema is not" in lowered or "schema is invalid" in lowered or "schema mismatch" in lowered:
        return "response_schema_invalid"
    if "expected completed stage" in lowered or "did not count the completed" in lowered:
        return "learning_flow_incomplete"
    if "explicit consent" in lowered or "destructive" in lowered or "plaintext" in lowered:
        return "safety_contract_failed"
    return "full_api_flow_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "./scripts/launch_skill_mode.sh",
        f"API_BASE={API_BASE} python3 scripts/verify_full_api_flow.py",
        "python3 scripts/diagnose_adoption.py",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run the verifier from a normal terminal or host shell that permits localhost sockets.",
            "If this came from Codex or another sandboxed Agent, collect this blocked report and rerun outside the sandbox.",
        ],
        "api_unreachable": [
            "Start the local API first with `./scripts/launch_skill_mode.sh`.",
            "If the API is already running on another port, pass it with `API_BASE=http://127.0.0.1:<port>`.",
        ],
        "api_health_not_ok": [
            "Open `/v1/health` on the configured API_BASE and inspect the reported service status.",
            "Restart Skill Mode, then rerun the verifier.",
        ],
        "agent_eval_failed": [
            "Run the flow with the bundled fake agent first; required eval gates must pass before publishing evidence.",
            "Inspect `/v1/sessions/<session_id>/agent-eval/artifact` from the failed run if you have local access.",
        ],
        "agent_audit_failed": [
            "Verify the fake agent or configured provider covered quiz generation, grading, synthesis, and source verification.",
            "Inspect `/v1/sessions/<session_id>/agent-audit` locally; do not publish raw source or answers.",
        ],
        "privacy_leak": [
            "Do not share the raw transcript publicly.",
            "Fix the leaking API response or artifact before using this run as release evidence.",
        ],
        "response_schema_invalid": [
            "Confirm the API server was started from the same checkout as this verifier.",
            "Rerun setup with `python3 scripts/setup_env.py` if the API code and verifier are out of sync.",
        ],
        "learning_flow_incomplete": [
            "Rerun the fake-agent flow; the smoke session must reach `completed` before release evidence is valid.",
            "Check the session events endpoint locally for the first failed workflow stage.",
        ],
        "safety_contract_failed": [
            "Keep restore/export actions in preview or explicit-consent mode.",
            "Do not publish evidence from a run that exposes plaintext, destructive restore, or implicit PMF export.",
        ],
    }
    return matrix.get(classification, ["Rerun the verifier after starting the local Skill Mode API."]) + common


def failure_report(exc: BaseException) -> dict[str, Any]:
    diagnostic = sanitize_text(str(exc))
    classification = classify_failure(diagnostic)
    report = {
        "status": "blocked",
        "classification": classification,
        "diagnostic": diagnostic,
        "next_steps": failure_next_steps(classification),
        "source": {
            "verifier": VERIFIER_NAME,
            "api_base": sanitize_text(API_BASE),
        },
        "privacy": {
            "raw_source_text_included": False,
            "learner_answers_included": False,
            "real_model_keys_included": False,
            "local_absolute_paths_included": False,
        },
    }
    assert_failure_report_redacted(report)
    return report


def format_failure_for_human(report: dict[str, Any]) -> str:
    steps = [
        f"- {sanitize_text(str(step))}"
        for step in report.get("next_steps", [])
        if isinstance(step, str) and step.strip()
    ]
    return "\n".join(
        [
            f"{VERIFIER_NAME} failed:",
            f"classification: {sanitize_text(str(report.get('classification') or 'full_api_flow_failed'))}",
            f"Diagnostic: {sanitize_text(str(report.get('diagnostic') or '')) or '(empty)'}",
            "Next steps:",
            *(steps or ["- Run ./scripts/launch_skill_mode.sh, then rerun this verifier."]),
        ]
    )


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"/private/(?:var/)?folders/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise RuntimeError(f"Full API verifier failure report leaked private data: {leaks}")


def request(path: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{API_BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    try:
        with urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"{exc.code} {path}: {detail}") from exc
    except (URLError, OSError) as exc:
        raise RuntimeError(
            format_api_unreachable(API_BASE, exc, verifier=VERIFIER_NAME)
        ) from exc


def main() -> None:
    health = request("/v1/health")
    if health.get("status") != "ok":
        raise RuntimeError(f"API health is not ok: {health}")

    commercial_readiness = request("/v1/commercial/readiness")
    if commercial_readiness.get("schema_version") != "commercial-readiness-v1":
        raise RuntimeError(
            f"Commercial readiness schema is not commercial-readiness-v1: {commercial_readiness}"
        )
    if commercial_readiness.get("launch_assessment", {}).get("hosted_paid_services") != "not_ready":
        raise RuntimeError(f"Hosted paid services should not be ready in local alpha: {commercial_readiness}")
    if (commercial_readiness.get("privacy") or {}).get("real_model_keys_stored_by_study_anything"):
        raise RuntimeError(f"Commercial readiness reported stored model keys: {commercial_readiness}")

    recovery = request("/v1/recovery/status")
    if recovery.get("schema_version") != "recovery-status-v1":
        raise RuntimeError(f"Recovery status schema is not recovery-status-v1: {recovery}")
    if recovery.get("restore_api_enabled"):
        raise RuntimeError(f"Recovery status exposed destructive restore through the API: {recovery}")
    serialized_recovery = json.dumps(recovery, ensure_ascii=False)
    forbidden_recovery_fragments = ["/Users/", "/home/runner", "/private/", "OPENAI_API_KEY", "sk-"]
    leaked_fragments = [fragment for fragment in forbidden_recovery_fragments if fragment in serialized_recovery]
    if leaked_fragments:
        raise RuntimeError(f"Recovery status leaked local path or secret-looking data: {leaked_fragments}")

    plugins = request("/v1/plugins")
    if not isinstance(plugins, list):
        raise RuntimeError("Plugin endpoint did not return a list.")
    registry_verified_plugins = [
        plugin
        for plugin in plugins
        if plugin.get("trust", {}).get("registry_status") == "digest_verified"
    ]
    if not registry_verified_plugins:
        raise RuntimeError(f"No bundled plugin reported registry digest verification: {plugins}")
    registry_review = request("/v1/plugins/registry-review")
    if registry_review.get("schema_version") != "plugin-registry-review-v1":
        raise RuntimeError(
            f"Plugin registry review schema is not plugin-registry-review-v1: {registry_review}"
        )
    if registry_review.get("remote_code_downloads_allowed") or registry_review.get("entrypoints_executed"):
        raise RuntimeError(f"Plugin registry review must remain metadata-only: {registry_review}")
    if registry_review.get("verified_count", 0) < 1:
        raise RuntimeError(f"Plugin registry review did not count verified plugins: {registry_review}")
    plugin_sdk = request("/v1/plugins/sdk")
    if plugin_sdk.get("schema_version") != "plugin-sdk-v1":
        raise RuntimeError(f"Plugin SDK schema is not plugin-sdk-v1: {plugin_sdk}")
    if plugin_sdk.get("remote_code_downloads_allowed") or plugin_sdk.get("entrypoints_executed"):
        raise RuntimeError(f"Plugin SDK contract must remain metadata-only: {plugin_sdk}")
    plugin_capabilities = request("/v1/plugins/capabilities")
    if plugin_capabilities.get("schema_version") != "plugin-capability-index-v1":
        raise RuntimeError(f"Plugin capability index schema is invalid: {plugin_capabilities}")
    if (plugin_capabilities.get("privacy") or {}).get("entrypoints_executed"):
        raise RuntimeError(f"Plugin capability index executed entrypoints: {plugin_capabilities}")
    plugin_ids = {
        plugin.get("plugin_id")
        for plugin in plugin_capabilities.get("items", [])
        if isinstance(plugin, dict)
    }
    if "example-enrichment-importer" not in plugin_ids:
        raise RuntimeError(f"Plugin capability index did not include enrichment sample: {plugin_capabilities}")
    plugin_validation = request(
        "/v1/plugins/validate-package",
        {"source_path": "plugins/example-exporter"},
    )
    if plugin_validation.get("schema_version") != "plugin-package-validation-v1":
        raise RuntimeError(f"Plugin package validation schema is invalid: {plugin_validation}")
    if plugin_validation.get("status") != "valid":
        raise RuntimeError(f"Plugin package validation did not pass: {plugin_validation}")
    if plugin_validation.get("execution_allowed_by_validation"):
        raise RuntimeError(f"Plugin package validation attempted execution: {plugin_validation}")

    agents = request("/v1/agents/status")
    if agents.get("schema_version") != "agent-v1":
        raise RuntimeError(f"Agent status is not agent-v1: {agents}")

    session = request(
        "/v1/sessions",
        {"user_id": "smoke-user", "track": "ACADEMIC", "use_demo_agent": True},
    )
    session_id = session["session_id"]
    request(
        f"/v1/sessions/{session_id}/reading",
        {
            "source_type": "local_text",
            "reference": "demo://full-api-flow",
            "title": "Full API Flow",
            "text": "A launch smoke test should create a quiz, grade an answer, and update mastery.",
        },
    )
    teaching = request(
        f"/v1/sessions/{session_id}/teaching-layers",
        {"layers": ["overview", "glossary"]},
    )
    if teaching.get("schema_version") != "teaching-layers-v1":
        raise RuntimeError(f"Teaching layers schema is not teaching-layers-v1: {teaching}")
    teaching_layers = teaching.get("layers") or []
    layer_names = {item.get("layer") for item in teaching_layers if isinstance(item, dict)}
    if not {"overview", "glossary"}.issubset(layer_names):
        raise RuntimeError(f"Teaching layers did not include overview and glossary: {teaching}")
    teaching_tasks = {
        (item.get("agent") or {}).get("task_type")
        for item in teaching_layers
        if isinstance(item, dict)
    }
    if not {"teach.overview", "teach.glossary"}.issubset(teaching_tasks):
        raise RuntimeError(f"Teaching layers did not include required Agent tasks: {teaching}")
    running = request(f"/v1/sessions/{session_id}/run", {})
    quiz_id = running["quiz_items"][0]["item_id"]
    completed = request(
        f"/v1/sessions/{session_id}/answers",
        {"answers": {quiz_id: "The system uses source evidence to update mastery."}},
    )
    if completed["stage"] != "completed":
        raise RuntimeError(f"Expected completed stage, got {completed['stage']}")
    agent_audit = request(f"/v1/sessions/{session_id}/agent-audit")
    if agent_audit.get("schema_version") != "agent-audit-v1":
        raise RuntimeError(f"Agent audit schema is not agent-audit-v1: {agent_audit}")
    if agent_audit.get("status") != "verified":
        raise RuntimeError(f"Agent audit did not verify required tasks: {agent_audit}")
    agent_eval_artifact = request(f"/v1/sessions/{session_id}/agent-eval/artifact")
    if agent_eval_artifact.get("schema_version") != "agent-eval-artifact-v1":
        raise RuntimeError(f"Agent eval artifact schema is not agent-eval-artifact-v1: {agent_eval_artifact}")
    if agent_eval_artifact.get("status") != "ready_for_external_eval":
        raise RuntimeError(f"Agent eval artifact is not ready: {agent_eval_artifact}")
    required_eval_gates = [
        gate for gate in agent_eval_artifact.get("native_gates", []) if gate.get("required")
    ]
    failed_eval_gates = [gate for gate in required_eval_gates if gate.get("status") != "pass"]
    if failed_eval_gates:
        raise RuntimeError(f"Agent eval required gates failed: {failed_eval_gates}")
    adapter_ids = {
        adapter.get("adapter_id") for adapter in agent_eval_artifact.get("adapter_strategy", [])
    }
    expected_adapter_ids = {"promptfoo", "deepeval", "langchain-agentevals", "ragas"}
    if adapter_ids != expected_adapter_ids:
        raise RuntimeError(f"Agent eval adapter strategy mismatch: {adapter_ids}")
    serialized_eval = json.dumps(agent_eval_artifact, ensure_ascii=False)
    if (
        "launch smoke test" in serialized_eval.lower()
        or "source evidence" in serialized_eval.lower()
        or "smoke-user" in serialized_eval
    ):
        raise RuntimeError(f"Agent eval artifact leaked private smoke data: {agent_eval_artifact}")
    metrics = request("/v1/metrics/pmf")
    if metrics.get("schema_version") != "pmf-v1":
        raise RuntimeError(f"PMF metrics schema is not pmf-v1: {metrics}")
    if metrics.get("sessions", {}).get("completed", 0) < 1:
        raise RuntimeError(f"PMF metrics did not count the completed smoke session: {metrics}")
    adoption_telemetry = request("/v1/adoption/telemetry")
    if adoption_telemetry.get("schema_version") != "adoption-telemetry-v1":
        raise RuntimeError(f"Adoption telemetry schema is not adoption-telemetry-v1: {adoption_telemetry}")
    telemetry_privacy = adoption_telemetry.get("privacy") or {}
    if telemetry_privacy.get("aggregate_only") is not True or telemetry_privacy.get("automatic_upload") is not False:
        raise RuntimeError(f"Adoption telemetry privacy contract is unsafe: {adoption_telemetry}")
    pmf_readiness = request("/v1/pmf/readiness")
    if pmf_readiness.get("schema_version") != "pmf-readiness-v1":
        raise RuntimeError(f"PMF readiness schema is not pmf-readiness-v1: {pmf_readiness}")
    if pmf_readiness.get("commercial_boundary", {}).get("hosted_paid_services_status") != "not_ready":
        raise RuntimeError(f"PMF readiness should keep hosted services not_ready: {pmf_readiness}")
    intent = request(
        "/v1/pmf/interest",
        {
            "user_id": "smoke-user",
            "services": ["hosted_alpha"],
            "source": "verify_full_api_flow",
        },
    )
    if not intent.get("local_only"):
        raise RuntimeError(f"PMF interest should be local-only: {intent}")
    try:
        request("/v1/pmf/export", {"destination": "self_archive"})
    except RuntimeError as exc:
        if "409" not in str(exc):
            raise
    else:
        raise RuntimeError("PMF export should require explicit consent.")
    export = request(
        "/v1/pmf/export",
        {
            "consent_to_share": True,
            "destination": "self_archive",
            "note": "Smoke export note must not be included.",
        },
    )
    if export.get("schema_version") != "pmf-export-v1":
        raise RuntimeError(f"PMF export schema is not pmf-export-v1: {export}")
    if export.get("adoption_telemetry", {}).get("schema_version") != "adoption-telemetry-v1":
        raise RuntimeError(f"PMF export did not include adoption telemetry: {export}")
    if export.get("pmf_readiness", {}).get("schema_version") != "pmf-readiness-v1":
        raise RuntimeError(f"PMF export did not include PMF readiness: {export}")
    serialized_export = json.dumps(export, ensure_ascii=False)
    if "Smoke export note" in serialized_export or "smoke-user" in serialized_export:
        raise RuntimeError(f"PMF export leaked private smoke data: {export}")
    sync_status = request("/v1/sync/status")
    if not sync_status.get("encrypted_package_supported"):
        raise RuntimeError(f"Sync status is not package-ready: {sync_status}")
    if sync_status.get("hosted_sync_enabled"):
        raise RuntimeError(f"Hosted sync should stay disabled in self-host alpha: {sync_status}")
    sync_export = request(
        "/v1/sync/export",
        {"passphrase": "verify full api encrypted sync passphrase"},
    )
    if sync_export.get("package", {}).get("schema_version") != "sync-package-v1":
        raise RuntimeError(f"Sync export schema is not sync-package-v1: {sync_export}")
    serialized_sync_export = json.dumps(sync_export, ensure_ascii=False)
    if (
        "smoke-user" in serialized_sync_export
        or "launch smoke test" in serialized_sync_export.lower()
        or "source evidence" in serialized_sync_export.lower()
    ):
        raise RuntimeError(f"Sync export leaked private smoke data: {sync_export}")
    sync_inspect = request(
        "/v1/sync/inspect",
        {
            "passphrase": "verify full api encrypted sync passphrase",
            "package": sync_export["package"],
        },
    )
    if sync_inspect.get("schema_version") != "sync-inspect-v1":
        raise RuntimeError(f"Sync inspect schema is not sync-inspect-v1: {sync_inspect}")
    if sync_inspect.get("privacy", {}).get("plaintext_returned"):
        raise RuntimeError(f"Sync inspect returned plaintext: {sync_inspect}")
    sync_restore_preview = request(
        "/v1/sync/restore-preview",
        {
            "passphrase": "verify full api encrypted sync passphrase",
            "package": sync_export["package"],
        },
    )
    if sync_restore_preview.get("schema_version") != "sync-restore-preview-v1":
        raise RuntimeError(
            f"Sync restore preview schema is not sync-restore-preview-v1: {sync_restore_preview}"
        )
    if sync_restore_preview.get("restore_api_enabled") or sync_restore_preview.get("destructive_restore"):
        raise RuntimeError(f"Sync restore preview must remain non-destructive: {sync_restore_preview}")
    if sync_restore_preview.get("privacy", {}).get("plaintext_returned"):
        raise RuntimeError(f"Sync restore preview returned plaintext: {sync_restore_preview}")
    serialized_preview = json.dumps(sync_restore_preview, ensure_ascii=False)
    if (
        "smoke-user" in serialized_preview
        or "launch smoke test" in serialized_preview.lower()
        or "source evidence" in serialized_preview.lower()
        or session_id in serialized_preview
    ):
        raise RuntimeError(f"Sync restore preview leaked private smoke data: {sync_restore_preview}")
    pmf_summary = request("/v1/pmf/summary")
    print(
        json.dumps(
            {
                "status": "ok",
                "session_id": session_id,
                "stage": completed["stage"],
                "mastery": completed["mastery"],
                "agent_schema": agents["schema_version"],
                "commercial_readiness_schema": commercial_readiness["schema_version"],
                "agent_audit_status": agent_audit["status"],
                "agent_eval_schema": agent_eval_artifact["schema_version"],
                "plugins": len(plugins),
                "pmf_completed_sessions": metrics["sessions"]["completed"],
                "pmf_interest_total": pmf_summary["total"],
                "pmf_export_schema": export["schema_version"],
                "adoption_telemetry_schema": adoption_telemetry["schema_version"],
                "pmf_readiness_schema": pmf_readiness["schema_version"],
                "sync_package_schema": sync_export["package"]["schema_version"],
                "sync_session_count": sync_inspect["payload_summary"]["session_count"],
                "sync_restore_preview_schema": sync_restore_preview["schema_version"],
                "recovery_schema": recovery["schema_version"],
                "restore_api_enabled": recovery["restore_api_enabled"],
                "registry_verified_plugins": len(registry_verified_plugins),
                "plugin_registry_review_schema": registry_review["schema_version"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        report = failure_report(exc)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        print(format_failure_for_human(report), file=sys.stderr)
        sys.exit(1)
