#!/usr/bin/env python3
"""Verify external Cognitive Loop Review Agent report handoff assets."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "platform" / "schemas" / "cognitive-loop-review-agent-report.schema.json"
PROMPT_PATH = ROOT / "platform" / "prompts" / "cognitive-loop-review-agent.json"
FIXTURE_DIR = ROOT / "fixtures" / "review-agent"
REPORT = ROOT / "platform" / "generated" / "study-anything-cognitive-loop-review-agent-report.json"

SCHEMA_VERSION = "cognitive-loop-review-agent-report-handoff-v1"
REPORT_SCHEMA_ID = "https://study-anything.local/schemas/cognitive-loop-review-agent-report-v1.json"
REPORT_VERSION = "1.0"
POSITIVE_FIXTURES = ("approved.json", "needs-review.json", "needs-fix.json")
NEGATIVE_FIXTURES = ("invalid-low-confidence-final.json",)
VALID_DIMENSIONS = {"logic", "security", "architecture", "test"}
VALID_SEVERITIES = {"info", "warn", "critical"}
VALID_CONFIDENCE = {"medium", "high"}
EVIDENCE_RE = re.compile(r"^[A-Za-z0-9_./-]+:\d+\b.+")
LINE_RANGE_RE = re.compile(r"^\d+(-\d+)?$")
SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"https?://[^/\s:]+:[^@\s]+@"),
)
FORBIDDEN_LITERALS = (
    "diff --git",
    "@@ ",
    "OPENAI_API_KEY=",
    "MOONSHOT_API_KEY=",
    "Private learner answer",
    "raw source text",
    "hidden chain-of-thought",
    "http://private-agent.local",
)


class ReviewAgentReportError(RuntimeError):
    """Readable Review Agent report handoff failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReviewAgentReportError(f"Cannot read JSON {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewAgentReportError(f"JSON object expected: {path.relative_to(ROOT)}")
    return value


def reject_private_text(value: Any, *, label: str) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    leaked_literals = [needle for needle in FORBIDDEN_LITERALS if needle in serialized]
    leaked_patterns = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(serialized)]
    if leaked_literals or leaked_patterns:
        raise ReviewAgentReportError(
            f"{label} contains private or raw-diff text: literals={leaked_literals} patterns={leaked_patterns}"
        )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewAgentReportError(message)


