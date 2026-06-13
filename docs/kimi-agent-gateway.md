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
python3 scripts/verify_agent_gateway_hardening.py
```

With a running Study Anything API, run the end-to-end dry-run acceptance flow:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
```

This starts `scripts/openai_compatible_agent_gateway.py` in `AGENT_GATEWAY_MODE=dry_run`, registers it
as an HTTP Agent provider, and completes teaching layers, quiz, grading, mastery, `agent-audit`, and
`agent-eval/artifact` without any model key.

The hardening verifier additionally checks unsupported task types, malformed Agent outputs, unsafe
provider endpoint secrets, provider metadata secrets, redacted health diagnostics, and API error
boundaries.

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

Do not append Kimi keys, bearer tokens, cookies, or signed query parameters to the endpoint URL.
Study Anything rejects those because credentials belong in the gateway process environment.

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

When Kimi or the surrounding platform Agent has gathered multiple sources, build a
`learning-context-package-v1` first instead of flattening everything into one prompt. Validate and
import it with:

```bash
python3 scripts/study_anything_cli.py context-validate \
  fixtures/notebooklm/notebooklm-style-context-package.json

python3 scripts/study_anything_cli.py context-import \
  fixtures/notebooklm/notebooklm-style-context-package.json --session
```

The package can contain `web`, `document`, `video_slice`, `app_context`, `markdown_note`, and
`obsidian_note` excerpts. It must not contain Kimi credentials, provider API keys, or hidden system
instructions. Use `POST /v1/sessions/{session_id}/context-package` when adding this package to an
existing Study Anything session.

`agent-add-http --set-default` registers the gateway for teaching layers, quiz generation, answer
grading, insight synthesis, scribe notes, source verification, and embedding tasks unless you pass
explicit `--capability` values.

After answering, collect redacted proof:

```bash
python3 scripts/study_anything_cli.py eval-policy
python3 scripts/study_anything_cli.py agent-audit SESSION_ID
python3 scripts/study_anything_cli.py agent-eval SESSION_ID
python3 scripts/study_anything_cli.py agent-eval-report SESSION_ID
python3 scripts/study_anything_cli.py quality-eval SESSION_ID
python3 scripts/study_anything_cli.py retrieval-eval SOURCE_SESSION_ID --query "focus topic"
python3 scripts/study_anything_cli.py enrichment-artifact SESSION_ID --markdown
python3 scripts/study_anything_cli.py obsidian-export SESSION_ID --markdown
python3 scripts/study_anything_cli.py package-export SESSION_ID
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool report --create-session --required
API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool deepeval --create-session --allow-native-quality-fallback
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/run_external_agent_evals.py --tool retrieval --create-session --required
```

For a full local acceptance run against the real Study Anything API and dry-run gateway:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
python3 scripts/verify_agent_gateway_hardening.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
STUDY_ANYTHING_RETRIEVAL_BACKEND=memory API_BASE=http://127.0.0.1:8000 \
  python3 scripts/verify_platform_ecosystem_eval_flow.py
```

For release or Kimi Work handoff acceptance, run the adoption pack verifier from a terminal-capable
workspace:

```bash
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_platform_operator_drill.py --check
python3 scripts/verify_agent_eval_baseline.py --check
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

This emits `study-anything-operator-drill-v1` for the Kimi-compatible pack directory and
`adoption-proof-v1` for runtime eval evidence, Obsidian export, and NotebookLM-style handoff while
keeping real Kimi credentials outside Study Anything.

Use `second-brain-handoff` or
`GET /v1/sessions/{session_id}/exports/second-brain-handoff` when a Kimi-compatible platform agent
needs to hand learning state to Obsidian, a NotebookLM-style workflow, or a local archive without
logging learner answers or grading feedback. Keep `obsidian-export` and `package-export` for
explicit user-owned exports.

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
