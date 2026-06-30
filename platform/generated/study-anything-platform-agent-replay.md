# Study Anything Platform Agent Release Replay

Schema: `platform-agent-release-replay-v1`
Version: `v0.3.31-alpha`
Status: `pass`

This evidence verifies the platform Agent path after release assets are
available: import the tool manifest, call the minimum learning tool chain, and
emit a redacted transcript that is safe to attach to GitHub issues.

## Archive

- Archive: `platform/generated/study-anything-platform-agent-replay.zip` sha256 `3dc0b035b69ddc00c7e81b601e5c61eb33dc526de18588785c2c456d1183118b`

## Commands

- `python3 scripts/replay_platform_agent_from_release.py --tag v0.3.31-alpha --platform kimi --runtime metadata-only`
- `python3 scripts/replay_platform_agent_from_release.py --tag v0.3.31-alpha --platform kimi --runtime skill-mode`
- `python3 scripts/replay_platform_agent_from_release.py --tag v0.3.31-alpha --platform kimi --runtime external-api --api-base http://127.0.0.1:8000`
- `python3 scripts/replay_platform_agent_from_release.py --fixture fixtures/release-asset-adoption/asset-only-pass.json --asset-dir platform/generated --platform kimi --runtime metadata-only`

## Required Replay Tools

- `study_anything_health`
- `study_anything_create_session`
- `study_anything_add_reading`
- `study_anything_teaching_layers`
- `study_anything_run`
- `study_anything_answer`
- `study_anything_mastery`
- `study_anything_agent_audit`
- `study_anything_agent_eval_artifact`

## Classification Matrix

- `platform_agent_replay_ready` -> `pass`: Release assets were unpacked, platform tool import succeeded, and the minimal learning tool chain completed against a running API.
- `platform_agent_replay_metadata_ready` -> `metadata_only`: Release assets and tool imports are valid, but no API runtime was called.
- `tool_import_invalid` -> `block_release_claim`: OpenAI tools or OpenAPI operations are malformed, missing required tools, or expose unsafe security schemes.
- `api_unavailable` -> `needs_runtime`: The selected runtime did not expose a reachable Study Anything API.
- `runtime_launch_failed` -> `needs_runtime`: The local Skill Mode runtime could not be launched.
- `tool_call_failed` -> `block_release_claim`: A required platform tool call failed after import.
- `schema_mismatch` -> `block_release_claim`: A tool response did not match the expected schema or state.
- `privacy_leak` -> `block_release_claim`: The replay transcript included private source text, answers, secrets, or local paths.
- `platform_entrypoint_missing` -> `block_release_claim`: The selected platform pack entrypoint is missing from the adoption pack.
- `release_asset_invalid` -> `block_release_claim`: The release assets could not be downloaded, verified, or unpacked.

## Privacy

No raw source text, learner answers, Agent prompts, endpoint secrets, real model
keys, private support bundle payloads, or local absolute paths are included.
