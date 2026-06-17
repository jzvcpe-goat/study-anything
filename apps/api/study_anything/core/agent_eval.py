"""Redacted Agent eval artifacts for external evaluation tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


AGENT_EVAL_ARTIFACT_SCHEMA_VERSION = "agent-eval-artifact-v1"
AGENT_EVAL_POLICY_SCHEMA_VERSION = "agent-eval-policy-v1"
AGENT_EVAL_REPORT_SCHEMA_VERSION = "agent-eval-report-v1"
AGENT_EVAL_REQUIRED_TASKS = [
    "teach.overview",
    "teach.glossary",
    "quiz.generate",
    "answer.grade",
    "insight.synthesize",
]
AGENT_EVAL_FIXTURES = [
    "evals/fixtures/fake-agent-learning-loop.json",
    "evals/fixtures/mock-http-agent-learning-loop.json",
]


@dataclass(frozen=True)
class AgentEvalAdapter:
    adapter_id: str
    project: str
    repo: str
    license: str
    stars: int
    role: str
    first_use: str

    def public_dict(self) -> dict[str, object]:
        return {
            "adapter_id": self.adapter_id,
            "project": self.project,
            "repo": self.repo,
            "license": self.license,
            "github_stars_as_of": "2026-06-12",
            "stars": self.stars,
            "role": self.role,
            "first_use": self.first_use,
        }


AGENT_EVAL_ADAPTERS = [
    AgentEvalAdapter(
        adapter_id="promptfoo",
        project="Promptfoo",
        repo="https://github.com/promptfoo/promptfoo",
        license="MIT",
        stars=22200,
        role="CLI/CI regression, HTTP contract checks, red-team style assertions.",
        first_use="Run API/Skill smoke cases against local or published Study Anything endpoints.",
    ),
    AgentEvalAdapter(
        adapter_id="deepeval",
        project="DeepEval",
        repo="https://github.com/confident-ai/deepeval",
        license="Apache-2.0",
        stars=16100,
        role="Python agent-quality evals with task-completion and component-level metrics.",
        first_use="Score completed learning sessions after invocation coverage is proven.",
    ),
    AgentEvalAdapter(
        adapter_id="langchain-agentevals",
        project="LangChain AgentEvals",
        repo="https://github.com/langchain-ai/agentevals",
        license="MIT",
        stars=617,
        role="Trajectory matching for ordered Agent/tool steps.",
        first_use="Compare Study Anything workflow events with expected learning-node trajectories.",
    ),
    AgentEvalAdapter(
        adapter_id="ragas",
        project="Ragas",
        repo="https://github.com/explodinggradients/ragas",
        license="Apache-2.0",
        stars=14400,
        role="Citation, grounding, answer relevance, and retrieval-quality metrics.",
        first_use="Evaluate source-bound answers once enrichment/retrieval datasets are exported.",
    ),
]


def agent_eval_policy() -> dict[str, object]:
    """Return the public eval maturity policy for platform agents and CI.

    The policy is metadata only. It intentionally does not configure evaluator
    model credentials, judge providers, or external service secrets.
    """

    return {
        "schema_version": AGENT_EVAL_POLICY_SCHEMA_VERSION,
        "status": "ready",
        "purpose": (
            "Prove that Study Anything learning loops were handled by a configured "
            "Agent provider and that exported eval evidence is redacted, replayable, "
            "and compatible with mature external eval tools."
        ),
        "native_fast_gate": {
            "required_for_release": True,
            "blocking": True,
            "required_schemas": [
                AGENT_EVAL_ARTIFACT_SCHEMA_VERSION,
                "agent-quality-eval-v1",
                "study-anything-agent-eval-regression-report-v1",
            ],
            "required_tasks": list(AGENT_EVAL_REQUIRED_TASKS),
            "required_checks": [
                "agent invocation coverage",
                "source reference present",
                "excerpt hash present",
                "privacy redaction",
                "minimum teaching quality",
                "deterministic baseline regression",
            ],
            "commands": [
                "python3 scripts/verify_agent_eval_assets.py",
                "python3 scripts/verify_agent_eval_baseline.py --check",
                "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_agent_eval_flow.py",
            ],
        },
        "external_adapters": [
            {
                **adapter.public_dict(),
                "required_for_release": False,
                "missing_runtime_result": "skipped",
                "timeout_result": "skipped",
                "secrets_owned_by": "user_external_eval_environment",
            }
            for adapter in AGENT_EVAL_ADAPTERS
        ],
        "external_adapter_policy": {
            "promptfoo": {
                "mode": "contract_regression",
                "command": "python3 scripts/run_external_agent_evals.py --tool promptfoo --create-session",
                "blocking_only_when": "--required is passed by CI or release operator",
            },
            "deepeval": {
                "mode": "teaching_quality",
                "command": (
                    "python3 scripts/run_external_agent_evals.py --tool deepeval "
                    "--create-session --allow-native-quality-fallback"
                ),
                "blocking_only_when": "--required is passed and evaluator credentials are available",
            },
            "langchain-agentevals": {
                "mode": "trajectory_match",
                "dataset": "agent_eval_report.trajectory",
                "blocking_only_when": "external trajectory suite is explicitly enabled",
            },
            "ragas": {
                "mode": "retrieval_grounding",
                "command": (
                    "STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 "
                    "python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required"
                ),
                "blocking_only_when": "retrieval smoke profile is enabled",
            },
        },
        "failure_classes": failure_classifications(),
        "fixtures": [
            {
                "path": path,
                "privacy": "redacted",
                "purpose": "Stable fixture for platform-agent and external-eval adapter tests.",
            }
            for path in AGENT_EVAL_FIXTURES
        ],
        "privacy": privacy_contract(),
    }


def build_agent_eval_artifact(agent_audit: Mapping[str, Any]) -> dict[str, object]:
    """Build a tool-neutral, redacted eval artifact from an Agent audit report.

    The artifact is intentionally not an LLM judge. It is the stable bridge
    between Study Anything's internal invocation audit and mature external eval
    projects such as Promptfoo, DeepEval, LangChain AgentEvals, and Ragas.
    """

    evidence = [item for item in agent_audit.get("evidence", []) if isinstance(item, Mapping)]
    observed_tasks = _string_list(agent_audit.get("observed_tasks"))
    missing_tasks = _string_list(agent_audit.get("missing_tasks"))
    required_tasks = _string_list(agent_audit.get("required_tasks"))
    privacy = agent_audit.get("privacy", {})
    source_bound = agent_audit.get("source_bound", {})

    gates = [
        _gate(
            "agent_invocation_coverage",
            pass_when=agent_audit.get("status") == "verified" and not missing_tasks,
            required=True,
            summary="Required learning tasks were handled by a Study Anything Agent provider.",
        ),
        _gate(
            "source_reference_present",
            pass_when=_mapping_bool(source_bound, "source_reference_present"),
            required=True,
            summary="The learning session includes a source reference for grounding.",
        ),
        _gate(
            "excerpt_hash_present",
            pass_when=_mapping_bool(source_bound, "excerpt_hash_present"),
            required=True,
            summary="The learning session includes a source excerpt hash instead of raw source text.",
        ),
        _gate(
            "privacy_redaction",
            pass_when=_privacy_redaction_passed(privacy),
            required=True,
            summary="Audit and eval artifacts omit source text, answers, feedback, endpoints, and raw metadata.",
        ),
        _gate(
            "external_agent_used",
            pass_when=bool(agent_audit.get("used_external_agent")),
            required=False,
            summary="A user-owned Agent handled the session rather than the deterministic demo Agent.",
        ),
    ]

    required_gate_failed = any(gate["required"] and gate["status"] != "pass" for gate in gates)
    return {
        "schema_version": AGENT_EVAL_ARTIFACT_SCHEMA_VERSION,
        "policy_schema_version": AGENT_EVAL_POLICY_SCHEMA_VERSION,
        "report_schema_version": AGENT_EVAL_REPORT_SCHEMA_VERSION,
        "session_id": agent_audit.get("session_id"),
        "stage": agent_audit.get("stage"),
        "status": "ready_for_external_eval" if not required_gate_failed else "blocked",
        "source_schema": agent_audit.get("schema_version"),
        "invocation_audit_status": agent_audit.get("status"),
        "observed_tasks": observed_tasks,
        "required_tasks": required_tasks,
        "missing_tasks": missing_tasks,
        "used_external_agent": bool(agent_audit.get("used_external_agent")),
        "used_fake_agent": bool(agent_audit.get("used_fake_agent")),
        "native_gates": gates,
        "trajectory": _trajectory(evidence),
        "adapter_strategy": [adapter.public_dict() for adapter in AGENT_EVAL_ADAPTERS],
        "external_eval_layers": [
            "contract_regression",
            "agent_task_completion",
            "trajectory_match",
            "source_grounding",
            "citation_quality",
        ],
        "privacy": {
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_feedback_included": False,
            "agent_endpoints_included": False,
            "raw_agent_metadata_included": False,
        },
        "promptfoo": {
            "config": "evals/promptfoo/agent-eval-artifact.yaml",
            "recommended_gate": "all required native_gates pass and schema_version matches.",
        },
        "deepeval": {
            "recommended_metrics": ["TaskCompletionMetric", "GEval", "AnswerRelevancy", "Faithfulness"],
            "requires_judge_model": True,
        },
        "langchain_agentevals": {
            "recommended_evaluator": "create_trajectory_match_evaluator",
            "trajectory_source": "trajectory",
        },
        "ragas": {
            "recommended_metrics": ["faithfulness", "answer_relevancy", "context_relevance"],
            "requires_retrieval_or_enrichment_dataset": True,
        },
    }


def build_agent_eval_report(
    *,
    agent_audit: Mapping[str, Any],
    agent_eval_artifact: Mapping[str, Any],
    quality_eval: Mapping[str, Any] | None = None,
    retrieval_eval: Mapping[str, Any] | None = None,
    export_status: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Build a release-gate report from redacted eval evidence.

    This report is intentionally a maturity report, not an LLM judge. External
    tools may consume it as a dataset or attach richer judge-model metrics from
    the user's own environment.
    """

    quality_eval = quality_eval or {}
    export_status = export_status or {}
    dimensions = [
        _invocation_dimension(agent_audit, agent_eval_artifact),
        _trajectory_dimension(agent_eval_artifact),
        _quality_dimension(quality_eval),
        _retrieval_dimension(retrieval_eval),
        _export_dimension(export_status),
        _privacy_dimension(agent_eval_artifact, quality_eval, retrieval_eval, export_status),
        _adapter_readiness_dimension(agent_eval_artifact),
    ]
    required_failed = [
        item for item in dimensions if item["required"] and item["status"] not in {"pass", "skipped"}
    ]
    optional_needs_review = [
        item for item in dimensions if not item["required"] and item["status"] in {"needs_review", "not_evaluated"}
    ]
    native_status = "fail" if required_failed else "pass"
    report_status = (
        "fail"
        if required_failed
        else "pass_with_optional_external_evals"
        if optional_needs_review
        else "pass"
    )
    return {
        "schema_version": AGENT_EVAL_REPORT_SCHEMA_VERSION,
        "policy_schema_version": AGENT_EVAL_POLICY_SCHEMA_VERSION,
        "session_id": agent_eval_artifact.get("session_id"),
        "stage": agent_eval_artifact.get("stage"),
        "status": report_status,
        "native_fast_gate": {
            "status": native_status,
            "blocking": True,
            "required_dimensions": [
                item["dimension_id"] for item in dimensions if item["required"]
            ],
            "failed_dimensions": [item["dimension_id"] for item in required_failed],
            "external_frameworks_required": False,
        },
        "dimensions": dimensions,
        "adapter_readiness": [
            _adapter_readiness(adapter, agent_eval_artifact)
            for adapter in AGENT_EVAL_ADAPTERS
        ],
        "failure_classes": failure_classifications(),
        "external_eval": {
            "required_for_release": False,
            "promptfoo_ready": _has_adapter(agent_eval_artifact, "promptfoo"),
            "deepeval_ready": _has_adapter(agent_eval_artifact, "deepeval"),
            "langchain_agentevals_ready": _has_adapter(agent_eval_artifact, "langchain-agentevals"),
            "ragas_ready": _has_adapter(agent_eval_artifact, "ragas"),
            "runner": "scripts/run_external_agent_evals.py",
        },
        "privacy": privacy_contract(),
        "redaction": {
            "raw_source_text_included": False,
            "raw_answers_included": False,
            "raw_feedback_included": False,
            "generated_insights_included": False,
            "agent_endpoints_included": False,
            "raw_agent_metadata_included": False,
            "secrets_included": False,
        },
        "next_optional_commands": [
            "python3 scripts/run_external_agent_evals.py --tool promptfoo --create-session",
            "python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback",
            "STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required",
        ],
    }


