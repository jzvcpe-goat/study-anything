#!/usr/bin/env python3
"""Verify typed allowlisted Agentic tools cannot become a trust root."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from study_anything.cbb.agentic.fixtures import (  # noqa: E402
    build_agentic_evolution_cases,
)
from study_anything.cbb.agentic.tools import default_tool_registry  # noqa: E402
from study_anything.cbb.protocol.models import (  # noqa: E402
    AgenticPlanV1,
    AgenticToolResultV1,
)


REPORT_SCHEMA_VERSION = "cbb-agentic-tool-boundary-verification-v1"
DEFAULT_REPORT = (
    ROOT / "platform" / "generated" / "study-anything-cbb-agentic-tool-boundary.json"
)


def _rejected(fn: Callable[[], object], expected: str) -> bool:
    try:
        fn()
    except ValueError as exc:
        return expected in str(exc)
    return False


def _forbidden_imports() -> list[str]:
    findings: list[str] = []
    forbidden = ("requests", "httpx", "subprocess", "openai", "anthropic", "socket")
    for relative in (
        "apps/api/study_anything/cbb/agentic/tools.py",
        "apps/api/study_anything/cbb/agentic/planner.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for module in forbidden:
            if f"import {module}" in text or f"from {module}" in text:
                findings.append(f"{relative}:{module}")
    return findings


def build_report() -> dict[str, Any]:
    registry = default_tool_registry()
    case = build_agentic_evolution_cases()["approved-local-candidate"]
    context = case["inputs"]["agentic_evidence"]
    plan = AgenticPlanV1.model_validate(context["plan"])
    results = [AgenticToolResultV1.model_validate(item) for item in context["tool_results"]]

    unknown_plan = deepcopy(context["plan"])
    unknown_plan["calls"][0]["tool_id"] = "cbb.gate.approve"
    effect_plan = deepcopy(context["plan"])
    effect_plan["calls"][0]["requested_effect"] = "propose_candidate"
    unsafe_request = deepcopy(context["plan"])
    unsafe_request["policy_mutation_requested"] = True
    missing_quarantine = deepcopy(context["plan"])
    missing_quarantine["calls"][1]["quarantine_acknowledged"] = False
    oversized_result = deepcopy(context["tool_results"][0])
    oversized_result["output_refs"] = [f"ref:{index}" for index in range(21)]

    checks = {
        "allowlist_exact": set(registry.contracts)
        == {"cbb.receipt.lookup", "cbb.memory.search", "cbb.evolution.propose"},
        "valid_plan_passes": not registry.validate_plan(plan),
        "valid_results_pass": not registry.validate_results(plan, results),
        "unknown_gate_tool_rejected": bool(
            registry.validate_plan(AgenticPlanV1.model_validate(unknown_plan))
        ),
        "effect_mismatch_rejected": bool(
            registry.validate_plan(AgenticPlanV1.model_validate(effect_plan))
        ),
        "policy_mutation_request_rejected": _rejected(
            lambda: AgenticPlanV1.model_validate(unsafe_request),
            "policy_mutation_requested",
        ),
        "missing_quarantine_rejected": _rejected(
            lambda: AgenticPlanV1.model_validate(missing_quarantine),
            "quarantined",
        ),
        "output_bound_rejected": bool(
            registry.validate_results(
                plan,
                [AgenticToolResultV1.model_validate(oversized_result), *results[1:]],
            )
        ),
        "contracts_have_no_side_effect_authority": all(
            not any(
                (
                    contract.network_allowed,
                    contract.filesystem_write_allowed,
                    contract.policy_mutation_allowed,
                    contract.gate_decision_allowed,
                    contract.production_mutation_allowed,
                )
            )
            for contract in registry.contracts.values()
        ),
        "results_are_supporting_only": all(
            result.authority == "supporting_evidence_only"
            and not result.policy_override_allowed
            and not result.gate_decision_allowed
            and not result.production_mutation_performed
            for result in results
        ),
        "static_runtime_isolation": not _forbidden_imports(),
    }
    if not all(checks.values()):
        raise ValueError(
            "Agentic tool boundary verification failed: "
            + ", ".join(name for name, passed in checks.items() if not passed)
        )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "registry_digest_sha256": registry.digest_sha256,
        "tool_count": len(registry.contracts),
        "checks": checks,
        "claim_boundary": (
            "This verifies a deterministic typed allowlist and proposal-only tool results. "
            "It does not prove model safety, production sandboxing, or external identity."
        ),
        "privacy": {
            "metadata_only": True,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "filesystem_writes_performed_by_tools": False,
            "production_mutation_performed": False,
            "policy_mutation_performed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("choose exactly one of --check or --write")
    serialized = json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output = Path(args.output)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    elif not output.is_file() or output.read_text(encoding="utf-8") != serialized:
        raise SystemExit(
            "Agentic tool boundary report is stale; run python3 "
            "scripts/verify_cbb_agentic_tool_boundary.py --write"
        )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
