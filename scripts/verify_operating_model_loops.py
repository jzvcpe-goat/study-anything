#!/usr/bin/env python3
"""Verify the Cognitive Black Box operating-model loop contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
LOOPS_PATH = ROOT / ".cognitive-loop" / "loops.yaml"
DOC_PATH = ROOT / "docs" / "operating-model.md"
REPORT_PATH = ROOT / "platform" / "generated" / "study-anything-operating-model-loops.json"
SCHEMA_VERSION = "cognitive-loop-operating-model-loops-v1"
REPORT_SCHEMA_VERSION = "study-anything-operating-model-loops-verification-v1"

REQUIRED_LOOPS: dict[str, dict[str, str]] = {
    "agentic_coding_loop": {
        "cadence": "~minutes",
        "cadence_unit": "minutes",
        "left_actor": "coding_agent",
        "right_actor": "product_spec_evals",
    },
    "developer_feedback_loop": {
        "cadence": "~hours",
        "cadence_unit": "hours",
        "left_actor": "product_spec_evals",
        "right_actor": "developer_vision",
    },
    "external_feedback_loop": {
        "cadence": "~days",
        "cadence_unit": "days",
        "left_actor": "developer_vision",
        "right_actor": "external_feedback",
    },
}

REQUIRED_PR_EVIDENCE = {
    "loop_id_declared",
    "privacy_boundary_statement",
    "claim_boundary_statement",
}

FORBIDDEN_MARKERS = (
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "AGENT_LLM_API_KEY=",
    "sk-proj-",
    "Bearer ",
    "cookie=",
    "signed_url=",
    "-----BEGIN PRIVATE KEY-----",
)


class OperatingModelVerifierError(RuntimeError):
    """Readable verifier failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise OperatingModelVerifierError(message)


def load_json_subset_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise OperatingModelVerifierError(f"missing contract: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OperatingModelVerifierError(
            f"{path} must remain JSON-subset YAML so the verifier needs no PyYAML: {exc}"
        ) from exc
    require(isinstance(payload, dict), f"{path} must contain an object")
    return payload


def assert_no_forbidden_markers(text: str, label: str) -> None:
    for marker in FORBIDDEN_MARKERS:
        require(marker not in text, f"{label} leaked forbidden marker: {marker}")


def require_string_list(payload: Mapping[str, Any], key: str, label: str) -> list[str]:
    value = payload.get(key)
    require(isinstance(value, list), f"{label}.{key} must be a list")
    require(value, f"{label}.{key} must not be empty")
    require(all(isinstance(item, str) and item for item in value), f"{label}.{key} must be strings")
    return list(value)


def validate_loop(loop: Mapping[str, Any]) -> dict[str, Any]:
    loop_id = loop.get("id")
    require(isinstance(loop_id, str), "loop.id must be a string")
    expected = REQUIRED_LOOPS.get(loop_id)
    require(expected is not None, f"unexpected loop id: {loop_id}")
    for key, expected_value in expected.items():
        require(loop.get(key) == expected_value, f"{loop_id}.{key} drifted")

    for key in ("name", "purpose"):
        require(isinstance(loop.get(key), str) and loop[key], f"{loop_id}.{key} missing")
    for key in ("entry_triggers", "allowed_outputs", "required_pr_evidence"):
        require_string_list(loop, key, loop_id)

    evidence = set(require_string_list(loop, "required_pr_evidence", loop_id))
    require(REQUIRED_PR_EVIDENCE <= evidence, f"{loop_id} missing common PR evidence fields")
    if loop_id == "developer_feedback_loop":
        require("developer_decision_reference" in evidence, "developer loop must require decision evidence")
        require("follow_up_loop_assignment" in evidence, "developer loop must assign follow-up loops")
    if loop_id == "external_feedback_loop":
        require("external_evidence_reference" in evidence, "external loop must require external evidence")
        require("redaction_or_privacy_receipt" in evidence, "external loop must require redaction evidence")
    if loop_id == "agentic_coding_loop":
        require("focused_verifier_command" in evidence, "agentic loop must require focused verifier evidence")
        require("generated_evidence_current" in evidence, "agentic loop must require generated evidence freshness")

    promotion = loop.get("promotion_rule")
    require(isinstance(promotion, Mapping), f"{loop_id}.promotion_rule missing")
    allowed = require_string_list(promotion, "release_stack_candidate_allowed_when", loop_id)
    blocked = require_string_list(promotion, "blocked_when", loop_id)
    require(any("claim" in item for item in allowed + blocked), f"{loop_id} must mention claim boundary")
    require(any("privacy" in item or "secret" in item for item in allowed + blocked), f"{loop_id} must mention privacy boundary")

    dual_loop = loop.get("dual_loop_alignment")
    require(isinstance(dual_loop, Mapping), f"{loop_id}.dual_loop_alignment missing")
    for key in (
        "controlled_failure_environment",
        "human_attention_reconstruction",
        "propagation_gate",
    ):
        require(isinstance(dual_loop.get(key), str) and dual_loop[key], f"{loop_id}.{key} missing")

    return {
        "id": loop_id,
        "cadence": loop["cadence"],
        "actors": [loop["left_actor"], loop["right_actor"]],
        "required_evidence_count": len(evidence),
        "release_stack_candidate_conditions": len(allowed),
        "blocked_conditions": len(blocked),
    }