def failure_classifications() -> list[dict[str, object]]:
    return [
        {
            "failure_class": "missing_runtime",
            "status_when_optional": "skipped",
            "status_when_required": "failed",
            "examples": ["npx unavailable", "deepeval package unavailable"],
        },
        {
            "failure_class": "missing_evaluator_credentials",
            "status_when_optional": "skipped",
            "status_when_required": "failed",
            "examples": ["judge model API key missing from user-owned eval environment"],
        },
        {
            "failure_class": "timeout",
            "status_when_optional": "skipped",
            "status_when_required": "failed",
            "examples": ["external eval process exceeded timeout"],
        },
        {
            "failure_class": "schema_mismatch",
            "status_when_optional": "failed",
            "status_when_required": "failed",
            "examples": ["unexpected eval artifact schema"],
        },
        {
            "failure_class": "native_gate_failed",
            "status_when_optional": "failed",
            "status_when_required": "failed",
            "examples": ["missing required Agent task", "missing excerpt hash"],
        },
        {
            "failure_class": "privacy_leak",
            "status_when_optional": "failed",
            "status_when_required": "failed",
            "examples": ["raw source text, answer, endpoint, metadata, or secret appears in eval evidence"],
        },
    ]


def privacy_contract() -> dict[str, object]:
    return {
        "real_model_keys_stored_by_study_anything": False,
        "agent_endpoints_returned": False,
        "raw_source_text_returned": False,
        "learner_answers_returned": False,
        "grading_feedback_returned": False,
        "generated_insights_returned": False,
        "raw_agent_metadata_returned": False,
        "secrets_returned": False,
    }


