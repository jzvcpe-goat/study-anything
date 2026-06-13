# Adoption Readiness

This guide is for external users and maintainers who want to prove Study Anything works from a clean
checkout before connecting real model credentials.

## Platform Adoption Pack

For Kimi Work, Codex, WorkBuddy-style HTTP workspaces, or another platform Agent, start from the
copy-ready adoption pack:

```bash
python3 scripts/generate_platform_adoption_pack.py
python3 scripts/generate_platform_adoption_pack.py --check
python3 scripts/verify_platform_operator_drill.py --check
python3 scripts/verify_agent_eval_baseline.py --check
python3 scripts/verify_external_adoption.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip \
  --copy-worktree
```

The archive contains OpenAPI/OpenAI tool import assets, Kimi/Codex/WorkBuddy packs, the repo-local
Skill, gateway examples, mock agent, NotebookLM fixture, verifier scripts, and a SHA256 manifest.
The operator drill emits `study-anything-operator-drill-v1` evidence that the pack can be consumed as
an external platform tool directory. The adoption verifier emits `adoption-proof-v1` and exercises
importer, enrichment, retrieval, teaching layers, eval, Obsidian export, and NotebookLM-style
learning-package export through Skill Mode.

Use this path before claiming a platform integration works. It does not require the standalone
frontend, and it does not store real model keys in Study Anything.

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
- `agent-eval/quality`
- platform tool, enriched lesson, and importer lesson smoke through Skill Mode

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
return `agent-audit`, `agent-eval/artifact`, `agent-eval/quality`, Obsidian export, and
`learning-package-v1` after each learning loop.

To prove the complete plugin-style lesson path against a running API:

```bash
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_platform_lesson_flow.py
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_importer_lesson_flow.py
```

This verifier runs source input, enrichment, overview/glossary teaching, quiz, answer grading, quality
eval, Obsidian export, and the portable learning package. The importer verifier starts from
`fixtures/notebooklm/notebooklm-style-context-package.json` and proves Learning Context Package import
without depending on an official NotebookLM API.

## Diagnostics

When adoption fails, run:

```bash
python3 scripts/diagnose_adoption.py
```

It checks:

- missing `.env` and copyable setup command
- localhost API reachability
- Docker daemon availability
- GHCR manifest visibility
- Agent endpoint health
- provider capability defaults

Use `--strict` in CI-like environments where warnings should fail the run.
The JSON payload is `adoption-diagnostics-v1` and includes `adoption-diagnostic-plan-v1`, a
platform-agent-friendly next-command plan.

Common remediation classes are included in `adoption-proof-v1` and `diagnose_adoption.py`: GHCR or
Docker Hub availability, non-ASCII checkout paths, port conflicts, local Agent endpoint reachability,
Node/npm availability, and optional Promptfoo setup.

## Ecosystem Submission Smoke

Before submitting Kimi-compatible, Codex Skill, WorkBuddy-style HTTP, or generic OpenAPI assets to an
external platform, run:

```bash
python3 scripts/verify_ecosystem_submission_pack.py
```

The verifier emits `ecosystem-submission-verification-v1` and proves the submission pack has no
standalone frontend requirement, no Study Anything custody of real model keys, no raw learning data
in submission metadata, and no high-risk management endpoints in the imported platform tool surface.

## Adoption Telemetry And PMF Readiness

After the API is reachable, verify the local aggregate adoption contracts:

```bash
python3 scripts/verify_adoption_telemetry.py --api-base http://127.0.0.1:8000
curl http://127.0.0.1:8000/v1/adoption/telemetry
curl http://127.0.0.1:8000/v1/pmf/readiness
```

The verifier emits `adoption-telemetry-verification-v1`. The API contracts are
`adoption-telemetry-v1` and `pmf-readiness-v1`; they report aggregate clean-clone/runtime/tool/eval,
repeat-learning, plugin-validation, and explicit opt-in feedback counts only. They do not include raw
source text, answers, insights, user ids, Agent endpoints, API keys, browser context, app context, or
video transcripts.

## Published Image Fallback

The normal published-image smoke is:

```bash
python3 scripts/verify_published_image_launch.py --tag v0.3.2-alpha
```

If the local machine can inspect the multi-arch manifest but GHCR layer download is too slow, record a
diagnostic instead of leaving the run ambiguous:

```bash
python3 scripts/verify_published_image_launch.py \
  --tag v0.3.2-alpha \
  --pull-timeout-seconds 180 \
  --allow-pull-timeout-report
```

This fallback is acceptable only when GitHub `docker-images` succeeded and
`docker manifest inspect ghcr.io/jzvcpe-goat/study-anything/api:v0.3.2-alpha` shows `linux/amd64`
and `linux/arm64`. The timeout report includes `manifest_evidence` plus explicit fallback acceptance
conditions so reviewers do not confuse a local GHCR download stall with a broken release image.
