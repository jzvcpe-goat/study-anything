# Study Anything Release Cleanroom Bootstrap

Version: `v0.3.31-alpha`

`release-cleanroom-bootstrap-evidence-v1` proves that Study Anything can be bootstrapped
from GitHub Release assets without assuming an existing repository checkout.

## Commands

- `python3 study_anything_release_bootstrap.py --tag v0.3.31-alpha --platform kimi --runtime metadata-only`
- `python3 study_anything_release_bootstrap.py --tag v0.3.31-alpha --platform kimi --runtime skill-mode`
- `python3 study_anything_release_bootstrap.py --tag v0.3.31-alpha --platform generic-openapi --runtime published-image`
- `python3 platform/bootstrap/study_anything_release_bootstrap.py --fixture fixtures/release-asset-adoption/asset-only-pass.json --asset-dir platform/generated --runtime metadata-only`

## Classification Matrix

- `cleanroom_bootstrap_ready` -> `pass`: Release assets, platform imports, and selected runtime path are usable from a clean directory.
- `release_asset_missing` -> `block_release_claim`: One or more required public zip assets are absent from the GitHub Release.
- `release_asset_digest_mismatch` -> `block_release_claim`: A downloaded asset does not match GitHub sha256 metadata.
- `release_asset_pack_corrupted` -> `block_release_claim`: The platform adoption pack cannot be unpacked safely.
- `tool_import_invalid` -> `block_platform_submission`: OpenAI tools or OpenAPI operation IDs are malformed or incomplete.
- `platform_entrypoint_missing` -> `block_platform_submission`: The selected Kimi, Codex, WorkBuddy, Hermes, or generic entrypoint is missing.
- `source_download_failed` -> `needs_network_or_source_dir`: Runtime replay needs source code but the GitHub tag source archive could not be downloaded.
- `runtime_launch_failed` -> `needs_runtime_triage`: The selected Skill Mode, external API, or published-image runtime could not be launched.
- `api_unavailable` -> `needs_runtime_triage`: The Study Anything API was not reachable for tool replay.
- `schema_mismatch` -> `block_release_claim`: A runtime response did not match the expected learning/eval schema.
- `privacy_leak` -> `block_release_claim`: A report included source text, answers, local paths, prompts, endpoints, or keys.
- `network_unavailable` -> `needs_independent_recheck`: GitHub release metadata or assets could not be fetched.
- `cleanroom_bootstrap_failed` -> `needs_triage`: The bootloader failed outside a more specific classification.

## Privacy

- Raw source text included: `false`
- Learner answers included: `false`
- Real model keys included: `false`
- Agent endpoint secrets included: `false`
- Local absolute paths included: `false`

## Archive

- Archive: `platform/generated/study-anything-release-cleanroom-bootstrap.zip` sha256 `d7e897f0b830fe293e19f7b4a5688d21542ff189b8552ecb462e4096965eb6e8`
