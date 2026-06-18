#!/usr/bin/env python3
"""Verify the external Cognitive Loop Review Agent prompt contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
PROMPT_CONTRACT = ROOT / "platform" / "prompts" / "cognitive-loop-review-agent.json"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review-agent-prompt.json"
SCHEMA_VERSION = "cognitive-loop-review-agent-prompt-verification-v1"
PROMPT_SCHEMA_VERSION = "cognitive-loop-review-agent-prompt-v1"


class ReviewAgentPromptError(RuntimeError):
    """Raised when the Review Agent prompt contract drifts."""


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ReviewAgentPromptError(f"Expected JSON object: {path}")
    return data


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentPromptError(message)


def _require_text(container: Any, needle: str, label: str) -> None:
    haystack = json.dumps(container, ensure_ascii=False, sort_keys=True)
    _require(needle in haystack, f"{label} must include: {needle}")


def _require_bool(mapping: Mapping[str, Any], key: str, expected: bool) -> None:
    _require(mapping.get(key) is expected, f"{key} must be {expected!r}.")


def validate_prompt_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    _require(payload.get("schema_version") == PROMPT_SCHEMA_VERSION, "Prompt schema version drifted.")
    _require(payload.get("agent_id") == "cognitive-loop-review-agent", "Unexpected Review Agent id.")

    boundary = payload.get("product_boundary")
    _require(isinstance(boundary, Mapping), "product_boundary must be an object.")
    _require_bool(boundary, "delivery_assurance_tooling", True)
    _require_bool(boundary, "end_user_learning_feature", False)
    _require_bool(boundary, "generates_business_feature_code", False)
    _require(boundary.get("study_anything_learning_adapter") == "out_of_scope", "Learning Adapter must be out of scope.")
    _require(boundary.get("model_key_custody") == "external_only", "Model key custody must stay external.")
    _require(boundary.get("diff_storage_in_study_anything") == "forbidden", "Diff storage must be forbidden.")
    _require(boundary.get("raw_file_storage_in_study_anything") == "forbidden", "File-body storage must be forbidden.")

    audience = payload.get("audience")
    _require(isinstance(audience, list), "audience must be a list.")
    _require({"maintainers", "platform_agents"}.issubset(set(audience)), "Audience must target maintainers and platform Agents.")

    _require_text(payload.get("identity_boundaries", []), "你不是用户学习助手", "identity_boundaries")
    _require_text(payload.get("identity_boundaries", []), "不生成业务功能代码", "identity_boundaries")
    _require_text(payload.get("input_constraints", []), "仅基于提供的 git diff", "input_constraints")
    _require_text(payload.get("input_constraints", []), "不假设未显示的测试覆盖", "input_constraints")

    output = payload.get("output_discipline")
    _require(isinstance(output, Mapping), "output_discipline must be an object.")
    _require(output.get("format") == "json_only", "Review Agent output must be JSON-only.")
    _require_bool(output, "no_explanatory_prose", True)
    _require_bool(output, "omit_uncertain_findings", True)
    _require(output.get("max_findings") == 8, "External Review Agent must cap findings at 8.")
    _require_text(output.get("required_evidence", ""), "具体行号或代码片段", "output_discipline")

    stages = payload.get("review_stages")
    _require(isinstance(stages, Mapping), "review_stages must be an object.")
    for key in ("pre_review", "logic_review", "security_review", "architecture_review", "test_review"):
        _require(key in stages, f"review_stages missing {key}.")

    final_schema = payload.get("final_report_schema")
    _require(isinstance(final_schema, Mapping), "final_report_schema must be an object.")
    _require("findings" in final_schema, "final_report_schema must define findings.")
    _require("suppressed_low_confidence" in final_schema, "final_report_schema must include suppressed_low_confidence.")

    confidence = payload.get("confidence_rules")
    _require(isinstance(confidence, Mapping), "confidence_rules must be an object.")
    _require_bool(confidence, "evidence_required", True)
    _require(confidence.get("final_report_confidence") == ["high", "medium"], "Only high/medium confidence findings may enter final report.")
    _require(confidence.get("suppressed_confidence") == ["low"], "Low confidence findings must be suppressed.")
    _require_text(confidence, "[文件名]:[行号] 代码片段", "confidence_rules")

    notes = payload.get("integration_notes")
    _require(isinstance(notes, Mapping), "integration_notes must be an object.")
    _require_text(notes, "metadata-only", "integration_notes")
    _require_text(notes, "最多 5 条", "integration_notes")
    _require_text(notes, "最多 8 个发现", "integration_notes")
    _require_text(notes, "不保存 raw diff", "integration_notes")

    return {
        "identity_boundaries": "pass",
        "input_constraints": "pass",
        "output_discipline": "pass",
        "confidence_rules": "pass",
        "product_boundary": "pass",
        "external_max_findings": output["max_findings"],
    }


def validate_docs_reference_prompt() -> dict[str, Any]:
    required_refs = {
        "README.md": [
            "platform/prompts/cognitive-loop-review-agent.json",
            "developer/operator",
        ],
        "docs/cognitive-loop-code-review.md": [
            "platform/prompts/cognitive-loop-review-agent.json",
            "JSON-only",
            "最多 8",
        ],
        "docs/cognitive-loop-contracts.md": [
            "verify_cognitive_loop_review_agent_prompt.py --check",
        ],
        ".cognitive-loop/evals.yaml": [
            "cognitive-loop.review-agent-prompt",
            "python3 scripts/verify_cognitive_loop_review_agent_prompt.py --check",
        ],
        "scripts/release_check.sh": [
            "scripts/verify_cognitive_loop_review_agent_prompt.py --check",
        ],
    }
    covered: dict[str, str] = {}
    for relative, needles in required_refs.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for needle in needles:
            _require(needle in text, f"{relative} must reference {needle!r}.")
        covered[relative] = "pass"
    return covered


def build_report() -> dict[str, Any]:
    prompt = _read_json(PROMPT_CONTRACT)
    checks = validate_prompt_contract(prompt)
    docs = validate_docs_reference_prompt()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "prompt_contract": str(PROMPT_CONTRACT.relative_to(ROOT)),
        "checks": checks,
        "docs": docs,
        "privacy": {
            "study_anything_stores_diff": False,
            "study_anything_stores_file_bodies": False,
            "study_anything_stores_model_keys": False,
            "external_agent_reads_diff_only_when_ci_provides_it": True,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_review_agent_prompt.py --check",
            "prompt_contract": "platform/prompts/cognitive-loop-review-agent.json",
            "built_in_review_cli": "scripts/cognitive_loop_review.py remains metadata-only advisory evidence",
        },
    }


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    report = build_report()
    serialized = dump_json(report)
    output = Path(args.output)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop Review Agent prompt report is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Review Agent prompt report is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_review_agent_prompt.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