def _gate(gate_id: str, *, pass_when: bool, required: bool, summary: str) -> dict[str, object]:
    return {
        "gate_id": gate_id,
        "status": "pass" if pass_when else "fail",
        "required": required,
        "summary": summary,
    }


def _dimension(
    dimension_id: str,
    *,
    status: str,
    required: bool,
    score: float | None,
    evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "dimension_id": dimension_id,
        "status": status,
        "required": required,
        "score": score,
        "evidence": dict(evidence or {}),
    }


def _invocation_dimension(
    audit: Mapping[str, Any],
    artifact: Mapping[str, Any],
) -> dict[str, object]:
    failed_required = _failed_required_native_gates(artifact)
    pass_when = audit.get("status") == "verified" and not failed_required
    return _dimension(
        "agent_invocation_coverage",
        status="pass" if pass_when else "fail",
        required=True,
        score=1.0 if pass_when else 0.0,
        evidence={
            "audit_status": audit.get("status"),
            "artifact_status": artifact.get("status"),
            "observed_tasks": _string_list(artifact.get("observed_tasks")),
            "missing_tasks": _string_list(artifact.get("missing_tasks")),
            "failed_required_gates": [gate.get("gate_id") for gate in failed_required],
            "used_external_agent": bool(artifact.get("used_external_agent")),
            "used_fake_agent": bool(artifact.get("used_fake_agent")),
        },
    )


