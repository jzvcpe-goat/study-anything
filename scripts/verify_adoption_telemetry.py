#!/usr/bin/env python3
"""Verify adoption telemetry and PMF readiness privacy contracts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from localhost_diagnostics import (  # noqa: E402
    format_api_unreachable,
    redact_diagnostic,
    verifier_name_from_file,
)


MIN_PYTHON = (3, 11)


def runtime_failure_payload(
    *,
    classification: str,
    diagnostic: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "adoption-telemetry-error-v1",
        "status": "blocked",
        "classification": classification,
        "diagnostic": redact_diagnostic(diagnostic),
        "details": details or {},
        "next_steps": [
            ".venv/bin/python scripts/verify_adoption_telemetry.py",
            "python3 scripts/setup_env.py",
            "./scripts/run_skill_mode_demo.sh",
        ],
        "privacy": {
            "local_absolute_paths_included": False,
            "secrets_recorded": False,
        },
    }


def runtime_failure(
    message: str,
    *,
    classification: str = "python_dependency_missing",
    details: dict[str, Any] | None = None,
) -> None:
    print(
        json.dumps(
            runtime_failure_payload(
                classification=classification,
                diagnostic=message,
                details=details,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    sys.exit(1)


if sys.version_info < MIN_PYTHON:  # pragma: no cover - depends on local interpreter
    runtime_failure(
        "verify_adoption_telemetry requires Python 3.11 or newer.",
        classification="python_version_unsupported",
        details={"python_version": sys.version.split()[0]},
    )

try:
    from study_anything.core.pmf import build_adoption_telemetry, build_pmf_readiness  # noqa: E402
except ModuleNotFoundError as exc:  # pragma: no cover - depends on local interpreter
    runtime_failure(
        f"Python dependencies are missing for this interpreter ({exc.name}).",
        classification="python_dependency_missing",
        details={"missing_module": redact_diagnostic(exc.name or "required module")},
    )


SCHEMA_VERSION = "adoption-telemetry-verification-v1"
VERIFIER_NAME = verifier_name_from_file(__file__)
FORBIDDEN_VALUES = [
    "Private source text",
    "Private learner answer",
    "Private generated insight",
    "http://agent.example.test/secret-token",
    "sk-" + "proj-private",
    "MOONSHOT_API_KEY",
    "browser session transcript",
    "video slice transcript",
]


class AdoptionTelemetryError(RuntimeError):
    """Readable adoption telemetry verification failure."""


def format_cli_failure(exc: BaseException) -> str:
    diagnostic = redact_diagnostic(str(exc))
    return "\n".join(
        [
            f"{VERIFIER_NAME} failed.",
            f"Diagnostic: {diagnostic}",
            "Next steps:",
            "  1. Verify the local core without a running API:",
            "     python3 scripts/verify_adoption_telemetry.py",
            "  2. If you want API-backed telemetry, start Skill Mode and pass the API base:",
            "     ./scripts/launch_skill_mode.sh",
            "     API_BASE=http://127.0.0.1:8000 python3 scripts/verify_adoption_telemetry.py",
            "  3. If platform adoption evidence changed, refresh the generated pack:",
            "     python3 scripts/generate_platform_adoption_pack.py",
            "     python3 scripts/generate_platform_bundle_manifest.py",
        ]
    )


def fixture_metrics() -> dict[str, Any]:
    return {
        "schema_version": "pmf-v1",
        "sessions": {
            "total": 6,
            "completed": 4,
            "discarded": 1,
            "open_hitl": 0,
            "completion_rate": 0.6667,
            "private_source_text": "Private source text",
        },
        "learners": {
            "unique": 3,
            "active_7d": 2,
            "active_30d": 3,
            "repeat": 3,
            "repeat_rate": 1.0,
            "raw_user_id": "private-user-id",
        },
        "learning": {
            "answered_sessions": 4,
            "total_answers": 12,
            "average_mastery_delta": 0.55,
            "private_answer": "Private learner answer",
            "private_insight": "Private generated insight",
        },
        "plugins": {"ready": 2, "invalid": 0},
        "signals": {
            "weekly_active_learners": 2,
            "completion_rate": 0.6667,
            "repeat_learning_rate": 1.0,
            "plugin_installs": 2,
            "hosted_waitlist_count": 5,
        },
        "hosted_interest": {
            "total": 5,
            "with_contact": 3,
            "with_comment": 2,
            "services": {"neural_sync": 3, "neural_teams": 2},
            "sources": {"skill-mode": 4, "api": 1},
            "freeform_comment": "browser session transcript",
        },
    }


def fixture_adoption_proof() -> dict[str, Any]:
    return {
        "schema_version": "adoption-proof-v1",
        "status": "ok",
        "within_target_minutes": True,
        "source": {"mode": "copy_worktree", "repo": ".", "ref": None},
        "runtime": {
            "runtime": "skill-mode",
            "commands": {
                "platform_tools": {
                    "status": "ok",
                    "tool_count": 34,
                    "agent_endpoint": "http://agent.example.test/secret-token",
                },
                "operator_drill": {"status": "ok", "openapi_path_count": 29},
                "agent_eval_baseline": {"status": "ok"},
                "retrieval_eval_runner": {"status": "ok"},
                "platform_ecosystem": {"status": "ok"},
            },
            "diagnostics": {
                "status": "needs_attention",
                "warnings": [{"name": "ghcr_manifest", "stderr": "MOONSHOT_API_KEY"}],
                "blocking": [],
            },
        },
        "private_context": "video slice transcript",
    }


def request_json(api_base: str, path: str) -> dict[str, Any]:
    request = Request(f"{api_base.rstrip('/')}{path}", method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise AdoptionTelemetryError(f"API returned {exc.code} for {path}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AdoptionTelemetryError(
            format_api_unreachable(api_base.rstrip("/"), exc, verifier=VERIFIER_NAME)
        ) from exc
    except json.JSONDecodeError as exc:
        raise AdoptionTelemetryError(f"Cannot read {path} from {api_base}: {exc}") from exc


def assert_privacy(payload: dict[str, Any], *, label: str) -> None:
    privacy = payload.get("privacy")
    if not isinstance(privacy, dict):
        raise AdoptionTelemetryError(f"{label} is missing privacy contract.")
    required_false = [
        "source_text_included",
        "answers_included",
        "insights_included",
        "raw_user_ids_included",
        "agent_endpoints_included",
        "api_keys_included",
        "browser_video_app_context_included",
    ]
    for key in required_false:
        if privacy.get(key) is not False:
            raise AdoptionTelemetryError(f"{label} privacy.{key} must be false.")
    if privacy.get("aggregate_only") is not True:
        raise AdoptionTelemetryError(f"{label} must be aggregate-only.")
    if privacy.get("automatic_upload") is not False:
        raise AdoptionTelemetryError(f"{label} must not enable automatic upload.")
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    leaks = [value for value in FORBIDDEN_VALUES if value in serialized]
    if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{8,}", serialized):
        leaks.append("secret-looking sk token")
    if re.search(r"https?://[^\\s\"']*(?:token|secret|key)[^\\s\"']*", serialized, flags=re.I):
        leaks.append("secret-looking endpoint")
    if leaks:
        raise AdoptionTelemetryError(f"{label} leaked private values: {leaks}")


def verify_core() -> tuple[dict[str, Any], dict[str, Any]]:
    metrics = fixture_metrics()
    interest = dict(metrics["hosted_interest"])
    telemetry = build_adoption_telemetry(
        metrics,
        interest,
        adoption_proof=fixture_adoption_proof(),
    )
    readiness = build_pmf_readiness(telemetry)
    if telemetry.get("schema_version") != "adoption-telemetry-v1":
        raise AdoptionTelemetryError("Core telemetry schema drifted.")
    if readiness.get("schema_version") != "pmf-readiness-v1":
        raise AdoptionTelemetryError("Core readiness schema drifted.")
    if telemetry.get("adoption", {}).get("tool_import_success") is not True:
        raise AdoptionTelemetryError("Core telemetry did not recognize platform tool success.")
    if telemetry.get("quality", {}).get("agent_eval_passed") is not True:
        raise AdoptionTelemetryError("Core telemetry did not recognize Agent eval success.")
    assert_privacy(telemetry, label="core telemetry")
    assert_privacy(readiness, label="core readiness")
    return telemetry, readiness


def verify_api(api_base: str) -> tuple[dict[str, Any], dict[str, Any]]:
    telemetry = request_json(api_base, "/v1/adoption/telemetry")
    readiness = request_json(api_base, "/v1/pmf/readiness")
    if telemetry.get("schema_version") != "adoption-telemetry-v1":
        raise AdoptionTelemetryError(f"API telemetry schema drifted: {telemetry.get('schema_version')}")
    if readiness.get("schema_version") != "pmf-readiness-v1":
        raise AdoptionTelemetryError(f"API readiness schema drifted: {readiness.get('schema_version')}")
    assert_privacy(telemetry, label="API telemetry")
    assert_privacy(readiness, label="API readiness")
    return telemetry, readiness


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base",
        help="Optional API base. Defaults to API_BASE or STUDY_ANYTHING_API_BASE when either is set.",
    )
    args = parser.parse_args()
    api_base = args.api_base or os.environ.get("API_BASE") or os.environ.get("STUDY_ANYTHING_API_BASE")

    core_telemetry, core_readiness = verify_core()
    api_checked = False
    api_summary: dict[str, Any] | None = None
    if api_base:
        api_telemetry, api_readiness = verify_api(api_base)
        api_checked = True
        api_summary = {
            "telemetry_schema": api_telemetry.get("schema_version"),
            "readiness_schema": api_readiness.get("schema_version"),
            "sessions_total": api_telemetry.get("usage", {}).get("sessions_total"),
            "readiness_status": api_readiness.get("status"),
        }

    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "ok",
                "api_checked": api_checked,
                "core": {
                    "telemetry_schema": core_telemetry["schema_version"],
                    "readiness_schema": core_readiness["schema_version"],
                    "tool_import_success": core_telemetry["adoption"]["tool_import_success"],
                    "agent_eval_passed": core_telemetry["quality"]["agent_eval_passed"],
                    "privacy": {
                        "aggregate_only": core_telemetry["privacy"]["aggregate_only"],
                        "automatic_upload": core_telemetry["privacy"]["automatic_upload"],
                        "source_text_included": core_telemetry["privacy"]["source_text_included"],
                        "answers_included": core_telemetry["privacy"]["answers_included"],
                        "agent_endpoints_included": core_telemetry["privacy"]["agent_endpoints_included"],
                    },
                },
                "api": api_summary,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(format_cli_failure(exc), file=sys.stderr)
        sys.exit(1)
