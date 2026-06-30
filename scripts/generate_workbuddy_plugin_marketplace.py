#!/usr/bin/env python3
"""Generate the CodeBuddy/WorkBuddy marketplace plugin files and evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.3.31-alpha"
MARKETPLACE_PATH = ROOT / ".codebuddy-plugin" / "marketplace.json"
PLUGIN_ROOT = ROOT / "plugins" / "study-anything"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".codebuddy-plugin" / "plugin.json"
PLUGIN_README_PATH = PLUGIN_ROOT / "README.md"
PLUGIN_SKILL_PATH = PLUGIN_ROOT / "skills" / "study-anything" / "SKILL.md"
COMMAND_PATHS = {
    "start": PLUGIN_ROOT / "commands" / "start.md",
    "learn": PLUGIN_ROOT / "commands" / "learn.md",
    "diagnose": PLUGIN_ROOT / "commands" / "diagnose.md",
    "export": PLUGIN_ROOT / "commands" / "export.md",
}
REPORT_PATH = ROOT / "platform" / "generated" / "study-anything-workbuddy-codebuddy-marketplace.json"
MARKDOWN_PATH = ROOT / "platform" / "generated" / "study-anything-workbuddy-codebuddy-marketplace.md"
SCHEMA_VERSION = "workbuddy-codebuddy-marketplace-v1"

REQUIRED_PUBLIC_REFS = (
    ".codebuddy-plugin/marketplace.json",
    "plugins/study-anything/.codebuddy-plugin/plugin.json",
    "plugins/study-anything/skills/study-anything/SKILL.md",
    "plugins/study-anything/commands/start.md",
    "plugins/study-anything/commands/learn.md",
    "plugins/study-anything/commands/diagnose.md",
    "plugins/study-anything/commands/export.md",
    "docs/use-with-workbuddy.md",
    "scripts/workbuddy_learning_flow.py",
    "scripts/verify_workbuddy_inline_learning_flow.py",
    "platform/schemas/workbuddy-learning-input-v1.schema.json",
    "platform/schemas/workbuddy-learning-output-v1.schema.json",
    "fixtures/workbuddy-learning-flow/deepseek-pm-interview/input.json",
    "fixtures/workbuddy-learning-flow/deepseek-pm-interview/expected-boundary.json",
    "platform/generated/study-anything-workbuddy-inline-learning-flow.json",
    "platform/generated/study-anything-platform-openapi.json",
)

FORBIDDEN_PATTERNS = (
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_./+=-]{8,}"),
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/private/(?:tmp|var/folders)/[^\s\"']+"),
)
FORBIDDEN_LITERALS = (
    "OPENAI_API_KEY",
    "MOONSHOT_API_KEY",
    "AGENT_LLM_API_KEY=",
    "raw_source_text=",
    "learner_answer=",
    "Private source text:",
    "Private answer:",
)


class WorkBuddyPluginMarketplaceError(RuntimeError):
    """Readable WorkBuddy/CodeBuddy marketplace generation failure."""


def dump_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


OWNER = {
    "name": "Study Anything Maintainers",
    "url": "https://github.com/jzvcpe-goat/study-anything",
}

KEYWORDS = [
    "study-anything",
    "learning",
    "cognitive-loop",
    "workbuddy",
    "codebuddy",
    "local-first",
    "openapi",
]


def marketplace_payload() -> dict[str, Any]:
    return {
        "name": "study-anything",
        "description": "Study Anything local-first learning and cognitive-loop tools for CodeBuddy/WorkBuddy.",
        "version": VERSION,
        "owner": OWNER,
        "plugins": [
            {
                "name": "study-anything",
                "source": "./plugins/study-anything",
                "description": (
                    "Install Study Anything as a CodeBuddy/WorkBuddy plugin that runs an inline "
                    "learning workflow first, with OpenAPI/local HTTP kept as a fallback."
                ),
                "version": VERSION,
                "author": OWNER,
                "homepage": "https://github.com/jzvcpe-goat/study-anything",
                "repository": "https://github.com/jzvcpe-goat/study-anything",
                "license": "Apache-2.0",
                "keywords": KEYWORDS,
                "category": "AI Agents",
                "strict": True,
                "commands": ["commands"],
                "skills": ["skills"],
            }
        ],
    }


def plugin_payload() -> dict[str, Any]:
    return {
        "name": "study-anything",
        "version": VERSION,
        "description": (
            "Local-first learning workflow kernel for CodeBuddy/WorkBuddy. WorkBuddy owns the "
            "real model, search, files, and conversation; Study Anything records source-bound "
            "learning state, mastery, evidence, and exports without storing model keys."
        ),
        "author": OWNER,
        "homepage": "https://github.com/jzvcpe-goat/study-anything",
        "repository": "https://github.com/jzvcpe-goat/study-anything",
        "license": "Apache-2.0",
        "keywords": KEYWORDS,
        "category": "AI Agents",
        "commands": ["commands"],
        "skills": ["skills"],
        "metadata": {
            "inline_runtime": {
                "default_mode": "workbuddy_inline",
                "script": "scripts/workbuddy_learning_flow.py",
                "input_schema": "platform/schemas/workbuddy-learning-input-v1.schema.json",
                "output_schema": "platform/schemas/workbuddy-learning-output-v1.schema.json",
                "verification": "python3 scripts/verify_workbuddy_inline_learning_flow.py --check",
            },
            "local_runtime": {
                "default_api_base": "http://127.0.0.1:8000",
                "one_click": "./START_HERE.command",
                "launch": "./scripts/launch_skill_mode.sh",
                "stop": "./scripts/stop_skill_mode.sh",
            },
            "tool_contracts": {
                "inline": "scripts/workbuddy_learning_flow.py",
                "openapi": "platform/generated/study-anything-platform-openapi.json",
                "local_http": "fallback: http://127.0.0.1:8000",
                "mcp": "planned extension; not shipped by this plugin",
            },
            "privacy_boundaries": {
                "real_model_keys": "owned by CodeBuddy/WorkBuddy or the user's private Agent",
                "study_anything_stores": "local learning state, validation evidence, and redacted audit metadata",
            },
        },
    }


PLUGIN_README = """# Study Anything CodeBuddy/WorkBuddy Plugin

