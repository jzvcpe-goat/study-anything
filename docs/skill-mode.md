# Skill Mode

The Study Anything adapter can be used through an API/Skill-first human-reconstruction workflow. The repository includes a small standard-library CLI and a repo-local Codex skill:

- CLI: `scripts/study_anything_cli.py`
- Skill: `skills/study-anything`

The CLI talks only to the public API. It does not store model API keys or execute real model logic inside Study Anything.

## 零配置体验（不需要任何 API Key）

在接入真实模型之前，你可以先验证本地学习引擎本身是否工作。零配置路径会显式使用
`dry_run` Gateway：所有推理都是确定性的模拟输出，不产生任何费用，也不需要网络。

> **启动前检查**：Gateway 默认是 `auto` 模式。如果没有配置上游模型环境变量，它会
> 自动进入 `dry_run`，并在终端打印 health/invoke 地址、缺失的 env 和下一步建议。
> 只有当你显式设置 `AGENT_GATEWAY_MODE=upstream` 时，才必须同时提供
> `AGENT_LLM_BASE_URL`、`AGENT_LLM_API_KEY` 和 `AGENT_LLM_MODEL`；缺失时 Gateway
> 会带清楚诊断退出。真实模型也可以完全交给 WorkBuddy / Kimi Work / 你的终端 Agent
> 作为出口，Study Anything 只负责本地学习流程。

```bash
# 1. 启动本地引擎
./scripts/launch_skill_mode.sh
python3 scripts/study_anything_cli.py health

# 2. 启动 Gateway（显式 dry_run，不需要 key）
AGENT_GATEWAY_MODE=dry_run python3 scripts/openai_compatible_agent_gateway.py \
  --host 127.0.0.1 \
  --port 8787

# 3. 在另一个终端注册
python3 scripts/study_anything_cli.py agent-add-http \
  --label "Local gateway" \
  --endpoint "http://127.0.0.1:8787/invoke" \
  --set-default

# 4. 跑一条完整学习流
python3 scripts/study_anything_cli.py start \
  --title "Rust 所有权" \
  --text "Rust 的核心创新是所有权系统。" \
  --reference "rust-book"

# 拿到输出的 session_id 后
python3 scripts/study_anything_cli.py answer <SESSION_ID> \
  --text "所有权确保内存安全，编译器在编译时检查借用规则。"

python3 scripts/study_anything_cli.py teach <SESSION_ID> --layer overview
```

> **注意**：这个 Gateway 启动是**临时验证**用的。真正推荐的使用方式是让
> **WorkBuddy / Kimi Work / 你的终端 Agent** 作为模型出口，它们自带模型配置和浏览能力。
> Study Anything 只负责本地学习流程、校验、审计和导出。你不需要长期维护一个手动
> 启动的 Gateway 进程。

## Start

For the smallest working setup, launch the local Skill API and run the deterministic demo:

```bash
./scripts/run_skill_mode_demo.sh
```

This is the recommended smoke command for terminal-capable LLM agents. Some agent shells clean up
background processes after a command finishes; the one-command runner starts the API, verifies the CLI
learning loop, checks discard confirmation, and stops the API before exiting.

For persistent local use, run:

```bash
./scripts/launch_skill_mode.sh
python3 scripts/study_anything_cli.py health
python3 scripts/study_anything_cli.py demo
```

`launch_skill_mode.sh` verifies Python 3.11 or 3.12, creates `.venv` when needed, installs the
hash-bound dependencies from `requirements/locked-skill.txt`,
and starts the local API in the background with JSON session storage. Stop it with:

```bash
./scripts/stop_skill_mode.sh
```

Some desktop or agent sandboxes do not keep background processes alive after the launch command
returns. In that environment, keep the API in the foreground instead:

```bash
./scripts/launch_skill_mode.sh --foreground
```

or:

```bash
SKILL_API_FOREGROUND=true ./scripts/launch_skill_mode.sh
```

