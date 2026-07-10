#!/usr/bin/env python3
"""Verify that the canonical CBB trust kernel has no agentic runtime authority."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
KERNEL_FILES = (
    ROOT / "apps" / "api" / "study_anything" / "cbb" / "kernel" / "__init__.py",
    ROOT / "apps" / "api" / "study_anything" / "cbb" / "kernel" / "gate.py",
)
DEFAULT_REPORT = ROOT / "platform" / "generated" / "study-anything-cbb-runtime-isolation.json"
REPORT_SCHEMA_VERSION = "cbb-runtime-isolation-verification-v1"
BANNED_IMPORT_ROOTS = {
    "aiohttp",
    "anthropic",
    "chromadb",
    "httpx",
    "langchain",
    "openai",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}
BANNED_CALL_NAMES = {"__import__", "compile", "eval", "exec", "open"}
BANNED_ATTRIBUTE_CALLS = {
    "Popen",
    "connect",
    "open",
    "read_bytes",
    "read_text",
    "run",
    "send",
    "urlopen",
    "write_bytes",
    "write_text",
}


def _json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _scan(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
                if alias.name.split(".")[0] in BANNED_IMPORT_ROOTS:
                    violations.append(f"banned import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(module)
            root = module.split(".")[0]
            if root in BANNED_IMPORT_ROOTS or module.startswith("study_anything.core"):
                violations.append(f"banned import: {module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BANNED_CALL_NAMES:
                violations.append(f"banned call: {node.func.id}")
            elif isinstance(node.func, ast.Attribute) and node.func.attr in BANNED_ATTRIBUTE_CALLS:
                violations.append(f"banned attribute call: {node.func.attr}")
    if violations:
        raise RuntimeError(f"{path.name}: " + "; ".join(sorted(set(violations))))
    return {
        "path": str(path.relative_to(ROOT)),
        "imports": sorted(set(imports)),
        "violations": [],
    }


def build_report() -> dict[str, Any]:
    files = [_scan(path) for path in KERNEL_FILES]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "passed",
        "boundary": {
            "model_or_provider_sdk_imports": False,
            "network_imports": False,
            "retrieval_imports": False,
            "subprocess_or_tool_execution": False,
            "filesystem_io": False,
            "legacy_runtime_dependency": False,
        },
        "files": files,
        "claim_boundary": (
            "This verifier proves static runtime isolation for the canonical kernel "
            "files only; it is not a production sandbox or external security audit."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("choose exactly one of --check or --write")
    report = build_report()
    target = Path(args.report)
    expected = _json_text(report)
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected, encoding="utf-8")
    elif not target.exists() or target.read_text(encoding="utf-8") != expected:
        raise RuntimeError(
            "CBB runtime isolation report is stale; run verify_cbb_runtime_isolation.py --write"
        )
    print(expected, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
