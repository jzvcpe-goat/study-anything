# Platform Agent Release Replay

Study Anything v0.3.27-alpha adds `platform-agent-release-replay-v1` for
Kimi, Codex, WorkBuddy, and generic OpenAPI-style platform Agents.

Use it after `release-asset-bootstrap-v1` passes. Bootstrap proves the GitHub
Release assets and import manifests are valid; release replay proves a
platform-style tool caller can run the minimum learning loop against a running
Study Anything API.

## What It Replays

The replay tool imports the release adoption pack and executes this minimum
tool chain:

- `study_anything_health`
- `study_anything_create_session`
- `study_anything_add_reading`
- `study_anything_run`
- `study_anything_answer`
- `study_anything_mastery`
- `study_anything_agent_audit`
- `study_anything_agent_eval_artifact`

The transcript records tool name, OpenAPI operation id, method, path template,
payload keys, latency, status, and schema/status summaries. It does not record
raw source text, learner answer text, Agent prompts, endpoint secrets, model
keys, support payloads, or local absolute paths.

## Commands

Metadata-only replay verifies release assets, tool imports, and selected
platform entrypoints without calling an API:

```bash
python3 scripts/replay_platform_agent_from_release.py \
  --tag v0.3.27-alpha \
  --platform kimi \
  --runtime metadata-only
```

Skill Mode replay starts the local Study Anything API from the current source
checkout and calls the tool chain:

```bash
python3 scripts/replay_platform_agent_from_release.py \
  --tag v0.3.27-alpha \
  --platform kimi \
  --runtime skill-mode
```

External API replay calls a running local, private, or platform-launched Study
Anything API:

```bash
python3 scripts/replay_platform_agent_from_release.py \
  --tag v0.3.27-alpha \
  --platform workbuddy \
  --runtime external-api \
  --api-base http://127.0.0.1:8000
```

Published-image replay uses the same `--api-base` pattern after the operator
starts the published Docker image:

```bash
python3 scripts/replay_platform_agent_from_release.py \
  --tag v0.3.27-alpha \
  --platform generic-openapi \
  --runtime published-image \
  --api-base http://127.0.0.1:8000
```

Before the tag exists, maintainers can run the fixture path against generated
assets:

```bash
python3 scripts/replay_platform_agent_from_release.py \
  --fixture fixtures/release-asset-adoption/asset-only-pass.json \
  --asset-dir platform/generated \
  --platform kimi \
  --runtime metadata-only
```

## Classification

- `platform_agent_replay_ready`: release assets, tool import, API calls, audit,
  eval artifact, and privacy redaction passed.
- `platform_agent_replay_metadata_ready`: release assets and tool import passed
  without calling a runtime.
- `tool_import_invalid`: OpenAI tools or OpenAPI operations are missing,
  malformed, or unsafe.
- `api_unavailable`: no reachable API was available for replay.
- `runtime_launch_failed`: local Skill Mode could not launch.
- `tool_call_failed`: a required platform tool call failed.
- `schema_mismatch`: a response did not match the expected schema or state.
- `privacy_leak`: replay output included private data and must not be shared.
- `platform_entrypoint_missing`: the selected platform pack entrypoint is
  missing from the adoption pack.
- `release_asset_invalid`: release assets could not be downloaded, verified, or
  unpacked.

## Boundary

Study Anything does not own real model credentials or browser/file access.
Those remain inside the user-owned platform Agent. The replay uses the built-in
demo agent only to prove the Study Anything learning workflow and tool
contract are callable.
