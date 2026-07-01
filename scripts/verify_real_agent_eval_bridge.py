#!/usr/bin/env python3
"""Verify user-owned real-agent external eval receipt import."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.core.real_agent_eval_bridge import (  # noqa: E402
    ADAPTER_IDS,
    ADAPTER_RECEIPT_SCHEMA_VERSION,
    REAL_AGENT_EVAL_BRIDGE_REPORT_SCHEMA_VERSION,
    build_real_agent_eval_bridge_report,
    dump_json,
    load_json,
    render_bridge_html,
)


REPORT = ROOT / "platform" / "generated" / "study-anything-real-agent-eval-bridge.json"
HTML_REPORT = ROOT / "platform" / "generated" / "study-anything-real-agent-eval-bridge.html"
PASS_FIXTURE = ROOT / "fixtures" / "real-agent-eval-bridge" / "pass.json"
MISSING_MODEL_CALL_FIXTURE = ROOT / "fixtures" / "real-agent-eval-bridge" / "missing-model-call.json"
ADAPTER_FAILED_FIXTURE = ROOT / "fixtures" / "real-agent-eval-bridge" / "adapter-failed.json"
VERIFICATION_SCHEMA_VERSION = "real-agent-eval-bridge-verification-v1"


class RealAgentEvalBridgeVerifierError(RuntimeError):
    """Readable verifier failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RealAgentEvalBridgeVerifierError(message)


def build_from_fixture(path: Path) -> dict[str, Any]:
    return build_real_agent_eval_bridge_report(load_json(path))


def require_report_contract(report: Mapping[str, Any]) -> None:
    require(report.get("schema_version") == REAL_AGENT_EVAL_BRIDGE_REPORT_SCHEMA_VERSION, "report schema drifted")
    privacy = report.get("privacy")
    require(isinstance(privacy, Mapping), "privacy missing")
    require(privacy.get("metadata_only") is True, "report must be metadata-only")
    require(privacy.get("model_calls_performed_by_study_anything") is False, "Study Anything must not call models")
    require(privacy.get("model_keys_stored_by_study_anything") is False, "Study Anything must not store model keys")
    require(privacy.get("raw_prompts_included") is False, "raw prompts must be excluded")
    require(privacy.get("raw_source_text_included") is False, "raw source text must be excluded")
    require(privacy.get("raw_answers_included") is False, "raw answers must be excluded")
    receipts = report.get("adapter_receipts")
    require(isinstance(receipts, list), "adapter receipts missing")
    adapter_ids = {str(item.get("adapter_id")) for item in receipts if isinstance(item, Mapping)}
    require(adapter_ids == set(ADAPTER_IDS), f"adapter receipts drifted: {adapter_ids}")
    for item in receipts:
        require(isinstance(item, Mapping), "adapter receipt must be object")
        require(item.get("schema_version") == ADAPTER_RECEIPT_SCHEMA_VERSION, "adapter receipt schema drifted")
        require(item.get("privacy", {}).get("raw_outputs_included") is False, "raw external evaluator output leaked")
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "OPENAI_API_KEY=",
        "MOONSHOT_API_KEY=",
        "AGENT_LLM_API_KEY=",
        "raw private source text",
        "private answer:",
        "raw prompt:",
        "http://127.0.0.1:8787",
    ):
        require(forbidden not in serialized, f"forbidden marker leaked: {forbidden}")


def build_verification_report() -> dict[str, Any]:
    passing = build_from_fixture(PASS_FIXTURE)
    missing_model_call = build_from_fixture(MISSING_MODEL_CALL_FIXTURE)
    adapter_failed = build_from_fixture(ADAPTER_FAILED_FIXTURE)
    for report in (passing, missing_model_call, adapter_failed):
        require_report_contract(report)
    require(passing["gate"]["status"] == "allowed", "passing bridge fixture must be allowed")
    require(missing_model_call["gate"]["status"] == "blocked", "missing model call fixture must block")
    require(
        any(str(reason).startswith("external_model_call_missing:") for reason in missing_model_call["gate"]["blocked_reasons"]),
        "missing model call fixture must name the missing model-call evidence",
    )
    require(adapter_failed["gate"]["status"] == "blocked", "failed adapter fixture must block")
    require("adapter_failed:ragas" in adapter_failed["gate"]["blocked_reasons"], "failed adapter must identify ragas")
    return {
        "schema_version": VERIFICATION_SCHEMA_VERSION,
        "status": "pass",
        "bridge_report": passing,
        "negative_fixtures": {
            "missing_model_call": {
                "status": missing_model_call["status"],
                "gate": missing_model_call["gate"],
            },
            "adapter_failed": {
                "status": adapter_failed["status"],
                "gate": adapter_failed["gate"],
            },
        },
        "coverage": {
            "promptfoo_adapter_receipt": passing["adapter_statuses"]["promptfoo"] == "pass",
            "ragas_adapter_receipt": passing["adapter_statuses"]["ragas"] == "pass",
            "deepeval_adapter_receipt": passing["adapter_statuses"]["deepeval"] == "pass",
            "langchain_agentevals_adapter_receipt": passing["adapter_statuses"]["langchain-agentevals"] == "pass",
            "user_owned_eval_environment_required": True,
            "missing_model_call_blocks": missing_model_call["gate"]["status"] == "blocked",
            "adapter_failure_blocks": adapter_failed["gate"]["status"] == "blocked",
        },
        "privacy": {
            "metadata_only": True,
            "model_calls_performed_by_study_anything": False,
            "model_keys_stored_by_study_anything": False,
            "raw_prompt_source_answer_included": False,
        },
        "commands": {
            "build": "python3 scripts/real_agent_eval_bridge.py eval-bridge --input fixtures/real-agent-eval-bridge/pass.json",
            "verify": "python3 scripts/verify_real_agent_eval_bridge.py --check",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", default=str(REPORT))
    parser.add_argument("--html-output", default=str(HTML_REPORT))
    args = parser.parse_args()

    report = build_verification_report()
    serialized = dump_json(report)
    output = Path(args.output)
    html_output = Path(args.html_output)
    if args.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        html_output.write_text(render_bridge_html(report["bridge_report"], title="Real Agent Eval Bridge"), encoding="utf-8")
    if args.check:
        if not output.is_file():
            raise SystemExit(f"Real-agent eval bridge report missing: {output}")
        if output.read_text(encoding="utf-8") != serialized:
            raise SystemExit("Real-agent eval bridge report is stale. Run: python3 scripts/verify_real_agent_eval_bridge.py --write")
        expected_html = render_bridge_html(report["bridge_report"], title="Real Agent Eval Bridge")
        if not html_output.is_file() or html_output.read_text(encoding="utf-8") != expected_html:
            raise SystemExit("Real-agent eval bridge HTML report is stale. Run: python3 scripts/verify_real_agent_eval_bridge.py --write")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover
        print(f"verify_real_agent_eval_bridge failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