def validate_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    require(payload.get("schema_version") == SCHEMA_VERSION, "schema_version drifted")
    source_model = payload.get("source_model")
    require(isinstance(source_model, Mapping), "source_model missing")
    require(
        source_model.get("name") == "3 key product development loops",
        "source model must anchor the operator diagram",
    )
    require("full release validation" in str(source_model.get("claim_boundary", "")), "claim boundary missing")

    loops = payload.get("loops")
    require(isinstance(loops, list), "loops must be a list")
    require(len(loops) == 3, "exactly three operating loops are required")
    loop_reports = [validate_loop(loop) for loop in loops if isinstance(loop, Mapping)]
    require(len(loop_reports) == 3, "every loop must be an object")
    require({item["id"] for item in loop_reports} == set(REQUIRED_LOOPS), "loop id set drifted")

    pr_contract = payload.get("pull_request_contract")
    require(isinstance(pr_contract, Mapping), "pull_request_contract missing")
    required_fields = set(require_string_list(pr_contract, "required_fields", "pull_request_contract"))
    require(
        {"Loop", "Evidence", "Claim boundary", "Privacy boundary", "Release-stack effect"}
        <= required_fields,
        "PR required fields drifted",
    )
    require(pr_contract.get("primary_loop_exactly_one") is True, "PR must require exactly one primary loop")
    require(pr_contract.get("claim_boundary_required") is True, "claim boundary must be required")
    require(pr_contract.get("privacy_boundary_required") is True, "privacy boundary must be required")
    require(pr_contract.get("evidence_refs_required") is True, "evidence refs must be required")

    release_stack = payload.get("release_stack")
    require(isinstance(release_stack, Mapping), "release_stack missing")
    for key in ("candidate_entry_requires", "intake_requires", "promotion_requires"):
        values = set(require_string_list(release_stack, key, "release_stack"))
        require(any("loop" in item for item in values), f"release_stack.{key} must mention loop classification")
    require(release_stack.get("self_intake_after_merge") is True, "self-intake rule must be enabled")

    privacy = payload.get("privacy")
    require(isinstance(privacy, Mapping), "privacy missing")
    require(privacy.get("metadata_only") is True, "metadata_only must be true")
    false_flags = [
        "raw_source_text_included",
        "raw_report_text_included",
        "learner_answers_included",
        "screenshots_included",
        "keystrokes_included",
        "mouse_coordinates_included",
        "biometrics_included",
        "real_model_keys_included",
        "agent_credentials_included",
        "cookies_or_bearer_tokens_included",
        "signed_urls_included",
        "production_mutation_allowed_by_default",
    ]
    for key in false_flags:
        require(privacy.get(key) is False, f"privacy.{key} must be false")

    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert_no_forbidden_markers(serialized, "loops contract")

    return {
        "loop_reports": loop_reports,
        "required_pr_fields": sorted(required_fields),
        "release_stack": {
            "candidate_entry_requires": release_stack["candidate_entry_requires"],
            "intake_requires": release_stack["intake_requires"],
            "promotion_requires": release_stack["promotion_requires"],
            "self_intake_after_merge": True,
        },
        "privacy": dict(privacy),
    }


def validate_doc() -> dict[str, Any]:
    if not DOC_PATH.is_file():
        raise OperatingModelVerifierError(f"missing doc: {DOC_PATH}")
    text = DOC_PATH.read_text(encoding="utf-8")
    assert_no_forbidden_markers(text, "operating model doc")
    required_markers = [
        "Agentic Coding Loop",
        "Developer Feedback Loop",
        "External Feedback Loop",
        "~minutes",
        "~hours",
        "~days",
        "coding agent",
        "product spec/evals",
        "developer vision",
        "external feedback",
        "Loop:",
        "Evidence:",
        "Claim boundary:",
        "Privacy boundary:",
        "Release-stack effect:",
        ".cognitive-loop/loops.yaml",
        "python3 scripts/verify_operating_model_loops.py --check",
        "platform/generated/study-anything-operating-model-loops.json",
    ]
    missing = [marker for marker in required_markers if marker not in text]
    require(not missing, f"operating model doc missing markers: {missing}")
    return {
        "path": "docs/operating-model.md",
        "required_markers_present": True,
        "mentions_pr_contract": "Every non-trivial PR should include" in text,
        "mentions_release_stack_rule": "A PR can become a release-stack candidate only when" in text,
    }


def build_report() -> dict[str, Any]:
    payload = load_json_subset_yaml(LOOPS_PATH)
    contract_report = validate_contract(payload)
    doc_report = validate_doc()
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "pass",
        "source_contract": ".cognitive-loop/loops.yaml",
        "operating_model_doc": doc_report,
        "source_diagram_model": payload["source_model"],
        "loops": contract_report["loop_reports"],
        "pull_request_contract": {
            "primary_loop_exactly_one": True,
            "required_fields": contract_report["required_pr_fields"],
        },
        "release_stack": contract_report["release_stack"],
        "privacy": {
            **contract_report["privacy"],
            "forbidden_marker_patterns_scanned": len(FORBIDDEN_MARKERS),
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_operating_model_loops.py --check",
            "generated_report": "platform/generated/study-anything-operating-model-loops.json",
            "release_check_integrated": True,
        },
        "claim_boundary": (
            "This verifier proves the repository operating-model loop contract is present, "
            "metadata-only, and release-stack bounded. It does not prove a full release_check.sh run."
        ),
    }
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert_no_forbidden_markers(serialized, "verification report")
    return report


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT_PATH))
    args = parser.parse_args()

    output = Path(args.output)
    report = build_report()
    serialized = dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Operating model loop report is missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit(
                "Operating model loop report is out of date. "
                "Run: python3 scripts/verify_operating_model_loops.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"verify_operating_model_loops failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
