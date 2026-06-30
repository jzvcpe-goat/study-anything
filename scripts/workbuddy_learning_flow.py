#!/usr/bin/env python3
"""Run the WorkBuddy inline Study Anything learning flow."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from study_anything.adapters.workbuddy_inline import (  # noqa: E402
    INPUT_SCHEMA_VERSION,
    WorkBuddyInlineError,
    build_workbuddy_learning_package,
    dump_json,
    sanitize_runtime_env,
)
from study_anything import __version__  # noqa: E402


DEMO_CASES = {
    "deepseek-pm-interview": ROOT
    / "fixtures"
    / "workbuddy-learning-flow"
    / "deepseek-pm-interview"
    / "input.json"
}
REQUIRED_FEATURE_FILES = (
    "apps/api/study_anything/adapters/workbuddy_inline.py",
    "platform/schemas/workbuddy-learning-input-v1.schema.json",
    "platform/schemas/workbuddy-learning-output-v1.schema.json",
    "scripts/verify_workbuddy_inline_learning_flow.py",
)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise WorkBuddyInlineError(f"Cannot read JSON input {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkBuddyInlineError(f"JSON object expected: {path}")
    return payload


def write_optional(path_value: str | None, content: str) -> None:
    if not path_value:
        return
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run from a WorkBuddy learning input JSON file.")
    run.add_argument("--input", required=True, help=f"Path to {INPUT_SCHEMA_VERSION} JSON.")
    run.add_argument("--output", help="Optional JSON output path.")
    run.add_argument("--markdown", help="Optional Markdown output path.")
    run.add_argument("--data-dir", help="Optional data-dir hint; the inline flow does not create it.")
    run.add_argument(
        "--allow-deterministic-input",
        action="store_true",
        help="Allow deterministic fixture input. Do not use for real learner sessions.",
    )

    demo = subparsers.add_parser("demo", help="Run a deterministic WorkBuddy inline demo case.")
    demo.add_argument("--case", choices=sorted(DEMO_CASES), default="deepseek-pm-interview")
    demo.add_argument("--output", help="Optional JSON output path.")
    demo.add_argument("--markdown", help="Optional Markdown output path.")
    demo.add_argument("--data-dir", help="Optional data-dir hint; the inline flow does not create it.")

    doctor = subparsers.add_parser("doctor", help="Check WorkBuddy inline runtime capabilities.")
    doctor.add_argument("--data-dir", help="Optional data-dir hint; the inline flow does not create it.")
    return parser


def runtime_env() -> tuple[dict[str, str], list[str]]:
    sanitized, removed = sanitize_runtime_env(os.environ)
    for key in removed:
        os.environ.pop(key, None)
    return sanitized, removed


def run_command(args: argparse.Namespace) -> dict[str, Any]:
    payload = read_json(Path(args.input))
    env, removed = runtime_env()
    return build_workbuddy_learning_package(
        payload,
        data_dir=args.data_dir,
        env=env,
        require_platform_agent=not args.allow_deterministic_input,
        proxy_env_removed=removed,
    )


def demo_command(args: argparse.Namespace) -> dict[str, Any]:
    payload = read_json(DEMO_CASES[args.case])
    env, removed = runtime_env()
    return build_workbuddy_learning_package(
        payload,
        data_dir=args.data_dir,
        env=env,
        require_platform_agent=False,
        proxy_env_removed=removed,
    )


def doctor_command(args: argparse.Namespace) -> dict[str, Any]:
    env, removed = runtime_env()
    missing = [path for path in REQUIRED_FEATURE_FILES if not (ROOT / path).is_file()]
    return {
        "schema_version": "workbuddy-inline-runtime-doctor-v1",
        "status": "ok" if not missing else "needs_update",
        "product_version": __version__,
        "capability_version": "workbuddy-inline-v1",
        "feature_files_present": not missing,
        "missing_feature_files": missing,
        "data_dir_strategy": "explicit_parameter"
        if args.data_dir
        else (
            "study_anything_data_dir"
            if env.get("STUDY_ANYTHING_DATA_DIR")
            else "workbuddy_data_dir"
            if env.get("WORKBUDDY_DATA_DIR")
            else "xdg_data_home"
            if env.get("XDG_DATA_HOME")
            else "workspace_dot_workbuddy"
        ),
        "proxy_env_sanitized": True,
        "proxy_env_removed_count": len(removed),
        "git_pull_required_inside_workbuddy": False,
        "model_keys_required_by_study_anything": False,
        "notes": [
            "0.3.31-alpha is the product release train; WorkBuddy inline is a capability, not a separate runtime version.",
            "If feature_files_present is false, import the latest plugin pack or update the checkout outside the WorkBuddy sandbox.",
            "Real teaching quality requires WorkBuddy/Kimi to generate workbuddy_teaching, workbuddy_quiz, and workbuddy_grading before `run`.",
        ],
    }


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.command == "run":
        output = run_command(args)
    elif args.command == "demo":
        output = demo_command(args)
    elif args.command == "doctor":
        output = doctor_command(args)
    else:  # pragma: no cover - argparse prevents this
        raise WorkBuddyInlineError(f"Unsupported command: {args.command}")

    serialized = dump_json(output)
    write_optional(getattr(args, "output", None), serialized)
    if "exports" in output:
        write_optional(getattr(args, "markdown", None), str(output["exports"]["markdown_text"]))
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"workbuddy_learning_flow failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
