#!/usr/bin/env python3
"""Verify the commercial-readiness contract and platform exposure."""

from __future__ import annotations

import argparse
import json
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
        "schema_version": "commercial-readiness-error-v1",
        "status": "blocked",
        "classification": classification,
        "diagnostic": redact_diagnostic(diagnostic),
        "details": details or {},
        "next_steps": [
            ".venv/bin/python scripts/verify_commercial_readiness.py",
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
        "verify_commercial_readiness requires Python 3.11 or newer.",
        classification="python_version_unsupported",
        details={"python_version": sys.version.split()[0]},
    )

try:
    from study_anything import __version__  # noqa: E402
    from study_anything.core.commercial_readiness import (  # noqa: E402
        COMMERCIAL_READINESS_SCHEMA_VERSION,
        build_commercial_readiness,
    )
except ModuleNotFoundError as exc:  # pragma: no cover - depends on local interpreter
    runtime_failure(
        f"Python dependencies are missing for this interpreter ({exc.name}).",
        classification="python_dependency_missing",
        details={"missing_module": redact_diagnostic(exc.name or "required module")},
    )


PLATFORM_MANIFEST = ROOT / "platform" / "study-anything-platform-tools.json"
GENERATED_OPENAPI = ROOT / "platform" / "generated" / "study-anything-platform-openapi.json"
GENERATED_TOOLS = ROOT / "platform" / "generated" / "study-anything-openai-tools.json"
REQUIRED_TOOL = "study_anything_commercial_readiness"
FORBIDDEN_MARKERS = ("sk-", "api_key", "secret_key", "bearer ")
VERIFIER_NAME = verifier_name_from_file(__file__)


class CommercialReadinessError(RuntimeError):
    """Readable commercial-readiness verification failure."""


