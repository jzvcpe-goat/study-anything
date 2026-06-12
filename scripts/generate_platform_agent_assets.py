#!/usr/bin/env python3
"""Generate platform-agent wrapper assets from the Study Anything tool manifest."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "platform" / "study-anything-platform-tools.json"
OUTPUT_DIR = ROOT / "platform" / "generated"
OPENAPI_PATH = OUTPUT_DIR / "study-anything-platform-openapi.json"
OPENAI_TOOLS_PATH = OUTPUT_DIR / "study-anything-openai-tools.json"
CATALOG_PATH = OUTPUT_DIR / "study-anything-tool-catalog.md"
PATH_PARAM_RE = re.compile(r"{([^}]+)}")


class AssetGenerationError(RuntimeError):
    """Readable generation failure."""


def load_manifest(path: Path = MANIFEST_PATH) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AssetGenerationError(f"Cannot read manifest at {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise AssetGenerationError(f"Manifest is not valid JSON: {exc}") from exc


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def path_params(path_template: str) -> List[str]:
    return PATH_PARAM_RE.findall(path_template)


def schema_without_properties(schema: Dict[str, Any], names: Iterable[str]) -> Dict[str, Any]:
    names = set(names)
    cloned = copy.deepcopy(schema)
    properties = cloned.get("properties")
    if isinstance(properties, dict):
        for name in names:
            properties.pop(name, None)
    required = cloned.get("required")
    if isinstance(required, list):
        cloned["required"] = [name for name in required if name not in names]
        if not cloned["required"]:
            cloned.pop("required")
    return cloned


def parameter_for(name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "in": "path",
        "required": True,
        "schema": {"type": "string", "minLength": 1},
    }


def operation_for(tool: Dict[str, Any]) -> Dict[str, Any]:
    params = path_params(tool["path_template"])
    operation: Dict[str, Any] = {
        "operationId": tool["name"],
        "summary": tool["description"],
        "description": tool["description"],
        "parameters": [parameter_for(name) for name in params],
        "responses": {
            "200": {
                "description": "Study Anything tool response. See docs/api.md for endpoint-specific response details.",
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            "400": {"description": "Bad request"},
            "404": {"description": "Session or resource not found"},
            "409": {"description": "Workflow state conflict"},
            "503": {"description": "Optional dependency unavailable"},
        },
        "x-study-anything-output-requirements": tool.get("output_requirements", []),
        "x-study-anything-privacy": tool.get("privacy", {}),
    }
    if tool["method"] == "POST":
        body_schema = schema_without_properties(tool["input_schema"], params)
        operation["requestBody"] = {
            "required": bool(body_schema.get("required") or body_schema.get("properties")),
            "content": {"application/json": {"schema": body_schema}},
        }
    return operation


def build_openapi(manifest: Dict[str, Any]) -> Dict[str, Any]:
    paths: Dict[str, Any] = {}
    for tool in manifest["tools"]:
        path = tool["path_template"]
        method = tool["method"].lower()
        paths.setdefault(path, {})[method] = operation_for(tool)
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Study Anything Platform Agent Tools",
            "version": manifest["schema_version"],
            "description": manifest["description"],
        },
        "servers": [
            {
                "url": manifest.get("default_api_base", "http://127.0.0.1:8000"),
                "description": "Default local Study Anything API",
            }
        ],
        "paths": paths,
        "x-study-anything-manifest": {
            "schema_version": manifest["schema_version"],
            "name": manifest["name"],
            "api_base_env": manifest.get("api_base_env", "STUDY_ANYTHING_API_BASE"),
            "privacy_contract": manifest.get("privacy_contract", {}),
            "acceptance_evidence": manifest.get("acceptance_evidence", {}),
        },
    }


def build_openai_tools(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": (
                    f"{tool['description']} Method: {tool['method']} {tool['path_template']}."
                ),
                "parameters": copy.deepcopy(tool["input_schema"]),
            },
        }
        for tool in manifest["tools"]
    ]


def markdown_list(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def evidence_commands(evidence: Dict[str, Any]) -> List[str]:
    keys = [
        "local_verification_command",
        "openai_compatible_gateway_dry_run_command",
        "gateway_only_command",
    ]
    return [str(evidence[key]) for key in keys if evidence.get(key)]


def build_catalog(manifest: Dict[str, Any]) -> str:
    acceptance_evidence = manifest.get("acceptance_evidence", {})
    lines: List[str] = [
        "# Study Anything Platform Tool Catalog",
        "",
        "Generated from `platform/study-anything-platform-tools.json`.",
        "",
        "## Purpose",
        "",
        manifest["description"],
        "",
        "## Privacy Contract",
        "",
        "The platform Agent owns browsing, files, external data, application tooling, model credentials, and user-facing conversation.",
        "Study Anything owns source-bound learning state, workflow orchestration, output validation, mastery, HITL, redacted audit, and redacted eval artifacts.",
        "",
        "Never log or share:",
        "",
        markdown_list(manifest.get("privacy_contract", {}).get("must_not_log_or_share", [])),
        "",
        "## Generated Assets",
        "",
        "- `study-anything-platform-openapi.json`: constrained OpenAPI 3.1 document for HTTP tool importers.",
        "- `study-anything-openai-tools.json`: OpenAI-compatible function tool definitions for Kimi-compatible and other tool-calling agents.",
        "- `study-anything-tool-catalog.md`: this human-readable catalog.",
        "",
        "## Acceptance",
        "",
        "A platform wrapper is acceptable only when it completes the local verification command:",
        "",
        "```bash",
        acceptance_evidence.get(
            "local_verification_command",
            "API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_agent_tools.py",
        ),
        "```",
        "",
        "Additional gateway and release acceptance commands:",
        "",
        markdown_list(evidence_commands(acceptance_evidence)) or "- none",
        "",
        "## Tools",
        "",
    ]
    for tool in manifest["tools"]:
        lines.extend(
            [
                f"### `{tool['name']}`",
                "",
                f"- Method: `{tool['method']}`",
                f"- Path: `{tool['path_template']}`",
                f"- Description: {tool['description']}",
                "",
                "Output requirements:",
                "",
                markdown_list(tool.get("output_requirements", [])) or "- none",
                "",
                "Privacy:",
                "",
                "```json",
                dump_json(tool.get("privacy", {})).rstrip(),
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def generated_assets(manifest: Dict[str, Any]) -> List[Tuple[Path, str]]:
    return [
        (OPENAPI_PATH, dump_json(build_openapi(manifest))),
        (OPENAI_TOOLS_PATH, dump_json(build_openai_tools(manifest))),
        (CATALOG_PATH, build_catalog(manifest)),
    ]


def write_assets(manifest: Dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in generated_assets(manifest):
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


def check_assets(manifest: Dict[str, Any]) -> None:
    missing: List[str] = []
    stale: List[str] = []
    for path, expected in generated_assets(manifest):
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            stale.append(str(path.relative_to(ROOT)))
    if missing or stale:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if stale:
            details.append(f"stale={stale}")
        raise AssetGenerationError(
            "Generated platform assets are out of date. Run "
            "`python3 scripts/generate_platform_agent_assets.py`. "
            + " ".join(details)
        )
    print("ok    generated platform assets are up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated assets are missing or stale")
    args = parser.parse_args()
    manifest = load_manifest()
    if args.check:
        check_assets(manifest)
    else:
        write_assets(manifest)


if __name__ == "__main__":
    try:
        main()
    except AssetGenerationError as exc:
        print(f"generate_platform_agent_assets failed: {exc}", file=sys.stderr)
        sys.exit(1)
