"""Commercial readiness contract for the local-first alpha."""

from __future__ import annotations

from typing import Any


COMMERCIAL_READINESS_SCHEMA_VERSION = "commercial-readiness-v1"


def build_commercial_readiness(*, version: str) -> dict[str, Any]:
    """Return the machine-readable commercial readiness contract.

    The report is intentionally metadata-only. It describes what is ready for
    OSS/platform-agent distribution and what remains contract-only for future
    hosted convenience services.
    """

    local_core_invariants = [
        {
            "id": "no_account_required",
            "label": "No account required for local learning",
            "status": "pass",
            "required_for_oss_launch": True,
            "evidence": [
                "Skill Mode starts from local scripts.",
                "Docker Compose starts from local .env.",
                "The API creates sessions with hashed local user ids.",
            ],
        },
        {
            "id": "no_real_model_keys_stored",
            "label": "Real model credentials stay outside Study Anything",
            "status": "pass",
            "required_for_oss_launch": True,
            "evidence": [
                "Bring Your Own Agent uses HTTP endpoints and capabilities.",
                "Fake deterministic Agent covers tests and demos.",
                "Platform Agent or user-owned Agent owns model credentials.",
            ],
        },
        {
            "id": "local_data_ownership",
            "label": "Learning state remains user-owned and exportable",
            "status": "pass",
            "required_for_oss_launch": True,
            "evidence": [
                "Local session store is the source of truth.",
                "Encrypted sync package uses a user-supplied passphrase.",
                "Obsidian, NotebookLM-style, and archive handoffs are local exports.",
            ],
        },
        {
            "id": "hosted_services_do_not_block_core",
            "label": "Future hosted services do not gate the OSS workflow",
            "status": "pass",
            "required_for_oss_launch": True,
            "evidence": [
                "Hosted Sync/Publish/Teams are not required by release checks.",
                "Self-host and Skill Mode verifiers use local runtime only.",
                "PMF interest capture is opt-in and local by default.",
            ],
        },
        {
            "id": "platform_agent_distribution",
            "label": "Platform Agent adoption path is ready",
            "status": "pass",
            "required_for_oss_launch": True,
            "evidence": [
                "OpenAPI and OpenAI-compatible tool assets are generated.",
                "Kimi, Codex, and WorkBuddy packs are checked into the repo.",
                "External adoption verifier emits adoption-proof-v1.",
            ],
        },
    ]

    hosted_services = [
        {
            "service_id": "neural_sync",
            "label": "Neural Sync",
            "status": "contract_only",
            "commercial_stage": "post_pmf",
            "user_value": "Encrypted backup and multi-device learning-state sync.",
            "local_foundation": "sync-package-v1 local encrypted export and restore preview.",
            "must_not_block": ["self_host_launch", "skill_mode", "local_exports"],
            "required_before_sale": [
                "managed identity provisioning and account recovery",
                "OIDC signing-key rotation operations",
                "remote encrypted storage",
                "conflict resolution",
                "support runbooks",
                "security review",
            ],
        },
        {
            "service_id": "neural_publish",
            "label": "Neural Publish",
            "status": "contract_only",
            "commercial_stage": "post_pmf",
            "user_value": "Publish selected learning maps, reading trails, decks, or mastery reports.",
            "local_foundation": "learning-package-v1 and second-brain-handoff-v1 exports.",
            "must_not_block": ["obsidian_export", "learning_package_export", "local_archive"],
            "required_before_sale": [
                "publish consent workflow",
                "public/private sharing controls",
                "abuse and takedown process",
                "versioned published artifacts",
            ],
        },
        {
            "service_id": "neural_teams",
            "label": "Neural Teams",
            "status": "contract_only",
            "commercial_stage": "post_pmf",
            "user_value": "Shared courses, private team workspaces, admin controls, and export/audit.",
            "local_foundation": "workspace metadata, hashed members, and role capability names.",
            "must_not_block": ["personal_workspace", "local_session_creation"],
            "required_before_sale": [
                "database-enforced tenant isolation and migration tests",
                "tenant retention and deletion guarantees",
                "admin audit/export guarantees",
                "retention controls",
                "billing and support workflows",
                "enterprise security posture",
            ],
        },
        {
            "service_id": "catalyst",
            "label": "Catalyst",
            "status": "contract_only",
            "commercial_stage": "community_validation",
            "user_value": "One-time supporter tier for early builds, roadmap voting, and community signal.",
            "local_foundation": "local PMF interest capture and aggregate PMF export.",
            "must_not_block": ["free_core", "community_plugins", "source_distribution"],
            "required_before_sale": [
                "clear supporter promise",
                "refund and tax handling",
                "no feature lock-in to core workflow",
                "public roadmap process",
            ],
        },
    ]

    return {
        "schema_version": COMMERCIAL_READINESS_SCHEMA_VERSION,
        "version": version,
        "status": "architecture_ready_for_oss_platform_alpha",
        "launch_assessment": {
            "github_oss_launch": "ready",
            "platform_agent_distribution": "ready",
            "self_host_alpha": "ready",
            "standalone_app": "not_in_launch_path",
            "hosted_paid_services": "not_ready",
            "commercialization_strategy": (
                "Ship the OSS local-first learning layer first, collect adoption and PMF "
                "evidence, then sell optional hosted convenience services."
            ),
        },
        "local_core_invariants": local_core_invariants,
        "hosted_foundation": {
            "status": "application_layer_foundation",
            "authentication": "offline_oidc_jwt_with_static_jwks",
            "principal_binding": "issuer_tenant_subject",
            "authorization": [
                "tenant-filtered sessions",
                "workspace role permissions",
                "principal-scoped Agent providers",
                "cross-tenant resource hiding",
            ],
            "verifier": "python3 scripts/verify_hosted_identity_tenancy.py --check",
            "not_proven": [
                "managed IdP lifecycle or account recovery",
                "SCIM provisioning",
                "database row-level security",
                "separate tenant databases",
                "retention and deletion operations",
                "hosted infrastructure security",
                "independent external audit completion",
            ],
        },
        "security_audit": {
            "status": "ready_for_independent_audit",
            "audit_completed": False,
            "self_certification_allowed": False,
            "human_security_reviewer_required": True,
            "ai_only_review_sufficient": False,
            "signed_report_required": True,
            "pack": "platform/generated/study-anything-external-security-audit-pack.zip",
            "verifier": "python3 scripts/verify_external_security_audit_pack.py --check",
            "commercial_gate": (
                "Hosted paid production remains not_ready until an external auditor returns "
                "a signed report and all critical or high findings are closed and retested."
            ),
        },
        "hosted_service_contracts": hosted_services,
        "monetization_alignment": {
            "free_core": [
                "self-hosted learning workflow",
                "Skill Mode and HTTP API",
                "fake deterministic Agent",
                "user-owned HTTP Agent integration",
                "community plugins and local exports",
            ],
            "paid_services_sell": [
                "hosting convenience",
                "encrypted sync reliability",
                "team collaboration",
                "publishing convenience",
                "support and trust operations",
            ],
            "must_not_sell": [
                "lock-in to core learning workflow",
                "Study Anything-hosted model keys",
                "access to user-owned local data",
                "closed plugin distribution as a requirement",
            ],
            "obsidian_inspired": True,
            "business_model_reference_only": True,
        },
        "pmf_signals_required_before_hosted_services": [
            "weekly_active_learners",
            "completion_rate",
            "repeat_learning_rate",
            "mastery_delta_per_session",
            "plugin_installs",
            "hosted_waitlist_count",
            "platform_pack_successful_adoptions",
        ],
        "acceptance_evidence": {
            "required_schemas": [
                "deployment-guide-v1",
                "commercial-readiness-v1",
                "adoption-proof-v1",
                "agent-eval-policy-v1",
                "agent-eval-report-v1",
                "learning-package-v1",
                "second-brain-handoff-v1",
                "sync-package-v1",
                "hosted-identity-tenancy-verification-v1",
                "external-security-audit-pack-v1",
            ],
            "commands": [
                "python3 scripts/verify_commercial_readiness.py",
                "python3 scripts/verify_hosted_identity_tenancy.py --check",
                "python3 scripts/generate_external_security_audit_pack.py --check",
                "python3 scripts/verify_external_security_audit_pack.py --check",
                "python3 scripts/generate_platform_agent_assets.py --check",
                "python3 scripts/generate_platform_adoption_pack.py --check",
                "python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree",
                "python3 scripts/release_check.sh",
            ],
        },
        "privacy": {
            "real_model_keys_stored_by_study_anything": False,
            "hosted_account_required_for_local_core": False,
            "billing_required_for_local_core": False,
            "raw_source_text_in_readiness_report": False,
            "learner_answers_in_readiness_report": False,
            "agent_endpoints_in_readiness_report": False,
            "must_not_include": [
                "raw source text",
                "learner answers",
                "agent endpoints",
                "API keys",
                "model secrets",
                "billing credentials",
                "raw contacts",
            ],
        },
    }


def summarize_commercial_readiness(report: dict[str, Any]) -> dict[str, Any]:
    """Return a compact readiness summary for system status surfaces."""

    assessment = report.get("launch_assessment") or {}
    local_invariants = [
        item for item in report.get("local_core_invariants", []) if isinstance(item, dict)
    ]
    hosted_services = [
        item for item in report.get("hosted_service_contracts", []) if isinstance(item, dict)
    ]
    return {
        "schema_version": report.get("schema_version"),
        "status": report.get("status"),
        "github_oss_launch": assessment.get("github_oss_launch"),
        "platform_agent_distribution": assessment.get("platform_agent_distribution"),
        "hosted_paid_services": assessment.get("hosted_paid_services"),
        "standalone_app": assessment.get("standalone_app"),
        "local_invariants_passed": sum(1 for item in local_invariants if item.get("status") == "pass"),
        "local_invariant_count": len(local_invariants),
        "hosted_contract_count": len(hosted_services),
        "security_audit_status": (report.get("security_audit") or {}).get("status"),
        "security_audit_completed": (report.get("security_audit") or {}).get(
            "audit_completed"
        ),
    }
