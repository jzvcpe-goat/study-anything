#!/usr/bin/env python3
"""Verify the platform-agent tool manifest against a running Study Anything API."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from localhost_diagnostics import format_api_unreachable, resolve_api_base, verifier_name_from_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "platform" / "study-anything-platform-tools.json"
PACKS_DIR = ROOT / "platform" / "packs"
API_BASE = resolve_api_base()
VERIFIER_NAME = verifier_name_from_file(__file__)
REQUIRED_TOOLS = {
    "study_anything_deployment_guide",
    "study_anything_commercial_readiness",
    "study_anything_adoption_telemetry",
    "study_anything_pmf_readiness",
    "study_anything_health",
    "study_anything_eval_policy",
    "study_anything_create_session",
    "study_anything_add_reading",
    "study_anything_validate_context_package",
    "study_anything_create_session_from_context_package",
    "study_anything_append_context_package",
    "study_anything_plugin_sdk",
    "study_anything_plugin_capabilities",
    "study_anything_validate_plugin_package",
    "study_anything_run_importer",
    "study_anything_retrieval_status",
    "study_anything_retrieval_rebuild",
    "study_anything_retrieval_search",
    "study_anything_retrieval_quality_eval",
    "study_anything_create_session_from_retrieval",
    "study_anything_append_retrieval_context",
    "study_anything_add_enrichment",
    "study_anything_teaching_layers",
    "study_anything_run",
    "study_anything_answer",
    "study_anything_mastery",
    "study_anything_agent_audit",
    "study_anything_agent_eval_artifact",
    "study_anything_agent_quality_eval",
    "study_anything_agent_eval_report",
    "study_anything_obsidian_export",
    "study_anything_enrichment_artifact_export",
    "study_anything_learning_package_export",
    "study_anything_second_brain_handoff_export",
}
REQUIRED_ADAPTERS = {"promptfoo", "deepeval", "langchain-agentevals", "ragas"}
REQUIRED_TRAJECTORY = ["quiz.generate", "answer.grade", "insight.synthesize"]
REQUIRED_PLATFORM_PACKS = {"codex", "kimi", "workbuddy"}
NOTEBOOKLM_FIXTURE = ROOT / "fixtures" / "notebooklm" / "notebooklm-style-context-package.json"
PRIVATE_SOURCE_TEXT = "Private platform tool smoke source text must stay out of audit artifacts."
PRIVATE_ENRICHMENT_TEXT = "Private enrichment web and video context must stay out of redacted evidence."
PRIVATE_ANSWER = "Private platform tool smoke answer."
PRIVATE_TITLE = "Private Platform Tool Smoke"
PRIVATE_USER = "platform-tools-smoke-user"
PRIVATE_CONTEXT_USER = "platform-context-tools-smoke-user"
BANNED_TOOL_PATH_FRAGMENTS = (
    "/v1/agents/providers",
    "/v1/agents/defaults",
    "/v1/models/",
    "/v1/plugins/install",
    "/v1/sync/export",
    "/v1/sync/inspect",
    "/v1/sync/restore-preview",
    "/v1/pmf/export",
)


class VerificationError(RuntimeError):
    """Readable verification failure."""


FORBIDDEN_LITERALS = (
    PRIVATE_SOURCE_TEXT,
    PRIVATE_ENRICHMENT_TEXT,
    PRIVATE_ANSWER,
    PRIVATE_TITLE,
    PRIVATE_USER,
    PRIVATE_CONTEXT_USER,
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
        PRIVATE_ENRICHMENT_TEXT: "<private-enrichment-text>",
        PRIVATE_ANSWER: "<private-answer>",
        PRIVATE_TITLE: "<private-title>",
        PRIVATE_USER: "<private-user>",
        PRIVATE_CONTEXT_USER: "<private-user>",
    }
    for literal, replacement in replacements.items():
        text = text.replace(literal, replacement)
    text = re.sub(r"(?i)private platform tool smoke source text[^\"'\n.]*\.?", "<private-source-text>", text)
    text = re.sub(r"(?i)private enrichment web and video context[^\"'\n.]*\.?", "<private-enrichment-text>", text)
    text = re.sub(r"(?i)private platform tool smoke answer[^\"'\n.]*\.?", "<private-answer>", text)
    text = re.sub(r"(?i)private fixture [^:]{1,80} excerpt:[^\"'\n.]*\.?", "<private-fixture-text>", text)
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
    if "cannot read platform manifest" in lowered or "platform manifest" in lowered:
        return "manifest_invalid"
    if "missing platform ecosystem packs" in lowered:
        return "platform_pack_missing"
    if "commercial readiness" in lowered or "pmf readiness" in lowered or "adoption telemetry" in lowered:
        return "commercial_boundary_failed"
    if "plugin" in lowered and ("invalid schema" in lowered or "validation" in lowered or "capabilities" in lowered):
        return "plugin_contract_failed"
    if "context package" in lowered or "importer" in lowered:
        return "context_package_failed"
    if "retrieval" in lowered:
        return "retrieval_contract_failed"
    if "teaching layers" in lowered:
        return "teaching_layer_failed"
    if "did not produce a quiz" in lowered or "did not complete the learning loop" in lowered:
        return "learning_flow_incomplete"
    if "agent audit" in lowered:
        return "agent_audit_failed"
    if "eval" in lowered or "quality" in lowered:
        return "agent_eval_failed"
    if "obsidian" in lowered or "learning package" in lowered or "second-brain" in lowered or "enrichment artifact" in lowered:
        return "export_contract_failed"
    if "leaked" in lowered or "privacy" in lowered:
        return "privacy_leak"
    return "platform_agent_tools_failed"


def failure_next_steps(classification: str) -> list[str]:
    common = [
        "./scripts/launch_skill_mode.sh",
        f"API_BASE={API_BASE} python3 scripts/verify_platform_agent_tools.py",
        "python3 scripts/diagnose_adoption.py",
    ]
    matrix = {
        "localhost_socket_blocked": [
            "Run the verifier from a normal terminal or host shell that permits localhost sockets.",
            "If this came from Codex or another sandboxed Agent, collect this blocked report and rerun outside the sandbox.",
        ],
        "api_unreachable": [
            "Start the Study Anything API first with `./scripts/launch_skill_mode.sh`.",
            "If the API is already running on another port, pass it with `API_BASE=http://127.0.0.1:<port>`.",
        ],
        "manifest_invalid": [
            "Regenerate platform Agent assets and confirm `platform/study-anything-platform-tools.json` is present.",
            "Run `python3 scripts/generate_platform_agent_assets.py --check` before this verifier.",
        ],
        "platform_pack_missing": [
            "Restore platform packs under `platform/packs/{codex,kimi,workbuddy}`.",
            "Regenerate the platform adoption pack after restoring pack metadata.",
        ],
        "commercial_boundary_failed": [
            "Check hosted paid services remain contract-only and local core does not require billing.",
            "Do not publish platform evidence until commercial/privacy boundaries are green.",
        ],
        "plugin_contract_failed": [
            "Run plugin SDK/capability/package validation checks separately.",
            "Confirm plugin validation remains metadata-only and does not execute or copy plugin packages.",
        ],
        "context_package_failed": [
            "Validate the NotebookLM-style Learning Context Package independently.",
            "Run `python3 scripts/verify_importer_lesson_flow.py` first to isolate importer/context issues.",
        ],
        "retrieval_contract_failed": [
            "Check `/v1/retrieval/status`; use `STUDY_ANYTHING_RETRIEVAL_BACKEND=memory` for local Skill Mode when retrieval evidence is required.",
            "Rerun retrieval rebuild/eval on the failing session locally.",
        ],
        "teaching_layer_failed": [
            "Confirm the configured Agent supports `teach.overview` and `teach.glossary`.",
            "Retry with the bundled fake agent path before validating a custom Agent.",
        ],
        "learning_flow_incomplete": [
            "Check session events locally for the first failed workflow stage.",
            "Rerun the simpler `verify_platform_lesson_flow.py` before this full tool-manifest verifier.",
        ],
        "agent_audit_failed": [
            "Inspect `/v1/sessions/<session_id>/agent-audit` locally for observed task coverage.",
            "Do not publish raw source, enrichment, or answers while debugging.",
        ],
        "agent_eval_failed": [
            "Run `python3 scripts/verify_agent_eval_flow.py` first to isolate eval failures.",
            "Required native eval gates must pass before release evidence is valid.",
        ],
        "export_contract_failed": [
            "Check Obsidian, enrichment artifact, learning package, and second-brain exports locally.",
            "Do not publish export evidence until privacy flags and schemas are correct.",
        ],
        "privacy_leak": [
            "Do not share the raw transcript publicly.",
            "Fix the leaking API response, eval artifact, or export before using this run as evidence.",
        ],
    }
    return matrix.get(classification, ["Rerun after starting the local API."]) + common


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
            "manifest": sanitize_text(str(DEFAULT_MANIFEST.relative_to(ROOT))),
        },
        "privacy": {
            "raw_source_text_included": False,
            "raw_enrichment_text_included": False,
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
            f"classification: {sanitize_text(str(report.get('classification') or 'platform_agent_tools_failed'))}",
            f"Diagnostic: {sanitize_text(str(report.get('diagnostic') or '')) or '(empty)'}",
            "Next steps:",
            *(steps or ["- Regenerate platform Agent assets, then rerun this verifier."]),
        ]
    )


def assert_failure_report_redacted(report: dict[str, Any]) -> None:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in serialized]
    if re.search(r"(?i)private (?:platform|enrichment|fixture)[^\"']+", serialized):
        leaks.append("private smoke text")
    if re.search(r"/Users/[^\s\"']+", serialized):
        leaks.append("local absolute path")
    if re.search(r"/private/(?:var/)?folders/[^\s\"']+", serialized):
        leaks.append("local temp path")
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{12,}", serialized):
        leaks.append("secret-looking sk token")
    if leaks:
        raise VerificationError(f"Platform Agent tools verifier failure report leaked private data: {leaks}")


def load_manifest(path: Path = DEFAULT_MANIFEST) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise VerificationError(f"Cannot read platform manifest at {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise VerificationError(f"Platform manifest is not valid JSON: {exc}") from exc


def validate_manifest(manifest: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if manifest.get("schema_version") != "study-anything-platform-tools-v1":
        raise VerificationError(f"Unexpected manifest schema_version: {manifest.get('schema_version')}")
    tools = manifest.get("tools")
    if not isinstance(tools, list) or not tools:
        raise VerificationError("Platform manifest must include a non-empty tools list.")

    by_name: Dict[str, Dict[str, Any]] = {}
    for tool in tools:
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            raise VerificationError(f"Tool has invalid name: {tool}")
        if name in by_name:
            raise VerificationError(f"Duplicate tool name in platform manifest: {name}")
        method = tool.get("method")
        if method not in {"GET", "POST"}:
            raise VerificationError(f"{name} has unsupported method: {method}")
        path_template = tool.get("path_template")
        if not isinstance(path_template, str) or not path_template.startswith("/v1/"):
            raise VerificationError(f"{name} has invalid path_template: {path_template}")
        banned = [fragment for fragment in BANNED_TOOL_PATH_FRAGMENTS if fragment in path_template]
        if banned:
            raise VerificationError(f"{name} exposes high-risk management endpoint(s): {banned}")
        input_schema = tool.get("input_schema")
        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            raise VerificationError(f"{name} must declare an object input_schema.")
        by_name[name] = tool

    missing = REQUIRED_TOOLS - set(by_name)
    if missing:
        raise VerificationError(f"Platform manifest is missing required tools: {sorted(missing)}")

    evidence = manifest.get("acceptance_evidence") or {}
    command = evidence.get("local_verification_command", "")
    if "verify_platform_agent_tools.py" not in command:
        raise VerificationError("Manifest acceptance evidence must point to verify_platform_agent_tools.py.")
    missing_packs = [
        pack_id
        for pack_id in sorted(REQUIRED_PLATFORM_PACKS)
        if not (PACKS_DIR / pack_id / "pack.json").exists()
    ]
    if missing_packs:
        raise VerificationError(f"Missing platform ecosystem packs: {missing_packs}")
    return by_name


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
        raise VerificationError(f"API returned {exc.code} for {path}: {detail}") from exc
    except (URLError, OSError) as exc:
        raise VerificationError(
            format_api_unreachable(API_BASE, exc, verifier=VERIFIER_NAME)
        ) from exc


def path_for(tool: Dict[str, Any], **params: str) -> str:
    path = str(tool["path_template"])
    for key, value in params.items():
        path = path.replace("{" + key + "}", quote(value, safe=""))
    if "{" in path or "}" in path:
        raise VerificationError(f"Unresolved path parameter in {tool['name']}: {path}")
    return path


def call_tool(
    tools: Dict[str, Dict[str, Any]],
    name: str,
    payload: Optional[Dict[str, Any]] = None,
    **path_params: str,
) -> Any:
    tool = tools[name]
    path = path_for(tool, **path_params)
    if tool["method"] == "GET":
        return request(path)
    return request(path, payload or {})


def assert_contains_all(actual: Iterable[str], expected: Iterable[str], label: str) -> None:
    missing = set(expected) - set(actual)
    if missing:
        raise VerificationError(f"{label} missing required values: {sorted(missing)}")


def main() -> None:
    manifest = load_manifest()
    tools = validate_manifest(manifest)

    health = call_tool(tools, "study_anything_health")
    if health.get("status") != "ok":
        raise VerificationError(f"Health tool did not return ok: {health}")

    deployment = call_tool(tools, "study_anything_deployment_guide")
    if deployment.get("schema_version") != "deployment-guide-v1":
        raise VerificationError(f"Deployment guide returned invalid schema: {deployment}")
    if deployment.get("no_frontend_required") is not True:
        raise VerificationError(f"Deployment guide must not require the standalone frontend: {deployment}")
    entrypoint_ids = [
        str(item.get("id"))
        for item in deployment.get("entrypoints", [])
        if isinstance(item, dict)
    ]
    assert_contains_all(
        entrypoint_ids,
        ["skill_mode", "docker_source", "published_image"],
        "Deployment guide entrypoints",
    )
    if (deployment.get("privacy") or {}).get("real_model_keys_stored_by_study_anything") is not False:
        raise VerificationError(f"Deployment guide must not store model keys: {deployment}")

    commercial = call_tool(tools, "study_anything_commercial_readiness")
    if commercial.get("schema_version") != "commercial-readiness-v1":
        raise VerificationError(f"Commercial readiness returned invalid schema: {commercial}")
    if commercial.get("status") != "architecture_ready_for_oss_platform_alpha":
        raise VerificationError(f"Commercial readiness returned invalid status: {commercial}")
    assessment = commercial.get("launch_assessment") or {}
    if assessment.get("github_oss_launch") != "ready":
        raise VerificationError(f"GitHub OSS launch should be ready: {commercial}")
    if assessment.get("platform_agent_distribution") != "ready":
        raise VerificationError(f"Platform Agent distribution should be ready: {commercial}")
    if assessment.get("hosted_paid_services") != "not_ready":
        raise VerificationError(f"Hosted paid services must remain not ready: {commercial}")
    invariant_failures = [
        item
        for item in commercial.get("local_core_invariants", [])
        if isinstance(item, dict) and item.get("status") != "pass"
    ]
    if invariant_failures:
        raise VerificationError(f"Commercial readiness local invariants failed: {invariant_failures}")
    hosted_statuses = {
        item.get("service_id"): item.get("status")
        for item in commercial.get("hosted_service_contracts", [])
        if isinstance(item, dict)
    }
    if hosted_statuses != {
        "neural_sync": "contract_only",
        "neural_publish": "contract_only",
        "neural_teams": "contract_only",
        "catalyst": "contract_only",
    }:
        raise VerificationError(f"Hosted service contracts are unsafe: {commercial}")
    commercial_privacy = commercial.get("privacy") or {}
    if commercial_privacy.get("real_model_keys_stored_by_study_anything") is not False:
        raise VerificationError(f"Commercial readiness must not store model keys: {commercial}")
    if commercial_privacy.get("billing_required_for_local_core") is not False:
        raise VerificationError(f"Commercial readiness must not require billing locally: {commercial}")

    adoption_telemetry = call_tool(tools, "study_anything_adoption_telemetry")
    if adoption_telemetry.get("schema_version") != "adoption-telemetry-v1":
        raise VerificationError(f"Adoption telemetry returned invalid schema: {adoption_telemetry}")
    telemetry_privacy = adoption_telemetry.get("privacy") or {}
    if telemetry_privacy.get("aggregate_only") is not True:
        raise VerificationError(f"Adoption telemetry must be aggregate-only: {adoption_telemetry}")
    for key in (
        "source_text_included",
        "answers_included",
        "insights_included",
        "raw_user_ids_included",
        "agent_endpoints_included",
        "api_keys_included",
        "browser_video_app_context_included",
    ):
        if telemetry_privacy.get(key) is not False:
            raise VerificationError(f"Adoption telemetry privacy.{key} must be false.")
    if (adoption_telemetry.get("collection") or {}).get("automatic_upload") is not False:
        raise VerificationError(f"Adoption telemetry must not auto-upload: {adoption_telemetry}")

    pmf_readiness = call_tool(tools, "study_anything_pmf_readiness")
    if pmf_readiness.get("schema_version") != "pmf-readiness-v1":
        raise VerificationError(f"PMF readiness returned invalid schema: {pmf_readiness}")
    boundary = pmf_readiness.get("commercial_boundary") or {}
    if boundary.get("sell_standalone_app_now") is not False:
        raise VerificationError(f"PMF readiness must not recommend selling standalone app: {pmf_readiness}")
    if boundary.get("hosted_paid_services_status") != "not_ready":
        raise VerificationError(f"Hosted paid services must remain not_ready: {pmf_readiness}")

    eval_policy = call_tool(tools, "study_anything_eval_policy")
    if eval_policy.get("schema_version") != "agent-eval-policy-v1":
        raise VerificationError(f"Eval policy returned invalid schema: {eval_policy}")
    policy_adapter_ids = {
        item.get("adapter_id")
        for item in eval_policy.get("external_adapters", [])
        if isinstance(item, dict)
    }
    if policy_adapter_ids != REQUIRED_ADAPTERS:
        raise VerificationError(f"Eval policy adapter strategy mismatch: {sorted(policy_adapter_ids)}")
    if (eval_policy.get("native_fast_gate") or {}).get("required_for_release") is not True:
        raise VerificationError(f"Eval policy native gate must be release-blocking: {eval_policy}")
    if (eval_policy.get("privacy") or {}).get("real_model_keys_stored_by_study_anything") is not False:
        raise VerificationError(f"Eval policy must not store model keys: {eval_policy}")

    plugin_sdk = call_tool(tools, "study_anything_plugin_sdk")
    if plugin_sdk.get("schema_version") != "plugin-sdk-v1":
        raise VerificationError(f"Plugin SDK tool returned invalid schema: {plugin_sdk}")
    if plugin_sdk.get("entrypoints_executed") is not False:
        raise VerificationError(f"Plugin SDK tool must be metadata-only: {plugin_sdk}")
    hook_names = {
        item.get("hook")
        for item in plugin_sdk.get("supported_hooks", [])
        if isinstance(item, dict)
    }
    assert_contains_all(
        [str(name) for name in hook_names if name],
        ["importer", "enrichment", "exporter", "agent_tool", "agent_panel"],
        "Plugin SDK hooks",
    )

    plugin_capabilities = call_tool(tools, "study_anything_plugin_capabilities")
    if plugin_capabilities.get("schema_version") != "plugin-capability-index-v1":
        raise VerificationError(
            f"Plugin capabilities tool returned invalid schema: {plugin_capabilities}"
        )
    if (plugin_capabilities.get("privacy") or {}).get("entrypoints_executed") is not False:
        raise VerificationError(
            f"Plugin capabilities tool must not execute entrypoints: {plugin_capabilities}"
        )
    plugin_items = {
        item.get("plugin_id"): item
        for item in plugin_capabilities.get("items", [])
        if isinstance(item, dict)
    }
    assert_contains_all(
        [str(plugin_id) for plugin_id in plugin_items if plugin_id],
        ["example-note-importer", "example-enrichment-importer", "example-exporter"],
        "Plugin capabilities",
    )
    if "export.second_brain_handoff" not in plugin_items["example-exporter"].get("capabilities", []):
        raise VerificationError(f"Second-brain exporter capability missing: {plugin_items['example-exporter']}")

    plugin_validation = call_tool(
        tools,
        "study_anything_validate_plugin_package",
        {"source_path": "example-exporter"},
    )
    if plugin_validation.get("schema_version") != "plugin-package-validation-v1":
        raise VerificationError(f"Plugin package validation returned invalid schema: {plugin_validation}")
    if plugin_validation.get("status") != "valid":
        raise VerificationError(f"Plugin package validation failed: {plugin_validation}")
    if plugin_validation.get("execution_allowed_by_validation") is not False:
        raise VerificationError(
            f"Plugin package validation should not execute plugins: {plugin_validation}"
        )
    if (plugin_validation.get("privacy") or {}).get("package_copied") is not False:
        raise VerificationError(f"Plugin package validation copied files: {plugin_validation}")

    context_fixture = json.loads(NOTEBOOKLM_FIXTURE.read_text(encoding="utf-8"))
    context_private_fragments = [
        str(item.get("text") or "")
        for item in context_fixture.get("items", [])
        if isinstance(item, dict)
    ]
    context_validation = call_tool(
        tools,
        "study_anything_validate_context_package",
        {"package": context_fixture},
    )
    if context_validation.get("schema_version") != "learning-context-package-v1":
        raise VerificationError(f"Context package validation returned invalid schema: {context_validation}")
    if context_validation.get("status") != "valid":
        raise VerificationError(f"Context package validation failed: {context_validation}")
    if any(fragment in json.dumps(context_validation, ensure_ascii=False) for fragment in context_private_fragments):
        raise VerificationError("Context package validation leaked raw fixture text.")
    context_created = call_tool(
        tools,
        "study_anything_create_session_from_context_package",
        {
            "user_id": PRIVATE_CONTEXT_USER,
            "use_demo_agent": True,
            "package": context_fixture,
        },
    )
    if context_created.get("status") != "session_created":
        raise VerificationError(f"Context package session creation failed: {context_created}")
    context_session = context_created.get("session") or {}
    context_session_id = context_session.get("session_id")
    if not isinstance(context_session_id, str) or not context_session_id:
        raise VerificationError(f"Context package creation did not return a session id: {context_created}")
    context_source_types = {
        item.get("source_type")
        for item in context_session.get("enrichment_items", [])
        if isinstance(item, dict)
    }
    assert_contains_all(
        context_source_types,
        ["web", "document", "video_slice", "app_context", "markdown_note", "obsidian_note"],
        "context package imported source types",
    )
    context_appended = call_tool(
        tools,
        "study_anything_append_context_package",
        {"package": context_fixture},
        session_id=context_session_id,
    )
    if context_appended.get("status") != "session_expanded":
        raise VerificationError(f"Context package append failed: {context_appended}")

    importer = call_tool(
        tools,
        "study_anything_run_importer",
        {
            "inputs": {
                "note_reference": "obsidian://Platform Tools/Importer Smoke",
                "title": "Importer Smoke",
                "markdown_excerpt": "Importer runtime should produce a validated learning context package.",
            },
            "confirmed_permissions": ["write:context"],
            "include_text": True,
        },
        plugin_id="example-note-importer",
    )
    if importer.get("schema_version") != "importer-run-v1":
        raise VerificationError(f"Importer tool returned invalid schema: {importer}")
    if (importer.get("package") or {}).get("schema_version") != "learning-context-package-v1":
        raise VerificationError(f"Importer tool did not return a Learning Context Package: {importer}")
    if "Importer runtime should produce" in json.dumps(importer.get("redacted_package"), ensure_ascii=False):
        raise VerificationError("Importer redacted_package leaked raw importer text.")

    retrieval_status = call_tool(tools, "study_anything_retrieval_status")
    if retrieval_status.get("status") not in {"disabled", "healthy", "unavailable"}:
        raise VerificationError(f"Retrieval status returned invalid state: {retrieval_status}")
    if retrieval_status.get("status") == "healthy":
        rebuilt = call_tool(
            tools,
            "study_anything_retrieval_rebuild",
            {},
            session_id=context_session_id,
        )
        if rebuilt.get("status") != "rebuilt":
            raise VerificationError(f"Retrieval rebuild failed: {rebuilt}")
        searched = call_tool(
            tools,
            "study_anything_retrieval_search",
            {"query": "learning context package", "limit": 2},
            session_id=context_session_id,
        )
        if searched.get("schema_version") != "retrieval-search-v1":
            raise VerificationError(f"Retrieval search returned invalid schema: {searched}")
        retrieval_quality = call_tool(
            tools,
            "study_anything_retrieval_quality_eval",
            {"query": "learning context package", "limit": 2},
            session_id=context_session_id,
        )
        if retrieval_quality.get("schema_version") != "retrieval-quality-eval-v1":
            raise VerificationError(
                f"Retrieval quality eval returned invalid schema: {retrieval_quality}"
            )
        if retrieval_quality.get("status") != "pass":
            raise VerificationError(
                f"Retrieval quality eval did not pass: {retrieval_quality}"
            )
        if (retrieval_quality.get("privacy") or {}).get("result_snippets_included"):
            raise VerificationError(
                f"Retrieval quality eval returned snippet-bearing evidence: {retrieval_quality}"
            )

    session = call_tool(
        tools,
        "study_anything_create_session",
        {
            "user_id": PRIVATE_USER,
            "track": "ACADEMIC",
            "use_demo_agent": True,
        },
    )
    session_id = session.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise VerificationError(f"Create session tool did not return a session_id: {session}")

    reading = call_tool(
        tools,
        "study_anything_add_reading",
        {
            "source_type": "local_text",
            "reference": "demo://platform-tools-smoke",
            "title": PRIVATE_TITLE,
            "text": PRIVATE_SOURCE_TEXT,
        },
        session_id=session_id,
    )
    source = reading.get("source") or {}
    if not source.get("excerpt_hash"):
        raise VerificationError(f"Reading tool did not persist an excerpt hash: {reading}")

    enrichment = call_tool(
        tools,
        "study_anything_add_enrichment",
        {
            "title": "Platform Tool Enrichment Bundle",
            "items": [
                {
                    "source_type": "web",
                    "reference": "https://example.test/platform-enrichment",
                    "title": "Private Enrichment Web",
                    "locator": "section=platform-smoke",
                    "text": PRIVATE_ENRICHMENT_TEXT,
                    "provenance": {
                        "collector": "platform-agent-tool-smoke",
                        "capture_method": "browser_excerpt",
                        "source_owner": "user",
                    },
                    "redaction_policy": "reference_only",
                },
                {
                    "source_type": "video_slice",
                    "reference": "video://platform-smoke/clip",
                    "title": "Private Enrichment Clip",
                    "locator": "00:00:08-00:00:21",
                    "text": PRIVATE_ENRICHMENT_TEXT,
                    "provenance": {
                        "collector": "platform-agent-tool-smoke",
                        "capture_method": "video_transcript_slice",
                        "source_owner": "user",
                    },
                    "redaction_policy": "reference_only",
                },
            ],
        },
        session_id=session_id,
    )
    if enrichment.get("schema_version") != "learning-enrichment-v1":
        raise VerificationError(f"Enrichment tool returned invalid schema: {enrichment}")
    if PRIVATE_ENRICHMENT_TEXT in json.dumps(enrichment, ensure_ascii=False):
        raise VerificationError("Enrichment tool response leaked raw enrichment text.")
    if not (enrichment.get("source") or {}).get("excerpt_hash"):
        raise VerificationError(f"Enrichment tool did not return a source excerpt hash: {enrichment}")

    teaching = call_tool(
        tools,
        "study_anything_teaching_layers",
        {
            "layers": ["overview", "glossary"],
            "language": "zh",
            "level": "beginner",
        },
        session_id=session_id,
    )
    if teaching.get("schema_version") != "teaching-layers-v1":
        raise VerificationError(f"Teaching layers tool returned invalid schema: {teaching}")
    teaching_layers = teaching.get("layers") or []
    layer_names = {item.get("layer") for item in teaching_layers if isinstance(item, dict)}
    if not {"overview", "glossary"}.issubset(layer_names):
        raise VerificationError(f"Teaching layers tool did not return requested layers: {teaching}")
    teaching_tasks = [
        item.get("agent", {}).get("task_type")
        for item in teaching_layers
        if isinstance(item, dict) and isinstance(item.get("agent"), dict)
    ]
    assert_contains_all(teaching_tasks, ["teach.overview", "teach.glossary"], "teaching layers")

    running = call_tool(tools, "study_anything_run", {}, session_id=session_id)
    quiz_items = running.get("quiz_items") or []
    if not quiz_items:
        raise VerificationError(f"Run tool did not produce a quiz item: {running}")
    quiz_id = quiz_items[0].get("item_id")
    if not quiz_id:
        raise VerificationError(f"Quiz item did not include item_id: {quiz_items[0]}")

    completed = call_tool(
        tools,
        "study_anything_answer",
        {"answers": {quiz_id: PRIVATE_ANSWER}},
        session_id=session_id,
    )
    if completed.get("stage") != "completed":
        raise VerificationError(f"Answer tool did not complete the learning loop: {completed}")

    mastery = call_tool(tools, "study_anything_mastery", session_id=session_id)
    if not isinstance(mastery.get("level"), (int, float)) or not mastery.get("bloom"):
        raise VerificationError(f"Mastery tool returned invalid mastery state: {mastery}")

    audit = call_tool(tools, "study_anything_agent_audit", session_id=session_id)
    if audit.get("schema_version") != "agent-audit-v1" or audit.get("status") != "verified":
        raise VerificationError(f"Agent audit tool did not return verified audit evidence: {audit}")
    assert_contains_all(audit.get("observed_tasks", []), REQUIRED_TRAJECTORY, "agent audit")

    artifact = call_tool(tools, "study_anything_agent_eval_artifact", session_id=session_id)
    if artifact.get("schema_version") != "agent-eval-artifact-v1":
        raise VerificationError(f"Unexpected eval artifact schema: {artifact}")
    if artifact.get("status") != "ready_for_external_eval":
        raise VerificationError(f"Eval artifact is not ready for external eval: {artifact}")
    failed_required_gates = [
        gate
        for gate in artifact.get("native_gates", [])
        if gate.get("required") and gate.get("status") != "pass"
    ]
    if failed_required_gates:
        raise VerificationError(f"Required native eval gates failed: {failed_required_gates}")
    adapter_ids = {adapter.get("adapter_id") for adapter in artifact.get("adapter_strategy", [])}
    if adapter_ids != REQUIRED_ADAPTERS:
        raise VerificationError(f"Eval adapter strategy mismatch: {sorted(adapter_ids)}")
    trajectory = [step.get("task_type") for step in artifact.get("trajectory", [])]
    assert_contains_all(trajectory, REQUIRED_TRAJECTORY, "eval artifact trajectory")

    quality = call_tool(tools, "study_anything_agent_quality_eval", session_id=session_id)
    if quality.get("schema_version") != "agent-quality-eval-v1":
        raise VerificationError(f"Unexpected quality eval schema: {quality}")
    if quality.get("status") != "pass":
        raise VerificationError(f"Quality eval did not pass minimum teaching gates: {quality}")
    quality_gate_ids = {gate.get("gate_id") for gate in quality.get("gates", [])}
    expected_quality_gates = {
        "overview_quality",
        "glossary_quality",
        "quiz_quality",
        "grading_quality",
        "synthesis_quality",
    }
    assert_contains_all(quality_gate_ids, expected_quality_gates, "quality eval gates")

    eval_report = call_tool(tools, "study_anything_agent_eval_report", session_id=session_id)
    if eval_report.get("schema_version") != "agent-eval-report-v1":
        raise VerificationError(f"Unexpected Agent eval report schema: {eval_report}")
    if eval_report.get("policy_schema_version") != "agent-eval-policy-v1":
        raise VerificationError(f"Agent eval report policy schema mismatch: {eval_report}")
    if (eval_report.get("native_fast_gate") or {}).get("status") != "pass":
        raise VerificationError(f"Agent eval native fast gate did not pass: {eval_report}")
    dimensions = {
        item.get("dimension_id"): item
        for item in eval_report.get("dimensions", [])
        if isinstance(item, dict)
    }
    assert_contains_all(
        [str(name) for name in dimensions if name],
        [
            "agent_invocation_coverage",
            "trajectory_coverage",
            "teaching_quality",
            "retrieval_grounding",
            "export_readiness",
            "privacy_redaction",
            "external_adapter_readiness",
        ],
        "Agent eval report dimensions",
    )
    report_adapter_ids = {
        item.get("adapter_id")
        for item in eval_report.get("adapter_readiness", [])
        if isinstance(item, dict)
    }
    if report_adapter_ids != REQUIRED_ADAPTERS:
        raise VerificationError(f"Agent eval report adapter readiness mismatch: {eval_report}")

    obsidian = call_tool(tools, "study_anything_obsidian_export", session_id=session_id)
    if obsidian.get("schema_version") != "obsidian-markdown-export-v1":
        raise VerificationError(f"Unexpected Obsidian export schema: {obsidian}")
    markdown = str(obsidian.get("markdown") or "")
    for heading in ["## Source", "## Quiz Review", "## Mastery", "## Enrichment Context"]:
        if heading not in markdown:
            raise VerificationError(f"Obsidian export missing heading {heading}: {markdown}")
    if PRIVATE_SOURCE_TEXT in markdown or PRIVATE_ENRICHMENT_TEXT in markdown:
        raise VerificationError("Obsidian export leaked raw source/enrichment text.")

    enrichment_artifact = call_tool(
        tools,
        "study_anything_enrichment_artifact_export",
        session_id=session_id,
    )
    if enrichment_artifact.get("schema_version") != "learning-enrichment-artifact-v1":
        raise VerificationError(f"Unexpected enrichment artifact schema: {enrichment_artifact}")
    if enrichment_artifact.get("format") != "markdown+html":
        raise VerificationError(f"Unexpected enrichment artifact format: {enrichment_artifact}")
    if "learning-enrichment-artifact-v1" not in str(enrichment_artifact.get("html") or ""):
        raise VerificationError(f"Enrichment artifact HTML missing schema marker: {enrichment_artifact}")
    if PRIVATE_SOURCE_TEXT in json.dumps(enrichment_artifact, ensure_ascii=False):
        raise VerificationError("Enrichment artifact leaked raw source text.")
    if PRIVATE_ENRICHMENT_TEXT in json.dumps(enrichment_artifact, ensure_ascii=False):
        raise VerificationError("Enrichment artifact leaked raw enrichment text.")

    package = call_tool(tools, "study_anything_learning_package_export", session_id=session_id)
    if package.get("schema_version") != "learning-package-v1":
        raise VerificationError(f"Unexpected learning package schema: {package}")
    consumers = set(str(item) for item in package.get("intended_consumers", []))
    assert_contains_all(consumers, ["platform_agent", "notebooklm_bridge", "obsidian_pipeline"], "learning package consumers")
    package_privacy = package.get("privacy") or {}
    if package_privacy.get("raw_source_text_included") or package_privacy.get("raw_enrichment_text_included"):
        raise VerificationError(f"Learning package privacy flags are unsafe: {package_privacy}")
    if PRIVATE_SOURCE_TEXT in json.dumps(package, ensure_ascii=False):
        raise VerificationError("Learning package leaked raw source text.")
    if PRIVATE_ENRICHMENT_TEXT in json.dumps(package, ensure_ascii=False):
        raise VerificationError("Learning package leaked raw enrichment text.")

    second_brain = call_tool(
        tools,
        "study_anything_second_brain_handoff_export",
        session_id=session_id,
    )
    if second_brain.get("schema_version") != "second-brain-handoff-v1":
        raise VerificationError(f"Unexpected second-brain handoff schema: {second_brain}")
    second_brain_privacy = second_brain.get("privacy") or {}
    forbidden_second_brain_flags = [
        "raw_source_text_included",
        "raw_enrichment_text_included",
        "learner_answers_included",
        "grading_feedback_included",
        "agent_metadata_included",
        "secrets_included",
    ]
    if any(second_brain_privacy.get(flag) for flag in forbidden_second_brain_flags):
        raise VerificationError(f"Second-brain privacy flags are unsafe: {second_brain_privacy}")
    archive_manifest = ((second_brain.get("local_archive") or {}).get("manifest") or {})
    if archive_manifest.get("schema_version") != "second-brain-archive-manifest-v1":
        raise VerificationError(f"Second-brain archive manifest is invalid: {second_brain}")
    obsidian_note = second_brain.get("obsidian") or {}
    if obsidian_note.get("schema_version") != "second-brain-obsidian-note-v1":
        raise VerificationError(f"Second-brain Obsidian note is invalid: {second_brain}")
    if PRIVATE_ANSWER in json.dumps(second_brain, ensure_ascii=False):
        raise VerificationError("Second-brain handoff leaked learner answer.")
    if PRIVATE_SOURCE_TEXT in json.dumps(second_brain, ensure_ascii=False):
        raise VerificationError("Second-brain handoff leaked raw source text.")
    if PRIVATE_ENRICHMENT_TEXT in json.dumps(second_brain, ensure_ascii=False):
        raise VerificationError("Second-brain handoff leaked raw enrichment text.")

    serialized_evidence = json.dumps(
        {
            "audit": audit,
            "artifact": artifact,
            "quality": quality,
            "eval_report": eval_report,
            "adoption_telemetry": adoption_telemetry,
            "pmf_readiness": pmf_readiness,
            "second_brain": second_brain,
        },
        ensure_ascii=False,
    )
    forbidden_fragments = [
        PRIVATE_SOURCE_TEXT,
        PRIVATE_ENRICHMENT_TEXT,
        PRIVATE_ANSWER,
        PRIVATE_TITLE,
        PRIVATE_USER,
        "127.0.0.1:8787",
        "OPENAI_API_KEY",
        "MOONSHOT_API_KEY",
    ]
    leaks = [fragment for fragment in forbidden_fragments if fragment in serialized_evidence]
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9]{16,}", serialized_evidence):
        leaks.append("secret-looking sk token")
    if leaks:
        raise VerificationError(f"Platform evidence leaked private data: {leaks}")

    print(
        json.dumps(
            {
                "status": "ok",
                "manifest_schema": manifest["schema_version"],
                "tool_count": len(tools),
                "api_base": API_BASE,
                "session_id": session_id,
                "agent_audit_status": audit["status"],
                "commercial_readiness_schema": commercial["schema_version"],
                "adoption_telemetry_schema": adoption_telemetry["schema_version"],
                "pmf_readiness_schema": pmf_readiness["schema_version"],
                "eval_schema": artifact["schema_version"],
                "quality_schema": quality["schema_version"],
                "eval_policy_schema": eval_policy["schema_version"],
                "eval_report_schema": eval_report["schema_version"],
                "obsidian_schema": obsidian["schema_version"],
                "enrichment_artifact_schema": enrichment_artifact["schema_version"],
                "learning_package_schema": package["schema_version"],
                "second_brain_schema": second_brain["schema_version"],
                "plugin_sdk_schema": plugin_sdk["schema_version"],
                "plugin_capability_index_schema": plugin_capabilities["schema_version"],
                "plugin_package_validation_schema": plugin_validation["schema_version"],
                "adapter_ids": sorted(adapter_ids),
                "trajectory_tasks": trajectory,
                "teaching_tasks": teaching_tasks,
            },
            ensure_ascii=False,
            sort_keys=True,
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
