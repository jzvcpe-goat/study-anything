# Kimi Agent Gateway

Study Anything does not store model credentials or call real models directly. To use Kimi, run the
included user-owned gateway as a separate local process.

Kimi's official API is OpenAI-compatible and accepts Chat Completions requests at
`https://api.moonshot.cn/v1/chat/completions`. The current Kimi quickstart uses
`kimi-k2.6`; check the official [Kimi API quickstart](https://platform.moonshot.cn/docs/guide/start-using-kimi-api),
[Chat Completions API](https://platform.moonshot.cn/docs/api/chat), and
[model list](https://platform.moonshot.cn/docs/intro) before choosing a production model.

## Start Study Anything

For a lightweight local setup:

```bash
./scripts/run_skill_mode_demo.sh
./scripts/launch_skill_mode.sh
```

For Docker self-host:

```bash
python3 scripts/setup_env.py
./scripts/launch_self_host.sh
```

## Verify The Gateway Without A Real Key

Before adding Kimi credentials, prove that the same gateway entrypoint can satisfy the Study Anything
Agent contract:

```bash
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
```

With a running Study Anything API, run the end-to-end dry-run acceptance flow:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
```

This starts `scripts/openai_compatible_agent_gateway.py` in `AGENT_GATEWAY_MODE=dry_run`, registers it
as an HTTP Agent provider, and completes teaching layers, quiz, grading, mastery, `agent-audit`, and
`agent-eval/artifact` without any model key.

## Start The User-Owned Kimi Gateway

Run this in a separate terminal. The API key remains in the gateway process environment and is never
stored by Study Anything:

```bash
export AGENT_LLM_BASE_URL="https://api.moonshot.cn/v1"
export AGENT_LLM_API_KEY="$MOONSHOT_API_KEY"
export AGENT_LLM_MODEL="${AGENT_LLM_MODEL:-kimi-k2.6}"
export AGENT_LLM_EXTRA_BODY_JSON='{"thinking":{"type":"disabled"}}'

python3 scripts/openai_compatible_agent_gateway.py \
  --host 127.0.0.1 \
  --port 8787
```

Disabling thinking is optional. It is useful for the short structured tasks in the Study Anything MVP.

## Register The Gateway

For Skill Mode or another host-local API:

```bash
python3 scripts/study_anything_cli.py agent-add-http \
  --label "My Kimi gateway" \
  --endpoint "http://127.0.0.1:8787/invoke" \
  --set-default
```

For a Docker-hosted Study Anything API, use:

```bash
python3 scripts/study_anything_cli.py agent-add-http \
  --label "My Kimi gateway" \
  --endpoint "http://host.docker.internal:8787/invoke" \
  --set-default
```

The command prints a provider ID. Verify it, then start a configured learning session:

```bash
python3 scripts/study_anything_cli.py agent-test PROVIDER_ID

python3 scripts/study_anything_cli.py start \
  --agent-mode configured \
  --title "My notes" \
  --reference "local://my-notes" \
  --text "Paste the source material here."
```

`agent-add-http --set-default` registers the gateway for teaching layers, quiz generation, answer
grading, insight synthesis, scribe notes, source verification, and embedding tasks unless you pass
explicit `--capability` values.

After answering, collect redacted proof:

```bash
python3 scripts/study_anything_cli.py agent-audit SESSION_ID
python3 scripts/study_anything_cli.py agent-eval SESSION_ID
python3 scripts/study_anything_cli.py quality-eval SESSION_ID
python3 scripts/study_anything_cli.py obsidian-export SESSION_ID --markdown
python3 scripts/study_anything_cli.py package-export SESSION_ID
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
```

For a full local acceptance run against the real Study Anything API and dry-run gateway:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
```

Use the Obsidian export for second-brain notes. Use `package-export` or
`GET /v1/sessions/{session_id}/exports/learning-package` when a Kimi-compatible platform agent needs
to hand the learning state to a NotebookLM-style workflow or local archive.

## DeepSeek-Compatible Gateway

The same gateway can be used with DeepSeek or another OpenAI-compatible provider. Keep the provider
key only in the gateway shell:

```bash
export AGENT_LLM_BASE_URL="https://api.deepseek.com"
export AGENT_LLM_API_KEY="$DEEPSEEK_API_KEY"
export AGENT_LLM_MODEL="${AGENT_LLM_MODEL:-deepseek-v4-flash}"
export AGENT_LLM_EXTRA_BODY_JSON='{"thinking":{"type":"disabled"},"max_tokens":2048}'

python3 scripts/openai_compatible_agent_gateway.py \
  --host 127.0.0.1 \
  --port 8787
```

DeepSeek's current OpenAI-format API supports `response_format={"type":"json_object"}`. The legacy
`deepseek-chat` and `deepseek-reasoner` aliases are scheduled for deprecation, so new Study Anything
examples should use `deepseek-v4-flash` or `deepseek-v4-pro`.

## Browser-Only Kimi Limitation

A browser-only Kimi conversation cannot run local scripts, access your repository, or call
`http://127.0.0.1`. Kimi's official documentation also states that the inference API itself does not
execute code or access external resources.

Use the local gateway above, or expose an authenticated private HTTPS gateway if Study Anything and
your agent run on different machines. Do not expose the local gateway directly to the public internet.

If you want Kimi to follow the repo-local skill, give it `skills/study-anything/SKILL.md` as a
runbook, but a local terminal-capable agent still needs to execute the commands. In the MVP, Kimi is
best used as the Bring Your Own Agent reasoning layer through the gateway, not as the local operator.