def format_cli_failure(exc: BaseException) -> str:
    diagnostic = redact_diagnostic(str(exc))
    return "\n".join(
        [
            f"{VERIFIER_NAME} failed.",
            f"Diagnostic: {diagnostic}",
            "Next steps:",
            "  1. Regenerate platform agent assets when tool contracts changed:",
            "     python3 scripts/generate_platform_agent_assets.py",
            "  2. Rebuild adoption/bundle evidence if generated assets changed:",
            "     python3 scripts/generate_platform_adoption_pack.py",
            "     python3 scripts/generate_platform_bundle_manifest.py",
            "  3. Re-run the commercial readiness verifier:",
            "     python3 scripts/verify_commercial_readiness.py",
            "     API_BASE=http://127.0.0.1:8000 python3 scripts/verify_commercial_readiness.py",
        ]
    )


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CommercialReadinessError(f"Cannot read JSON {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise CommercialReadinessError(f"{path.relative_to(ROOT)} must contain a JSON object.")
    return value


def fetch_report(api_base: str) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/v1/commercial/readiness"
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            value = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise CommercialReadinessError(f"API returned {exc.code} for {url}: {detail}") from exc
    except (URLError, OSError) as exc:
        raise CommercialReadinessError(
            format_api_unreachable(api_base.rstrip("/"), exc, verifier=VERIFIER_NAME)
        ) from exc
    if not isinstance(value, dict):
        raise CommercialReadinessError("Commercial readiness API did not return a JSON object.")
    return value


def assert_no_forbidden_markers(payload: dict[str, Any]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    leaked = [marker for marker in FORBIDDEN_MARKERS if marker in serialized]
    if leaked:
        raise CommercialReadinessError(f"Commercial readiness report contains forbidden marker(s): {leaked}")


def validate_report(report: dict[str, Any]) -> None:
    if report.get("schema_version") != COMMERCIAL_READINESS_SCHEMA_VERSION:
        raise CommercialReadinessError(f"Unexpected schema_version: {report.get('schema_version')}")
    if report.get("version") != __version__:
        raise CommercialReadinessError(
            f"Report version {report.get('version')} does not match package version {__version__}."
        )
    if report.get("status") != "architecture_ready_for_oss_platform_alpha":
        raise CommercialReadinessError(f"Unexpected readiness status: {report.get('status')}")

    assessment = report.get("launch_assessment") or {}
    expected_assessment = {
        "github_oss_launch": "ready",
        "platform_agent_distribution": "ready",
        "self_host_alpha": "ready",
        "standalone_app": "not_in_launch_path",
        "hosted_paid_services": "not_ready",
    }
    for key, expected in expected_assessment.items():
        if assessment.get(key) != expected:
            raise CommercialReadinessError(
                f"launch_assessment.{key} expected {expected!r}, got {assessment.get(key)!r}."
            )

    invariants = report.get("local_core_invariants")
    if not isinstance(invariants, list) or len(invariants) < 5:
        raise CommercialReadinessError("Commercial readiness must include local core invariants.")
    for item in invariants:
        if not isinstance(item, dict):
            raise CommercialReadinessError(f"Invalid invariant item: {item}")
        if item.get("required_for_oss_launch") is not True:
            raise CommercialReadinessError(f"Invariant is not release-required: {item}")
        if item.get("status") != "pass":
            raise CommercialReadinessError(f"Local core invariant did not pass: {item}")

    services = report.get("hosted_service_contracts")
    if not isinstance(services, list) or len(services) < 4:
        raise CommercialReadinessError("Commercial readiness must include hosted service contracts.")
    service_ids = {item.get("service_id") for item in services if isinstance(item, dict)}
    required_ids = {"neural_sync", "neural_publish", "neural_teams", "catalyst"}
    if service_ids != required_ids:
        raise CommercialReadinessError(f"Hosted service ids mismatch: {sorted(service_ids)}")
    for service in services:
        if not isinstance(service, dict):
            raise CommercialReadinessError(f"Invalid hosted service contract: {service}")
        if service.get("status") != "contract_only":
            raise CommercialReadinessError(f"Hosted service must stay contract-only in v0.3.0: {service}")
        if not service.get("required_before_sale"):
            raise CommercialReadinessError(f"Hosted service lacks required_before_sale: {service}")

    monetization = report.get("monetization_alignment") or {}
    if monetization.get("obsidian_inspired") is not True:
        raise CommercialReadinessError(f"Commercial model should be Obsidian-inspired: {monetization}")
    if "Study Anything-hosted model keys" not in monetization.get("must_not_sell", []):
        raise CommercialReadinessError("Commercial model must not sell hosted model-key custody.")

    privacy = report.get("privacy") or {}
    forbidden_true_flags = [
        "real_model_keys_stored_by_study_anything",
        "hosted_account_required_for_local_core",
        "billing_required_for_local_core",
        "raw_source_text_in_readiness_report",
        "learner_answers_in_readiness_report",
        "agent_endpoints_in_readiness_report",
    ]
    bad_flags = [name for name in forbidden_true_flags if privacy.get(name)]
    if bad_flags:
        raise CommercialReadinessError(f"Unsafe privacy flags are true: {bad_flags}")

    acceptance = report.get("acceptance_evidence") or {}
    schemas = set(acceptance.get("required_schemas") or [])
    for schema in [
        "commercial-readiness-v1",
        "deployment-guide-v1",
        "adoption-proof-v1",
        "agent-eval-report-v1",
    ]:
        if schema not in schemas:
            raise CommercialReadinessError(f"Acceptance evidence missing schema {schema}.")
    commands = "\n".join(str(command) for command in acceptance.get("commands") or [])
    if "verify_commercial_readiness.py" not in commands:
        raise CommercialReadinessError("Acceptance evidence must include verify_commercial_readiness.py.")

    assert_no_forbidden_markers(report)


def validate_platform_tooling() -> None:
    manifest = read_json(PLATFORM_MANIFEST)
    tools = {tool.get("name"): tool for tool in manifest.get("tools", []) if isinstance(tool, dict)}
    if REQUIRED_TOOL not in tools:
        raise CommercialReadinessError(f"Platform manifest missing {REQUIRED_TOOL}.")
    tool = tools[REQUIRED_TOOL]
    if tool.get("method") != "GET" or tool.get("path_template") != "/v1/commercial/readiness":
        raise CommercialReadinessError(f"Commercial readiness tool has wrong HTTP contract: {tool}")
    if "commercial-readiness-v1" not in tool.get("output_requirements", []):
        raise CommercialReadinessError(f"Commercial readiness tool must require schema output: {tool}")
    if (tool.get("privacy") or {}).get("returns_private_learning_data") is not False:
        raise CommercialReadinessError(f"Commercial readiness tool privacy is unsafe: {tool}")

    openapi = read_json(GENERATED_OPENAPI)
    operation = (openapi.get("paths") or {}).get("/v1/commercial/readiness", {}).get("get")
    if not isinstance(operation, dict) or operation.get("operationId") != REQUIRED_TOOL:
        raise CommercialReadinessError("Generated OpenAPI asset is missing commercial readiness operation.")

    openai_tools = json.loads(GENERATED_TOOLS.read_text(encoding="utf-8"))
    if not isinstance(openai_tools, list):
        raise CommercialReadinessError("Generated OpenAI tools asset must contain a list.")
    generated_names = {
        item.get("function", {}).get("name")
        for item in openai_tools
        if isinstance(item, dict)
    }
    if REQUIRED_TOOL not in generated_names:
        raise CommercialReadinessError("Generated OpenAI tools asset is missing commercial readiness tool.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base",
        help="Optional running API base URL. When omitted, verifies the local core contract.",
    )
    args = parser.parse_args()

    report = fetch_report(args.api_base) if args.api_base else build_commercial_readiness(version=__version__)
    validate_report(report)
    validate_platform_tooling()
    print(
        json.dumps(
            {
                "schema_version": "commercial-readiness-verification-v1",
                "status": "pass",
                "readiness_schema": report["schema_version"],
                "readiness_status": report["status"],
                "hosted_paid_services": report["launch_assessment"]["hosted_paid_services"],
                "tool": REQUIRED_TOOL,
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
