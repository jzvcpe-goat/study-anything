#!/usr/bin/env python3
"""Generate local Cognitive Loop advisory code review evidence."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REVIEW_MODULE_PATH = ROOT / "apps" / "api" / "study_anything" / "core" / "cognitive_loop_review.py"


def _load_review_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "study_anything_cognitive_loop_review", REVIEW_MODULE_PATH
    )
    if spec is None or spec.loader is None:
        raise CognitiveLoopReviewCliError(f"Cannot load Cognitive Loop review module: {REVIEW_MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CognitiveLoopReviewCliError(RuntimeError):
    """Readable CLI failure."""


review = _load_review_module()


def _root(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve()


def _dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _collect_changes(args: argparse.Namespace) -> tuple[list[review.ReviewChange], str]:
    root = _root(args)
    if args.pr_summary:
        changes = review.load_pr_summary_changes(
            Path(args.pr_summary),
            base_ref=args.base,
            head_ref=args.head,
        )
        return changes, "pr_summary"
    if args.base or args.head:
        changes = review.collect_git_review_changes(
            root,
            base_ref=args.base,
            head_ref=args.head,
        )
        return changes, "git_diff"
    changes = review.collect_git_review_changes(root)
    return changes, "worktree_diff"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository or project root.")
    parser.add_argument("--base", help="Base git ref. Example: main.")
    parser.add_argument("--head", help="Head git ref. Example: HEAD.")
    parser.add_argument(
        "--pr-summary",
        help="Optional redacted PR summary JSON containing changed_files, not raw patches.",
    )
    parser.add_argument("--html", action="store_true", help="Write a static HTML review artifact.")
    parser.add_argument(
        "--output",
        default=".cognitive-loop/artifacts/cognitive-loop-review.html",
        help="HTML output path. Defaults under .cognitive-loop/artifacts.",
    )
    parser.add_argument(
        "--json-output",
        default=".cognitive-loop/events/cognitive-loop-review.json",
        help="JSON output path. Defaults under .cognitive-loop/events.",
    )
    parser.add_argument(
        "--reviewer",
        default="fake-deterministic-reviewer",
        help="Reviewer id. v0.1 supports deterministic fake reviewer evidence only.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON even when --html is used.")
    args = parser.parse_args()

    root = _root(args)
    changes, source = _collect_changes(args)
    report = review.build_review_artifact(
        root,
        changes=changes,
        source=source,
        base_ref=args.base,
        head_ref=args.head,
        reviewer_id=args.reviewer,
        artifact_ref=args.output,
    )

    wrote: list[str] = []
    json_output = Path(args.json_output)
    if not json_output.is_absolute():
        json_output = root / json_output
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(_dump(report), encoding="utf-8")
    wrote.append(str(json_output))

    if args.html:
        html_output = Path(args.output)
        if not html_output.is_absolute():
            html_output = root / html_output
        html_output.parent.mkdir(parents=True, exist_ok=True)
        html_output.write_text(review.render_review_artifact_html(report), encoding="utf-8")
        wrote.append(str(html_output))

    if args.html and not args.json:
        for path in wrote:
            print(f"wrote: {path}")
        return 0
    print(_dump(report), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CognitiveLoopReviewCliError, review.CognitiveLoopReviewError) as exc:
        raise SystemExit(f"error: {exc}") from exc