This plugin lets CodeBuddy/WorkBuddy use Study Anything as a local-first
learning workflow kernel. The default path is inline: CodeBuddy/WorkBuddy owns
model choice, browser access, external tools, files, and private credentials;
Study Anything records source-bound learning state, mastery, audit/eval
evidence, and exports. OpenAPI/local HTTP remains available as a fallback.

## Install

```text
/plugin marketplace add jzvcpe-goat/study-anything
/plugin install study-anything@study-anything
```

For local development:

```text
/plugin marketplace add ./path/to/study-anything
/plugin install study-anything@study-anything
```

## Commands

- `/study-anything:start` checks inline mode first and explains HTTP fallback.
- `/study-anything:learn` turns WorkBuddy-generated teaching, quiz, and grading into a source-bound learning package.
- `/study-anything:diagnose` checks local runtime, endpoints, and plugin assets.
- `/study-anything:export` exports Obsidian, NotebookLM, or learning-package handoff evidence.

## Default Inline Runtime

```bash
python3 scripts/workbuddy_learning_flow.py demo --case deepseek-pm-interview
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
```

## HTTP Fallback

If you need HTTP tools, run Study Anything from the repository checkout:

```bash
./START_HERE.command
python3 scripts/study_anything_cli.py health
```

If your workspace can import OpenAPI tools, import:

```text
platform/generated/study-anything-platform-openapi.json
```

The default local API is `http://127.0.0.1:8000`. Do not use HTTP as the default
inside WorkBuddy sandboxes that do not preserve background processes.
"""

PLUGIN_SKILL = """---
name: study-anything
description: Use when CodeBuddy or WorkBuddy should run a source-bound learning workflow for requests like system learning, interview preparation, help me master this topic, build a study plan, quiz me, or review this material. Prefer the WorkBuddy inline flow where WorkBuddy owns real model/search/file/context work and Study Anything records learning state, mastery, evidence, and exports. Use OpenAPI/local HTTP only as fallback. Do not store model keys in Study Anything.
---