def _trajectory_dimension(artifact: Mapping[str, Any]) -> dict[str, object]:
    trajectory = [item for item in artifact.get("trajectory", []) if isinstance(item, Mapping)]
    tasks = [str(item.get("task_type")) for item in trajectory if item.get("task_type")]
    pass_when = all(task in tasks for task in AGENT_EVAL_REQUIRED_TASKS)
    return _dimension(
        "trajectory_coverage",
        status="pass" if pass_when else "fail",
        required=True,
        score=1.0 if pass_when else 0.0,
        evidence={
            "required_tasks": list(AGENT_EVAL_REQUIRED_TASKS),
            "trajectory_tasks": tasks,
            "trajectory_steps": len(trajectory),
        },
    )


def _quality_dimension(quality_eval: Mapping[str, Any]) -> dict[str, object]:
    status = str(quality_eval.get("status") or "not_evaluated")
    pass_when = quality_eval.get("schema_version") == "agent-quality-eval-v1" and status == "pass"
    return _dimension(
        "teaching_quality",
        status="pass" if pass_when else "needs_review",
        required=True,
        score=_float_or_none(quality_eval.get("quality_score")) if pass_when else 0.0,
        evidence={
            "schema_version": quality_eval.get("schema_version"),
            "quality_status": status,
            "threshold": quality_eval.get("threshold"),
            "gate_ids": [
                gate.get("gate_id")
                for gate in quality_eval.get("gates", [])
                if isinstance(gate, Mapping)
            ],
        },
    )


def _retrieval_dimension(retrieval_eval: Mapping[str, Any] | None) -> dict[str, object]:
    if not retrieval_eval:
        return _dimension(
            "retrieval_grounding",
            status="not_evaluated",
            required=False,
            score=None,
            evidence={
                "reason": "Retrieval/Ragas-compatible gate is optional unless the retrieval smoke profile is enabled.",
                "expected_schema": "retrieval-quality-eval-v1",
            },
        )
    status = str(retrieval_eval.get("status") or "needs_review")
    pass_when = retrieval_eval.get("schema_version") == "retrieval-quality-eval-v1" and status == "pass"
    return _dimension(
        "retrieval_grounding",
        status="pass" if pass_when else "needs_review",
        required=False,
        score=_float_or_none(retrieval_eval.get("quality_score")),
        evidence={
            "schema_version": retrieval_eval.get("schema_version"),
            "retrieval_status": status,
            "threshold": retrieval_eval.get("threshold"),
            "privacy": retrieval_eval.get("privacy"),
        },
    )


