"""CLI for metadata-only plugin evidence evaluation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from study_anything.cbb.plugin_evidence.evaluator import evaluate_plugin_evidence
from study_anything.cbb.plugin_evidence.models import PluginEvidenceBundleV1
from study_anything.cbb.protocol.canonical import (
    CanonicalProtocolError,
    assert_safe_metadata,
    pretty_json,
)


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=("Evaluate a metadata-only plugin evidence bundle for personal-local use.")
    )
    parser.add_argument("input", type=Path, help="Plugin evidence bundle JSON")
    parser.add_argument("--output", type=Path, help="Optional decision receipt path")
    args = parser.parse_args()

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        assert_safe_metadata(payload, label="plugin evidence input")
        bundle = PluginEvidenceBundleV1.model_validate(payload)
        decision = evaluate_plugin_evidence(bundle, evaluated_at=_now())
    except (OSError, json.JSONDecodeError, ValidationError, CanonicalProtocolError) as exc:
        print(f"plugin evidence input rejected: {exc}", file=sys.stderr)
        return 2

    rendered = pretty_json(decision)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if decision.status == "allow_personal_local":
        return 0
    if decision.status == "needs_evidence":
        return 3
    return 4
