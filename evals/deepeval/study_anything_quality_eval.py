#!/usr/bin/env python3
"""Run Study Anything's quality report through a DeepEval custom metric."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(url: str, *, timeout: int) -> dict[str, Any]:
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned {exc.code} for {url}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach Study Anything API at {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object from {url}.")
    return payload


def run_without_deepeval(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "ok" if report.get("status") == "pass" else "failed",
        "tool": "deepeval-compatible-native",
        "framework": "native",
        "quality_score": report.get("quality_score"),
        "threshold": report.get("threshold"),
        "reason": "DeepEval is not installed; used the same deterministic quality report directly.",
    }


def run_with_deepeval(report: dict[str, Any]) -> dict[str, Any]:
    from deepeval.metrics import BaseMetric
    from deepeval.test_case import LLMTestCase

    class StudyAnythingQualityMetric(BaseMetric):
        def __init__(self, threshold: float) -> None:
            self.threshold = threshold
            self.score = 0.0
            self.success = False
            self.reason = ""
            self.error = None

        def measure(self, test_case: LLMTestCase) -> float:
            values = json.loads(test_case.actual_output)
            self.score = float(values.get("quality_score") or 0.0)
            failed_required = [
                gate
                for gate in values.get("gates", [])
                if gate.get("required") and gate.get("status") != "pass"
            ]
            self.success = self.score >= self.threshold and not failed_required
            self.reason = (
                f"score={self.score} threshold={self.threshold} "
                f"failed_required={len(failed_required)}"
            )
            return self.score

        async def a_measure(self, test_case: LLMTestCase) -> float:
            return self.measure(test_case)

        def is_successful(self) -> bool:
            return self.success

        @property
        def __name__(self) -> str:
            return "StudyAnythingQualityMetric"

    metric = StudyAnythingQualityMetric(float(report.get("threshold") or 0.72))
    test_case = LLMTestCase(
        input="Evaluate a completed Study Anything learning session quality report.",
        actual_output=json.dumps(report, ensure_ascii=False, sort_keys=True),
        expected_output="All required gates pass and quality_score meets threshold.",
    )
    metric.measure(test_case)
    return {
        "status": "ok" if metric.is_successful() else "failed",
        "tool": "deepeval",
        "framework": "DeepEval",
        "metric": metric.__name__,
        "quality_score": metric.score,
        "threshold": metric.threshold,
        "reason": metric.reason,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--allow-native-fallback",
        action="store_true",
        help="Return a native deterministic result when DeepEval is unavailable.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    api_base = args.api_base.rstrip("/")
    report = request_json(
        f"{api_base}/v1/sessions/{args.session_id}/agent-eval/quality",
        timeout=args.timeout_seconds,
    )
    if report.get("schema_version") != "agent-quality-eval-v1":
        raise RuntimeError(f"Unexpected quality eval schema: {report.get('schema_version')}")
    try:
        result = run_with_deepeval(report)
    except ModuleNotFoundError:
        if not args.allow_native_fallback:
            result = {
                "status": "skipped",
                "tool": "deepeval",
                "reason": "deepeval is not installed. Install the eval extra or use --allow-native-fallback.",
                "quality_score": report.get("quality_score"),
                "threshold": report.get("threshold"),
            }
        else:
            result = run_without_deepeval(report)
    result["schema_version"] = "study-anything-deepeval-result-v1"
    result["session_id"] = args.session_id
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"study_anything_quality_eval failed: {exc}", file=sys.stderr)
        sys.exit(1)
