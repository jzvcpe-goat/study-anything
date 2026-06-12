# Adoption Readiness

This guide is for external users and maintainers who want to prove Study Anything works from a clean
checkout before connecting real model credentials.

## Clean Clone Smoke

From an existing checkout, run the adoption verifier:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo .
```

The verifier creates a temporary clone, generates `.env`, starts Skill Mode, verifies the
OpenAI-compatible gateway dry-run path, and completes:

- teaching layers
- quiz generation
- answer grading
- mastery update
- `agent-audit`
- `agent-eval/artifact`

For development before committing local edits, use:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo . --copy-worktree
```

## Optional Promptfoo Evidence

Promptfoo is the first external eval runner. It checks the redacted eval artifact contract; it does
not judge learning quality by itself.

```bash
python3 scripts/verify_clean_clone_adoption.py --repo . --with-promptfoo
```

Use `--promptfoo-required` only in an environment where Node/npm package installation is allowed to
fail the run:

```bash
python3 scripts/verify_clean_clone_adoption.py --repo . --with-promptfoo --promptfoo-required
```

Study Anything separates these layers:

- Invocation proof: `agent-audit` and native `agent-eval/artifact` gates prove the learning tasks were
  handled and redacted.
- Quality evaluation: Promptfoo, DeepEval, LangChain AgentEvals, and Ragas can score contract quality,
  task completion, trajectory, and grounding after native gates pass.

## Platform Adoption Paths

Kimi/OpenAI-compatible:

```bash
python3 scripts/verify_openai_compatible_gateway.py --gateway-only
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_openai_compatible_gateway.py
```

Then add real credentials to your own gateway environment. Study Anything does not store model API
keys.

Codex or another terminal-capable Agent:

```bash
ln -s "$(pwd)/skills/study-anything" "${CODEX_HOME:-$HOME/.codex}/skills/study-anything"
./scripts/run_skill_mode_demo.sh
```

WorkBuddy or another HTTP-tool workspace:

```bash
platform/generated/study-anything-platform-openapi.json
platform/generated/study-anything-openai-tools.json
```

Import one of those assets, set the API base to `http://127.0.0.1:8000`, and require the Agent to
return `agent-audit` plus `agent-eval/artifact` after each learning loop.

## Diagnostics

When adoption fails, run:

```bash
python3 scripts/diagnose_adoption.py
```

It checks:

- localhost API reachability
- Docker daemon availability
- GHCR manifest visibility
- Agent endpoint health
- provider capability defaults

Use `--strict` in CI-like environments where warnings should fail the run.

## Published Image Fallback

The normal published-image smoke is:

```bash
python3 scripts/verify_published_image_launch.py --tag v0.2.17-alpha
```

If the local machine can inspect the multi-arch manifest but GHCR layer download is too slow, record a
diagnostic instead of leaving the run ambiguous:

```bash
python3 scripts/verify_published_image_launch.py \
  --tag v0.2.17-alpha \
  --pull-timeout-seconds 180 \
  --allow-pull-timeout-report
```

This fallback is acceptable only when GitHub `docker-images` succeeded and
`docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.2.17-alpha` shows `linux/amd64`
and `linux/arm64`.
