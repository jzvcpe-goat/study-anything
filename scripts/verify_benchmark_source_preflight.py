#!/usr/bin/env python3
"""Verify source-preflight contracts without requiring public benchmark downloads."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.benchmark.models import (  # noqa: E402
    BenchmarkSource,
    SourcePreflightReceiptV1,
)
from study_anything.cbb.benchmark.source_preflight import (  # noqa: E402
    build_source_preflight,
)
from study_anything.cbb.protocol.canonical import assert_safe_metadata  # noqa: E402


REPORT_PATH = (
    ROOT
    / "platform"
    / "generated"
    / "delivery-clearance-benchmark-source-preflight.json"
)
FIXED_TIME = "2026-07-12T00:00:00Z"


def _rejects(action: Callable[[], object], expected: str) -> bool:
    try:
        action()
    except (ValidationError, ValueError) as exc:
        return expected in str(exc)
    return False


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp:
        receipt = build_source_preflight(
            BenchmarkSource.AGENTDOJO,
            source_root=Path(temp),
            generated_at=FIXED_TIME,
        )
    payload = receipt.model_dump(mode="json")
    forged_ready = deepcopy(payload)
    forged_ready["execution_readiness"] = "execution_ready"
    missing_blockers = deepcopy(payload)
    missing_blockers["blocker_codes"] = []
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    checks = {
        "missing_checkout_is_not_ready": receipt.execution_readiness
        == "source_unavailable",
        "missing_checkout_has_no_observed_revisions": (
            receipt.observed_task_data_revision is None
            and receipt.observed_scorer_revision is None
        ),
        "missing_checkout_has_blockers": bool(receipt.blocker_codes),
        "forged_execution_ready_rejected": _rejects(
            lambda: SourcePreflightReceiptV1.model_validate(forged_ready),
            "cannot contain blockers",
        ),
        "missing_blocker_ledger_rejected": _rejects(
            lambda: SourcePreflightReceiptV1.model_validate(missing_blockers),
            "blocker codes do not match checks",
        ),
        "receipt_excludes_local_absolute_paths": "/Users/" not in serialized
        and "/private/tmp/" not in serialized,
        "receipt_does_not_claim_scorer_execution": (
            "official_scorer_executed" not in payload
            and receipt.official_scorer_present is False
        ),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise RuntimeError(f"source preflight verifier failed: {failed}")
    report = {
        "schema_version": "benchmark-source-preflight-verification-v1",
        "status": "pass",
        "checks": checks,
        "claim_boundary": (
            "This verifier checks preflight contract behavior. It does not acquire "
            "public sources, execute official scorers, or establish an observed effect."
        ),
    }
    assert_safe_metadata(report, label="source preflight verifier report")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check == args.write:
        raise SystemExit("Choose exactly one of --check or --write.")
    content = json.dumps(build_report(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.write:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(content, encoding="utf-8")
    elif not REPORT_PATH.is_file() or REPORT_PATH.read_text(encoding="utf-8") != content:
        raise SystemExit(
            "Benchmark source-preflight report is stale. Run: "
            "python3 scripts/verify_benchmark_source_preflight.py --write"
        )
    print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