Leave that terminal running, then use another terminal, browser, or agent to call
`http://127.0.0.1:8000`. Stop the foreground API with `Ctrl-C`.

The deterministic demo creates a source-bound question, submits a grounded answer, updates mastery, and synthesizes an insight.
It also verifies Agent eval, platform tools, an enriched platform lesson, an importer-based lesson,
Obsidian export, and the portable learning package.

## Agent Runtime Boundary

The bundled skill is a repo-local instruction file, not a hosted service. It works directly in
terminal-capable agents such as Codex and local coding agents that can run shell commands inside this
repository.

Chat-only LLM products, including a browser-only Kimi conversation, cannot execute the scripts on your
computer or reach `http://127.0.0.1:8000`. To use Kimi for real reasoning, run Study Anything locally
and expose a private HTTPS agent gateway that implements `docs/agent-contract.md`. Keep model credentials
inside that gateway.

In short:

- Kimi as chat UI only: can read this runbook and tell you what to run, but cannot operate the local skill.
- Kimi through API: can be the reasoning model inside `scripts/openai_compatible_agent_gateway.py`.
- Terminal Agent/Codex/local coding agent: can operate `scripts/study_anything_cli.py` directly.

## Learn From A Source

### CLI 参数速查

| 命令 | session 怎么传 |
|------|---------------|
| `start` | 自动生成，不用传 |
| `teach <SESSION_ID>` | positional，或 `teach --session <SESSION_ID>` |
| `answer <SESSION_ID>` | positional，或 `answer --session <SESSION_ID>` |
| `show <SESSION_ID>` | positional，或 `show --session <SESSION_ID>` |
| `mastery <SESSION_ID>` | positional，或 `mastery --session <SESSION_ID>` |

示例：

```bash
# 正确
python3 scripts/study_anything_cli.py teach a1aea872-xxx --layer overview

# 也正确
python3 scripts/study_anything_cli.py teach --session a1aea872-xxx --layer overview
```

```bash
python3 scripts/study_anything_cli.py start \
  --title "Notes on retrieval practice" \
  --reference "local://retrieval-practice" \
  --text "Retrieval practice improves durable learning when recall is effortful and repeated."

python3 scripts/study_anything_cli.py answer SESSION_ID \
  --text "Effortful repeated recall strengthens durable learning."
```

Run `show SESSION_ID`, `mastery SESSION_ID`, `events SESSION_ID`, `agent-audit SESSION_ID`, or
`agent-eval SESSION_ID` to inspect the resulting state and Agent proof.

When a platform agent has gathered browser pages, documents, app context, or video slices, attach that
context before the quiz loop:

```bash
python3 scripts/study_anything_cli.py enrich SESSION_ID \
  --source-type video_slice \
  --reference "video://lesson/clip-1" \
  --title "Lesson clip" \
  --locator "00:00:05-00:00:42" \
  --text "Paste the bounded excerpt here."

python3 scripts/study_anything_cli.py teach SESSION_ID \
  --layer overview \
  --layer glossary \
  --language zh \
  --level beginner
```

For mixed-source imports, prefer a Learning Context Package:

```bash
python3 scripts/study_anything_cli.py context-validate \
  fixtures/notebooklm/notebooklm-style-context-package.json

python3 scripts/study_anything_cli.py context-import \
  fixtures/notebooklm/notebooklm-style-context-package.json --session
```

For import commands, bare `--session` prints the created/expanded session summary. Use
`--session SESSION_ID` or `--session-id SESSION_ID` to expand an existing session.

The package supports `web`, `document`, `video_slice`, `app_context`, `markdown_note`, and
`obsidian_note` items. Use this path when a platform Agent, Kimi workspace, Codex run, or WorkBuddy
workspace has collected several pieces of context before Study Anything starts teaching.

For one command that exercises the full learning-plugin path:

```bash
python3 scripts/study_anything_cli.py lesson \
  --title "Notes on retrieval practice" \
  --reference "local://retrieval-practice" \
  --text "Retrieval practice improves durable learning when recall is effortful and repeated." \
  --enrichment-text "A video clip shows learners recalling before rereading." \
  --answer "Effortful repeated recall strengthens durable learning."
```

## Connect Your Agent

Expose a user-owned gateway that implements `docs/agent-contract.md`, then configure its endpoint:

```bash
python3 scripts/study_anything_cli.py agent-add-http \
  --label "My private learning agent" \
  --endpoint "http://127.0.0.1:8787/invoke" \
  --set-default

python3 scripts/study_anything_cli.py agent-test
```

After `--set-default`, `start`, `lesson`, and context-import session creation use `--agent-mode auto`
by default: they route to the configured Agent when the common learning capabilities are covered and
fall back to the zero-key demo Agent when nothing is configured. Use `--agent-mode configured` only
when you want to force configured routing while debugging. Credentials, tools, and model choice remain inside the gateway.
By default, `agent-add-http --set-default` registers the gateway for teaching layers, quiz
generation, grading, synthesis, scribe notes, source verification, and embedding tasks. Use repeated
`--capability` flags when you want split routing across multiple providers.

If `auto` finds a partial Agent setup, the CLI prints the missing default capabilities and keeps the
lesson usable by falling back to the zero-key demo. Run `agents`, then `agent-set-default PROVIDER_ID`
to route the common learning capabilities, or set the missing capabilities one by one with repeated
`--capability` values.

For an OpenAI-compatible gateway dry-run that needs no model key:

```bash
python3 scripts/verify_openai_compatible_gateway.py --contract-only
python3 scripts/verify_agent_gateway_hardening.py --contract-only
python3 scripts/verify_external_agent_adapter_hardening.py --contract-only
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
```

Use `--contract-only` inside runners that block localhost listening sockets; it validates the
gateway and adapter contracts in-process before you rerun the socket checks from a host terminal.

You can also avoid environment variables by passing `--api-base`:

```bash
python3 scripts/study_anything_cli.py --api-base http://127.0.0.1:8000 health
```

## Install The Skill

For Codex, copy or symlink `skills/study-anything` into your skills directory to make it discoverable:

```bash
ln -s "$(pwd)/skills/study-anything" "${CODEX_HOME:-$HOME/.codex}/skills/study-anything"
```

The skill teaches an Agent to operate the same CLI, including HITL resolution and explicit confirmation before discard.

For another terminal-capable agent, provide `skills/study-anything/SKILL.md` as its operating
instructions and keep the repository available as its working directory. If that agent does not support
skills natively, ask it to follow the file as a runbook.

## Prove The Agent Was Used

After a learning loop completes, collect redacted proof:

```bash
python3 scripts/study_anything_cli.py agent-audit SESSION_ID
python3 scripts/study_anything_cli.py agent-eval SESSION_ID
python3 scripts/study_anything_cli.py quality-eval SESSION_ID
python3 scripts/study_anything_cli.py obsidian-export SESSION_ID --markdown
python3 scripts/study_anything_cli.py package-export SESSION_ID
python3 scripts/study_anything_cli.py second-brain-handoff SESSION_ID --archive-dir /tmp/study-anything-archive
```

`agent-audit` verifies that `quiz.generate`, `answer.grade`, and `insight.synthesize` were handled by
a Study Anything Agent provider. `agent-eval` emits the redacted `agent-eval-artifact-v1` bridge for
Promptfoo, DeepEval, LangChain AgentEvals, and Ragas. Neither command returns source text, answers,
feedback bodies, Agent endpoints, or raw Agent metadata.

`quality-eval` adds deterministic teaching-quality gates. `obsidian-export` creates a user-owned
Markdown note. `package-export` creates `learning-package-v1`. `second-brain-handoff` is the strict
redacted Obsidian, NotebookLM-style, and local archive export for platform-agent handoff.