# Study Anything For CodeBuddy/WorkBuddy

Study Anything is the learning workflow kernel. CodeBuddy/WorkBuddy remains the
main platform Agent: it owns real model credentials, browsing, external apps,
files, visualization, and private tool use. Study Anything owns local learning
workflow integrity, source binding, hidden session refs, mastery, audit/eval
evidence, and exports.

## Trigger Phrases

Use this skill when the user says things like:

- "systematically teach me ..."
- "prepare me for an interview ..."
- "help me master this topic"
- "build a study plan"
- "quiz me on this material"
- "review this source and turn it into learning cards"

## Default Inline Flow

1. WorkBuddy collects source material, user context, and any visual/search/file context.
2. WorkBuddy uses its own model to produce teaching claims, glossary terms, quiz items, and grading feedback.
3. Call Study Anything inline:

```bash
python3 scripts/workbuddy_learning_flow.py run --input workbuddy-learning-input.json --output workbuddy-learning-output.json --markdown study-card.md
```

4. Keep `session_ref` in hidden WorkBuddy context. Do not ask the user to manage it.
5. Return the teaching summary, quiz, feedback, mastery, and export options conversationally.

Validate the inline path:

```bash
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
```

The inline path does not start uvicorn, bind localhost, require a background
process, or ask for real model API keys.

## HTTP Fallback

Use HTTP only when the workspace can reliably reach a local or private endpoint.
From the Study Anything checkout:

```bash
./START_HERE.command
python3 scripts/study_anything_cli.py health
```

If a background server will not persist in this host, use the bounded demo:

```bash
./scripts/run_skill_mode_demo.sh
```

Use `STUDY_ANYTHING_API_BASE` or `--api-base` when the fallback runtime is not at
`http://127.0.0.1:8000`.

## Tool Contract

Fallback WorkBuddy/CodeBuddy import asset:

```text
platform/generated/study-anything-platform-openapi.json
```

Fallback local HTTP flow:

```bash
python3 scripts/study_anything_cli.py start --title "Topic" --text "Source text" --reference "source"
python3 scripts/study_anything_cli.py teach <SESSION_ID> --layer overview
python3 scripts/study_anything_cli.py answer <SESSION_ID> --text "My answer"
python3 scripts/study_anything_cli.py mastery <SESSION_ID>
```

MCP is a planned extension point in this repository, not a shipped runtime in
this plugin. Do not claim MCP support until an explicit MCP server is added.

## Privacy Boundary

Do not put raw private source text, learner answers, grading feedback, generated
private insights, Agent endpoints, Agent metadata, API keys, model secrets, or
browser/video/app private context into shared marketplace metadata, issue
reports, public logs, or release assets.

Study Anything may store local learning state and redacted evidence in the
operator's local runtime. It must not store real model provider keys.
"""

COMMANDS = {
    "start": """# Start Study Anything

Check the Study Anything WorkBuddy inline flow and explain HTTP fallback.

1. Preferred inline check:

```bash
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
```

2. Run the deterministic WorkBuddy demo:

```bash
python3 scripts/workbuddy_learning_flow.py demo --case deepseek-pm-interview
```

3. Use HTTP fallback only when the host can preserve a local runtime:

```bash
./START_HERE.command
python3 scripts/study_anything_cli.py health
```

If the host cannot keep background processes alive, do not force HTTP. Use the
inline flow or the bounded demo:

```bash
./scripts/run_skill_mode_demo.sh
```

If the fallback runtime is remote or uses another port, set:

```bash
export STUDY_ANYTHING_API_BASE="http://127.0.0.1:8000"
```

Do not ask the user for model API keys for Study Anything. Real model
credentials stay inside CodeBuddy/WorkBuddy or the user's private Agent.
""",
    "learn": """# Learn With Study Anything

Use Study Anything for a WorkBuddy-owned source-bound learning loop. WorkBuddy
should gather the topic, source material, learner profile, and user answer in
conversation; then use its own model to create teaching claims, glossary terms,
quiz items, and grading feedback.

Preferred inline flow:

