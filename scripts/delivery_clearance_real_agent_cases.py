#!/usr/bin/env python3
"""Build the frozen real-Agent delivery review set from public source files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.benchmark.real_agent_cases import (  # noqa: E402
    build_real_agent_case_set,
    load_real_agent_protocol,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--protocol",
        default=str(ROOT / "docs" / "evaluation" / "real-agent-v0.1-protocol.json"),
    )
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--issue-responses", required=True)
    parser.add_argument(
        "--output",
        default=str(ROOT / "validation" / "results" / "real-agent-v0.1"),
    )
    parser.add_argument(
        "--material-output",
        default=str(
            ROOT / ".delivery-clearance" / "benchmarks" / "real-agent-v0.1" / "reviewer-materials"
        ),
    )
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    result = build_real_agent_case_set(
        protocol=load_real_agent_protocol(Path(args.protocol).expanduser().resolve()),
        predictions_path=Path(args.predictions).expanduser().resolve(),
        results_path=Path(args.results).expanduser().resolve(),
        issue_response_dir=Path(args.issue_responses).expanduser().resolve(),
        output_dir=Path(args.output).expanduser().resolve(),
        material_output_dir=Path(args.material_output).expanduser().resolve(),
        replace=args.replace,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
