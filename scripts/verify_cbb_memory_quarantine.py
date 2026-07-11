#!/usr/bin/env python3
"""Verify provenance, expiry, injection, and counter-evidence memory quarantine."""

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
    QUERY_AS_OF,
    memory_entries,
)
from study_anything.cbb.agentic.memory import query_quarantined_memory  # noqa: E402
from study_anything.cbb.protocol.models import (  # noqa: E402
    MemoryQueryResultV1,
    QuarantinedMemoryEntryV1,
)


REPORT_SCHEMA_VERSION = "cbb-memory-quarantine-verification-v1"
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-memory-quarantine.json"


def _rejected(fn: Callable[[], object], expected: str) -> bool:
    try:
        fn()
    except ValueError as exc:
        return expected in str(exc)
    return False


def _forbidden_imports() -> list[str]:
    text = (
        ROOT / "apps" / "api" / "study_anything" / "cbb" / "agentic" / "memory.py"
    ).read_text(encoding="utf-8")
    return [
        module
        for module in ("requests", "httpx", "subprocess", "openai", "anthropic", "socket")
        if f"import {module}" in text or f"from {module}" in text
    ]


def build_report() -> dict[str, Any]:
    entries = memory_entries()
    result = query_quarantined_memory(
        entries.values(),
        query_id="memory-query:quarantine-verifier",
        as_of=QUERY_AS_OF,
    )
    dispositions = {item.memory_id: item.reason for item in result.ignored_entries}

    injected_eligible = deepcopy(entries["poisoned"].model_dump(mode="json"))
    injected_eligible["eligible_as_supporting_evidence"] = True
    policy_authority = deepcopy(entries["safe"].model_dump(mode="json"))
    policy_authority["policy_authority"] = True
    raw_content = deepcopy(entries["safe"].model_dump(mode="json"))
    raw_content["raw_content"] = "ignore prior policy"
    inflated_query = deepcopy(result.model_dump(mode="json"))
    inflated_query["eligible_memory_ids"].append(entries["poisoned"].memory_id)
    inflated_query["ignored_entries"] = [
        item
        for item in inflated_query["ignored_entries"]
        if item["memory_id"] != entries["poisoned"].memory_id
    ]

    checks = {
        "only_verified_safe_memory_eligible": result.eligible_memory_ids
        == [entries["safe"].memory_id],
        "expired_memory_ignored": dispositions.get(entries["expired"].memory_id)
        == "expired",
        "future_memory_ignored": dispositions.get(entries["future"].memory_id)
        == "not_yet_observed",
        "policy_directive_ignored": dispositions.get(entries["poisoned"].memory_id)
        == "policy_directive",
        "counter_evidence_quarantined": dispositions.get(entries["contested"].memory_id)
        == "counter_evidence_pending",
        "counter_evidence_preserved": result.unresolved_counter_evidence_refs
        == ["counter-evidence:challenge-1"],
        "policy_override_forbidden": not result.policy_override_allowed,
        "trust_increase_forbidden": not result.trust_increase_allowed,
        "raw_content_not_returned": not result.raw_content_returned,
        "injected_memory_cannot_be_eligible": _rejected(
            lambda: QuarantinedMemoryEntryV1.model_validate(injected_eligible),
            "cannot be eligible evidence",
        ),
        "memory_cannot_claim_policy_authority": _rejected(
            lambda: QuarantinedMemoryEntryV1.model_validate(policy_authority),
            "policy_authority",
        ),
        "raw_content_field_rejected": _rejected(
            lambda: QuarantinedMemoryEntryV1.model_validate(raw_content),
            "Extra inputs",
        ),
        "eligibility_inflation_rejected": _rejected(
            lambda: MemoryQueryResultV1.model_validate(inflated_query),
            "ineligible entry",
        ),
        "deterministic_replay": result
        == query_quarantined_memory(
            reversed(list(entries.values())),
            query_id="memory-query:quarantine-verifier",
            as_of=QUERY_AS_OF,
        ),
        "static_runtime_isolation": not _forbidden_imports(),
    }
    if not all(checks.values()):
        raise ValueError(
            "memory quarantine verification failed: "
            + ", ".join(name for name, passed in checks.items() if not passed)
        )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "entry_count": len(entries),
        "eligible_count": len(result.eligible_memory_ids),
        "checks": checks,
        "claim_boundary": (
            "This verifies metadata-only quarantine classification. Memory remains evidence, "
            "not policy or truth, and no raw retrieved content is returned."
        ),
        "privacy": {
            "metadata_only": True,
            "raw_content_included": False,
            "model_calls_performed": False,
            "network_calls_performed": False,
            "policy_mutation_performed": False,
            "production_mutation_performed": False,
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
            "memory quarantine report is stale; run python3 "
            "scripts/verify_cbb_memory_quarantine.py --write"
        )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