```bash
python3 scripts/workbuddy_learning_flow.py run \\
  --input workbuddy-learning-input.json \\
  --output workbuddy-learning-output.json \\
  --markdown study-card.md
```

For a deterministic example:

```bash
python3 scripts/workbuddy_learning_flow.py demo --case deepseek-pm-interview
```

Do not show the user raw session ids. Keep `session_ref` in WorkBuddy hidden
context and respond conversationally with overview, glossary, quiz, feedback,
mastery, and export options.

Fallback OpenAPI tool import:

```text
platform/generated/study-anything-platform-openapi.json
```

HTTP CLI fallback:

```bash
python3 scripts/study_anything_cli.py start \\
  --title "$ARGUMENTS" \\
  --text "PASTE_SOURCE_TEXT_HERE" \\
  --reference "workbuddy-source"

python3 scripts/study_anything_cli.py teach <SESSION_ID> --layer overview
python3 scripts/study_anything_cli.py teach <SESSION_ID> --layer glossary
python3 scripts/study_anything_cli.py answer <SESSION_ID> --text "USER_ANSWER"
python3 scripts/study_anything_cli.py mastery <SESSION_ID>
```

Keep raw private source text and learner answers out of public logs or
marketplace evidence.
""",
    "diagnose": """# Diagnose Study Anything

Run local diagnostics when CodeBuddy/WorkBuddy cannot run Study Anything.

```bash
python3 scripts/verify_workbuddy_inline_learning_flow.py --check
python3 scripts/study_anything_cli.py health
python3 scripts/diagnose_adoption.py
python3 scripts/verify_platform_agent_tools.py
python3 scripts/verify_workbuddy_plugin_marketplace.py --check
```

Common fixes:

- If inline flow passes but HTTP fails, keep using inline mode in WorkBuddy.
- Start the fallback runtime with `./START_HERE.command` or `./scripts/launch_skill_mode.sh`.
- If localhost is blocked by the host platform, use a private reachable HTTP endpoint.
- If dependency install is slow, configure `PIP_INDEX_URL` or retry from a normal terminal.
- If Docker is unavailable, use Skill Mode first.

Only share redacted diagnostic output. Do not share real model keys, Agent
endpoint secrets, raw source text, learner answers, or private browser/app data.
""",
    "export": """# Export Study Anything Evidence

Export compact learning evidence for Obsidian, NotebookLM, local archive, or a
platform Agent handoff.

After a WorkBuddy inline session is complete, use the generated Markdown and
JSON output:

```bash
python3 scripts/workbuddy_learning_flow.py run --input workbuddy-learning-input.json --output workbuddy-learning-output.json --markdown study-card.md
```

For HTTP fallback sessions, use the Study Anything CLI or imported HTTP tools:

```bash
python3 scripts/study_anything_cli.py mastery <SESSION_ID>
python3 scripts/study_anything_cli.py events <SESSION_ID>
```

For richer platform checks, run:

```bash
API_BASE="${STUDY_ANYTHING_API_BASE:-http://127.0.0.1:8000}" \\
  python3 scripts/verify_platform_agent_tools.py
```

Exported handoff evidence should include schema names, session refs, mastery
state, source references, and redacted audit/eval metadata. It must not include
raw source text, learner answers, generated private insights, Agent endpoint
secrets, or model API keys.
""",
}


def output_map() -> dict[Path, str]:
    outputs = {
        MARKETPLACE_PATH: dump_json(marketplace_payload()),
        PLUGIN_MANIFEST_PATH: dump_json(plugin_payload()),
        PLUGIN_README_PATH: PLUGIN_README,
        PLUGIN_SKILL_PATH: PLUGIN_SKILL,
    }
    for command, path in COMMAND_PATHS.items():
        outputs[path] = COMMANDS[command]
    report = build_report(outputs)
    outputs[REPORT_PATH] = dump_json(report)
    outputs[MARKDOWN_PATH] = markdown_report(report)
    return outputs


def assert_no_leaks(label: str, text: str) -> None:
    leaks = [literal for literal in FORBIDDEN_LITERALS if literal in text]
    leaks.extend(pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(text))
    if leaks:
        raise WorkBuddyPluginMarketplaceError(f"{label} contains private or secret-like text: {leaks}")


def build_report(outputs: dict[Path, str] | None = None) -> dict[str, Any]:
    if outputs is None:
        outputs = {}
    files: list[dict[str, Any]] = []
    for rel in REQUIRED_PUBLIC_REFS:
        path = ROOT / rel
        if path in outputs:
            content = outputs[path]
            exists = True
            digest = sha256_text(content)
            size = len(content.encode("utf-8"))
        else:
            exists = path.exists()
            digest = sha256_file(path) if exists and path.is_file() else None
            size = path.stat().st_size if exists and path.is_file() else None
        files.append({"path": rel, "exists": exists, "sha256": digest, "bytes": size})
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "version": VERSION,
        "marketplace": {
            "path": ".codebuddy-plugin/marketplace.json",
            "install_commands": [
                "/plugin marketplace add jzvcpe-goat/study-anything",
                "/plugin install study-anything@study-anything",
            ],
            "local_dev_commands": [
                "/plugin marketplace add ./path/to/study-anything",
                "/plugin install study-anything@study-anything",
            ],
        },
        "plugin": {
            "name": "study-anything",
            "path": "plugins/study-anything/.codebuddy-plugin/plugin.json",
            "commands": [f"/study-anything:{name}" for name in COMMAND_PATHS],
            "skill": "/study-anything:study-anything",
            "tool_contracts": {
                "inline": "scripts/workbuddy_learning_flow.py",
                "openapi": "platform/generated/study-anything-platform-openapi.json",
                "local_http": "fallback: http://127.0.0.1:8000",
                "mcp": "planned extension; not shipped by this plugin",
            },
        },
        "files": files,
        "privacy_assertions": {
            "raw_source_text_in_report": False,
            "learner_answers_in_report": False,
            "agent_endpoint_secrets_in_report": False,
            "real_model_keys_in_report": False,
            "local_absolute_paths_in_report": False,
            "marketplace_listing_ready": True,
            "mcp_runtime_shipped": False,
        },
        "verification_commands": [
            "python3 scripts/verify_workbuddy_inline_learning_flow.py --check",
            "python3 scripts/generate_workbuddy_plugin_marketplace.py --check",
            "python3 scripts/verify_workbuddy_plugin_marketplace.py --check",
        ],
    }
    assert_no_leaks("workbuddy marketplace report", json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report


def markdown_report(report: dict[str, Any]) -> str:
    rows = "\n".join(
        f"| `{item['path']}` | `{item['sha256']}` |" for item in report["files"]
    )
    commands = "\n".join(f"- `{command}`" for command in report["marketplace"]["install_commands"])
    checks = "\n".join(f"- `{command}`" for command in report["verification_commands"])
    return f"""# WorkBuddy / CodeBuddy Marketplace

Schema: `{report['schema_version']}`
Version: `{report['version']}`
Status: `{report['status']}`

## Install

{commands}

## Files

| Path | SHA-256 |
| --- | --- |
{rows}

## Verify

{checks}

## Boundary

This is an installable CodeBuddy/WorkBuddy plugin wrapper around the local
Study Anything learning workflow kernel. It supports WorkBuddy inline learning
today, keeps OpenAPI/local HTTP as fallback, and keeps MCP as a planned
extension rather than a shipped runtime claim.
"""


def write_outputs() -> None:
    for path, content in output_map().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


def check_outputs() -> None:
    missing: list[str] = []
    stale: list[str] = []
    for path, expected in output_map().items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            stale.append(str(path.relative_to(ROOT)))
    if missing or stale:
        raise WorkBuddyPluginMarketplaceError(
            "WorkBuddy/CodeBuddy marketplace files are stale. Run "
            "`python3 scripts/generate_workbuddy_plugin_marketplace.py`. "
            f"missing={missing} stale={stale}"
        )
    print("ok    WorkBuddy/CodeBuddy marketplace files are up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if generated marketplace files are stale")
    args = parser.parse_args()
    if args.check:
        check_outputs()
    else:
        write_outputs()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"generate_workbuddy_plugin_marketplace failed: {exc}", file=sys.stderr)
        sys.exit(1)