def require_string(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReviewAgentReportError(f"Expected non-empty string field: {key}")
    return value


def require_int(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping.get(key)
    if not isinstance(value, int) or value < 0:
        raise ReviewAgentReportError(f"Expected non-negative integer field: {key}")
    return value


def validate_schema_asset(schema: Mapping[str, Any]) -> dict[str, Any]:
    require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", "Schema must use draft 2020-12.")
    require(schema.get("$id") == REPORT_SCHEMA_ID, "Report schema id drifted.")
    required = set(schema.get("required", []))
    expected_required = {
        "report_version",
        "pr_id",
        "change_type",
        "overall_risk",
        "decision",
        "summary",
        "findings",
        "metrics",
        "ci_instructions",
        "suppressed_low_confidence",
    }
    missing = expected_required - required
    require(not missing, f"Report schema missing required fields: {sorted(missing)}")
    findings = schema.get("properties", {}).get("findings", {})
    require(findings.get("maxItems") == 8, "Report schema must cap findings at 8.")
    confidence = (
        schema.get("$defs", {})
        .get("finding", {})
        .get("properties", {})
        .get("confidence", {})
        .get("enum")
    )
    require(confidence == ["medium", "high"], "Final findings must only allow medium/high confidence.")
    suppressed_confidence = (
        schema.get("$defs", {})
        .get("suppressedFinding", {})
        .get("properties", {})
        .get("confidence", {})
        .get("const")
    )
    require(suppressed_confidence == "low", "Suppressed findings must require low confidence.")
    reject_private_text(schema, label="Review Agent report schema")
    return {
        "schema_id": schema["$id"],
        "max_findings": findings["maxItems"],
        "final_confidence": confidence,
        "suppressed_confidence": suppressed_confidence,
    }


def validate_finding(finding: Mapping[str, Any], *, fixture_name: str, expected_rank: int) -> dict[str, Any]:
    require(finding.get("rank") == expected_rank, f"{fixture_name} finding ranks must be contiguous.")
    dimension = require_string(finding, "dimension")
    severity = require_string(finding, "severity")
    confidence = require_string(finding, "confidence")
    file_path = require_string(finding, "file")
    line_range = require_string(finding, "line_range")
    evidence = require_string(finding, "evidence")
    require(dimension in VALID_DIMENSIONS, f"{fixture_name} invalid dimension: {dimension}")
    require(severity in VALID_SEVERITIES, f"{fixture_name} invalid severity: {severity}")
    require(confidence in VALID_CONFIDENCE, f"{fixture_name} final finding confidence must be medium/high.")
    require(not file_path.startswith("/") and ".." not in file_path.split("/"), f"{fixture_name} file must be repo-relative.")
    require(LINE_RANGE_RE.match(line_range) is not None, f"{fixture_name} invalid line_range: {line_range}")
    require(EVIDENCE_RE.match(evidence) is not None, f"{fixture_name} evidence must start with file:line snippet.")
    require(evidence.startswith(f"{file_path}:") or evidence.startswith(f"{file_path.split('/')[-1]}:"), f"{fixture_name} evidence must cite the finding file.")
    if dimension == "security" and severity == "critical":
        cwes = finding.get("cwe_references")
        require(isinstance(cwes, list) and cwes, f"{fixture_name} critical security findings need CWE references.")
    reject_private_text(finding, label=f"{fixture_name} finding")
    return {"dimension": dimension, "severity": severity, "confidence": confidence, "blocking": bool(finding.get("blocking"))}


def validate_suppressed(item: Mapping[str, Any], *, fixture_name: str) -> None:
    require(require_string(item, "confidence") == "low", f"{fixture_name} suppressed findings must be low confidence.")
    require(EVIDENCE_RE.match(require_string(item, "evidence")) is not None, f"{fixture_name} suppressed evidence must cite file:line.")
    require_string(item, "suppression_reason")
    reject_private_text(item, label=f"{fixture_name} suppressed finding")


def validate_report(payload: Mapping[str, Any], *, fixture_name: str) -> dict[str, Any]:
    require(payload.get("report_version") == REPORT_VERSION, f"{fixture_name} report_version drifted.")
    decision = require_string(payload, "decision")
    overall_risk = require_string(payload, "overall_risk")
    require(decision in {"approved", "needs-review", "needs-fix"}, f"{fixture_name} invalid decision.")
    require(overall_risk in {"low", "medium", "high"}, f"{fixture_name} invalid risk.")
    findings = payload.get("findings")
    suppressed = payload.get("suppressed_low_confidence")
    metrics = payload.get("metrics")
    ci = payload.get("ci_instructions")
    require(isinstance(findings, list), f"{fixture_name} findings must be a list.")
    require(isinstance(suppressed, list), f"{fixture_name} suppressed_low_confidence must be a list.")
    require(isinstance(metrics, Mapping), f"{fixture_name} metrics must be an object.")
    require(isinstance(ci, Mapping), f"{fixture_name} ci_instructions must be an object.")
    require(len(findings) <= 8, f"{fixture_name} has more than 8 findings.")
    finding_summaries = [
        validate_finding(finding, fixture_name=fixture_name, expected_rank=index)
        for index, finding in enumerate(findings, start=1)
        if isinstance(finding, Mapping)
    ]
    require(len(finding_summaries) == len(findings), f"{fixture_name} all findings must be objects.")
    for item in suppressed:
        require(isinstance(item, Mapping), f"{fixture_name} suppressed items must be objects.")
        validate_suppressed(item, fixture_name=fixture_name)

    severity_counts = {
        "critical": sum(1 for item in finding_summaries if item["severity"] == "critical"),
        "warn": sum(1 for item in finding_summaries if item["severity"] == "warn"),
        "info": sum(1 for item in finding_summaries if item["severity"] == "info"),
    }
    require(require_int(metrics, "critical_count") == severity_counts["critical"], f"{fixture_name} critical_count mismatch.")
    require(require_int(metrics, "warn_count") == severity_counts["warn"], f"{fixture_name} warn_count mismatch.")
    require(require_int(metrics, "info_count") == severity_counts["info"], f"{fixture_name} info_count mismatch.")
    dimensions = metrics.get("review_dimensions_covered")
    require(isinstance(dimensions, list) and set(dimensions).issubset(VALID_DIMENSIONS), f"{fixture_name} invalid dimensions.")

    should_block = ci.get("should_block_merge")
    human_review = ci.get("required_human_review")
    require(isinstance(should_block, bool), f"{fixture_name} should_block_merge must be boolean.")
    require(isinstance(human_review, bool), f"{fixture_name} required_human_review must be boolean.")
    if severity_counts["critical"]:
        require(decision == "needs-fix", f"{fixture_name} critical findings must decide needs-fix.")
        require(should_block is True, f"{fixture_name} critical findings must block merge.")
    elif severity_counts["warn"]:
        require(decision == "needs-review", f"{fixture_name} warn findings must decide needs-review.")
        require(human_review is True, f"{fixture_name} warn findings must require human review.")
    else:
        require(decision == "approved", f"{fixture_name} no warn/critical findings must approve.")
        require(should_block is False, f"{fixture_name} approved report must not block.")
    reject_private_text(payload, label=f"{fixture_name} report")
    return {
        "decision": decision,
        "overall_risk": overall_risk,
        "finding_count": len(findings),
        "suppressed_count": len(suppressed),
        "critical_count": severity_counts["critical"],
        "warn_count": severity_counts["warn"],
        "info_count": severity_counts["info"],
    }


def validate_negative_fixture(path: Path) -> str:
    payload = read_json(path)
    try:
        validate_report(payload, fixture_name=path.name)
    except ReviewAgentReportError as exc:
        return str(exc)
    raise ReviewAgentReportError(f"Negative fixture unexpectedly passed: {path.relative_to(ROOT)}")


def validate_prompt_and_docs() -> dict[str, str]:
    prompt = read_json(PROMPT_PATH)
    prompt_text = json.dumps(prompt, ensure_ascii=False, sort_keys=True)
    require("platform/schemas/cognitive-loop-review-agent-report.schema.json" in prompt_text, "Prompt contract must reference report schema.")
    docs = {
        "docs/cognitive-loop-code-review.md": [
            "platform/schemas/cognitive-loop-review-agent-report.schema.json",
            "fixtures/review-agent",
            "verify_cognitive_loop_review_agent_report.py --check",
        ],
        "docs/cognitive-loop-contracts.md": [
            "verify_cognitive_loop_review_agent_report.py --check",
        ],
        ".cognitive-loop/evals.yaml": [
            "cognitive-loop.review-agent-report",
            "python3 scripts/verify_cognitive_loop_review_agent_report.py --check",
        ],
        "scripts/release_check.sh": [
            "scripts/verify_cognitive_loop_review_agent_report.py --check",
        ],
    }
    checked: dict[str, str] = {}
    for relative, needles in docs.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        require(not missing, f"{relative} missing required Review Agent report references: {missing}")
        checked[relative] = "pass"
    return checked


def build_report() -> dict[str, Any]:
    schema_summary = validate_schema_asset(read_json(SCHEMA_PATH))
    fixture_summaries = {
        name: validate_report(read_json(FIXTURE_DIR / name), fixture_name=name)
        for name in POSITIVE_FIXTURES
    }
    negative = {name: validate_negative_fixture(FIXTURE_DIR / name) for name in NEGATIVE_FIXTURES}
    docs = validate_prompt_and_docs()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "report_schema": str(SCHEMA_PATH.relative_to(ROOT)),
        "fixtures": fixture_summaries,
        "negative_fixtures": negative,
        "docs": docs,
        "privacy": {
            "raw_diff_stored_by_study_anything": False,
            "file_bodies_stored_by_study_anything": False,
            "real_model_keys_stored_by_study_anything": False,
            "private_agent_endpoints_stored_by_study_anything": False,
            "hidden_chain_of_thought_allowed": False,
        },
        "acceptance": {
            "minimum_command": "python3 scripts/verify_cognitive_loop_review_agent_report.py --check",
            "schema_id": schema_summary["schema_id"],
            "max_findings": schema_summary["max_findings"],
            "final_confidence": schema_summary["final_confidence"],
            "suppressed_confidence": schema_summary["suppressed_confidence"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    args = parser.parse_args()

    output = Path(args.output)
    report = build_report()
    serialized = dump_json(report)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Cognitive Loop Review Agent report handoff is missing: {output}")
        current = output.read_text(encoding="utf-8")
        if current != serialized:
            raise SystemExit(
                "Cognitive Loop Review Agent report handoff is out of date. "
                "Run: python3 scripts/verify_cognitive_loop_review_agent_report.py --write"
            )
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