def _export_dimension(export_status: Mapping[str, Any]) -> dict[str, object]:
    checks = {
        "obsidian_ready": bool(export_status.get("obsidian_ready")),
        "learning_package_ready": bool(export_status.get("learning_package_ready")),
        "second_brain_ready": bool(export_status.get("second_brain_ready")),
    }
    pass_when = all(checks.values())
    return _dimension(
        "export_readiness",
        status="pass" if pass_when else "needs_review",
        required=False,
        score=1.0 if pass_when else 0.0,
        evidence=checks,
    )


def _privacy_dimension(
    artifact: Mapping[str, Any],
    quality_eval: Mapping[str, Any],
    retrieval_eval: Mapping[str, Any] | None,
    export_status: Mapping[str, Any],
) -> dict[str, object]:
    privacy_values = [
        artifact.get("privacy"),
        quality_eval.get("privacy"),
        (retrieval_eval or {}).get("privacy") if retrieval_eval else None,
        export_status.get("privacy"),
    ]
    pass_when = all(_privacy_report_passed(value) for value in privacy_values if value is not None)
    return _dimension(
        "privacy_redaction",
        status="pass" if pass_when else "fail",
        required=True,
        score=1.0 if pass_when else 0.0,
        evidence=privacy_contract(),
    )


def _adapter_readiness_dimension(artifact: Mapping[str, Any]) -> dict[str, object]:
    adapter_ids = {
        str(item.get("adapter_id"))
        for item in artifact.get("adapter_strategy", [])
        if isinstance(item, Mapping)
    }
    missing = sorted({adapter.adapter_id for adapter in AGENT_EVAL_ADAPTERS} - adapter_ids)
    return _dimension(
        "external_adapter_readiness",
        status="pass" if not missing else "needs_review",
        required=False,
        score=1.0 if not missing else 0.5,
        evidence={
            "adapter_ids": sorted(adapter_ids),
            "missing_adapters": missing,
            "external_frameworks_required": False,
            "fixtures": list(AGENT_EVAL_FIXTURES),
        },
    )


def _adapter_readiness(
    adapter: AgentEvalAdapter,
    artifact: Mapping[str, Any],
) -> dict[str, object]:
    ready = _has_adapter(artifact, adapter.adapter_id)
    return {
        **adapter.public_dict(),
        "status": "ready" if ready else "missing_from_artifact",
        "required_for_release": False,
        "skip_is_failure": False,
        "failure_class_when_unavailable": "missing_runtime",
    }


def _trajectory(evidence: list[Mapping[str, Any]]) -> list[dict[str, object]]:
    trajectory: list[dict[str, object]] = []
    for index, item in enumerate(evidence, start=1):
        trajectory.append(
            {
                "step": index,
                "node": item.get("node"),
                "task_type": item.get("task_type"),
                "provider_id": item.get("provider_id"),
                "provider_kind": item.get("provider_kind"),
                "status": item.get("status"),
                "latency_ms": item.get("latency_ms"),
                "confidence": item.get("confidence"),
            }
        )
    return trajectory


def _privacy_redaction_passed(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    forbidden_flags = [
        "source_text_returned",
        "answers_returned",
        "feedback_returned",
        "agent_endpoint_returned",
        "raw_agent_metadata_returned",
    ]
    return not any(value.get(flag) for flag in forbidden_flags)


def _privacy_report_passed(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    forbidden_flags = [
        "raw_source_text_included",
        "raw_answers_included",
        "raw_feedback_included",
        "learner_answers_included",
        "grading_feedback_included",
        "generated_insights_included",
        "agent_endpoints_included",
        "raw_agent_metadata_included",
        "agent_metadata_included",
        "secrets_included",
        "agent_secrets_allowed",
        "full_source_text_returned",
        "result_snippets_included",
    ]
    return not any(bool(value.get(flag)) for flag in forbidden_flags)


def _failed_required_native_gates(artifact: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        gate
        for gate in artifact.get("native_gates", [])
        if isinstance(gate, Mapping) and gate.get("required") and gate.get("status") != "pass"
    ]


def _has_adapter(artifact: Mapping[str, Any], adapter_id: str) -> bool:
    return any(
        item.get("adapter_id") == adapter_id
        for item in artifact.get("adapter_strategy", [])
        if isinstance(item, Mapping)
    )


def _float_or_none(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _mapping_bool(value: object, key: str) -> bool:
    return bool(value.get(key)) if isinstance(value, Mapping) else False


def _string_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []
