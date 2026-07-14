#!/usr/bin/env python3
"""Replay the bounded real-project Delivery Clearance evaluation set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.cbb.benchmark.project_scenarios import (  # noqa: E402
    default_python_executable,
    load_scenario_set,
    run_real_project_scenarios,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(ROOT))
    parser.add_argument(
        "--scenario-set",
        default=str(ROOT / "docs" / "evaluation" / "real-project-v0.1-scenarios.json"),
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "validation" / "results" / "real-project-v0.1"),
    )
    parser.add_argument("--python")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    scenario_path = Path(args.scenario_set).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    python_executable = (
        Path(args.python).expanduser().resolve() if args.python else default_python_executable(repo)
    )
    report = run_real_project_scenarios(
        source_repo=repo,
        scenario_set=load_scenario_set(scenario_path),
        output_dir=output,
        python_executable=python_executable,
        replace=args.replace,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
