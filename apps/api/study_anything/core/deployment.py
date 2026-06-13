"""Self-host deployment guidance for platform agents and first-run operators."""

from __future__ import annotations

from pathlib import Path
from typing import Any


DEPLOYMENT_GUIDE_SCHEMA_VERSION = "deployment-guide-v1"


def build_deployment_guide(project_root: Path, *, version: str) -> dict[str, Any]:
    """Return a redacted, copyable launch guide.

    This is intentionally static and metadata-only. It gives Kimi/Codex/WorkBuddy-style
    platform agents the same first-run commands that the human docs use, without exposing
    host secrets, absolute data paths, or provider credentials.
    """

    release_tag = f"v{version}" if not version.startswith("v") else version
    return {
        "schema_version": DEPLOYMENT_GUIDE_SCHEMA_VERSION,
        "status": "ready",
        "version": version,
        "no_frontend_required": True,
        "repository": {
            "name": "study-anything",
            "license": "Apache-2.0",
            "project_root_hint": project_root.name,
        },
        "entrypoints": [
            {
                "id": "skill_mode",
                "label": "Skill Mode / API-only",
                "best_for": "Kimi/Codex/WorkBuddy integration and local platform-agent workflows.",
                "commands": [
                    "python3 scripts/setup_env.py",
                    "./scripts/launch_skill_mode.sh",
                    "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_full_api_flow.py",
                ],
                "requires": ["python3"],
                "does_not_require": ["Docker", "frontend"],
            },
            {
                "id": "docker_source",
                "label": "Docker Compose from source",
                "best_for": "Developers who want to inspect and build the API image locally.",
                "commands": [
                    "python3 scripts/setup_env.py",
                    "./scripts/doctor.sh",
                    "./scripts/launch_self_host.sh",
                    "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_full_api_flow.py",
                ],
                "requires": ["Docker Desktop or Docker Engine", "Docker Compose plugin"],
                "does_not_require": ["frontend", "real model API keys"],
            },
            {
                "id": "published_image",
                "label": "Published GHCR image",
                "best_for": "Clean-clone users, non-ASCII checkout paths, and faster self-host startup.",
                "commands": [
                    "python3 scripts/setup_env.py",
                    f"USE_PUBLISHED_IMAGES=true STUDY_ANYTHING_IMAGE_TAG={release_tag} ./scripts/launch_self_host.sh",
                    f"python3 scripts/verify_published_image_launch.py --tag {release_tag} --pull-timeout-seconds 180 --allow-pull-timeout-report",
                ],
                "requires": ["Docker Desktop or Docker Engine", "network access to GHCR"],
                "does_not_require": ["local image build", "frontend", "real model API keys"],
            },
        ],
        "diagnostics": {
            "commands": [
                "./scripts/doctor.sh",
                "python3 scripts/diagnose_adoption.py",
                f"docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:{release_tag}",
                "docker compose --env-file .env -f infra/compose/docker-compose.yml ps",
            ],
            "failure_classes": [
                "docker_missing",
                "docker_daemon_unreachable",
                "compose_plugin_missing",
                "non_ascii_checkout_path",
                "port_in_use",
                "env_missing",
                "api_unreachable",
                "agent_endpoint_unreachable",
                "provider_defaults_missing",
                "ghcr_pull_timeout",
            ],
        },
        "platform_agent_contract": {
            "platform_agent_owns": [
                "browser access",
                "file access",
                "external data lookup",
                "video or application tooling",
                "real model credentials",
                "user-facing conversation",
            ],
            "study_anything_owns": [
                "source-bound learning workflow",
                "mastery state",
                "HITL state",
                "redacted audit and eval evidence",
                "second-brain handoff",
                "plugin metadata validation",
            ],
        },
        "privacy": {
            "real_model_keys_stored_by_study_anything": False,
            "must_not_log_or_share": [
                "raw source text",
                "learner answers",
                "agent endpoints with secrets",
                "API keys or model secrets",
                "platform-private browser or video context",
            ],
        },
    }
