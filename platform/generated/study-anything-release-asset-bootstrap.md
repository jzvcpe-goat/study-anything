# Study Anything Release Asset Bootstrap

Schema: `release-asset-bootstrap-v1`
Version: `v0.3.31-alpha`
Status: `pass`

This evidence makes the GitHub Release page the first adoption surface for
external platform Agents. It verifies public assets, import manifests, and
runtime choices without requiring a development checkout as the starting point.

## Archive

- Archive: `platform/generated/study-anything-release-asset-bootstrap.zip` sha256 `f6e6f7c83f809f9d59283f670e3af4c2ff338c8f39b79a3864d37605e1e7dc2c`

## Commands

- `python3 scripts/bootstrap_from_release.py --tag v0.3.31-alpha --runtime metadata-only`
- `python3 scripts/bootstrap_from_release.py --tag v0.3.31-alpha --runtime skill-mode`
- `python3 scripts/bootstrap_from_release.py --tag v0.3.31-alpha --runtime published-image`
- `python3 scripts/bootstrap_from_release.py --fixture fixtures/release-asset-adoption/asset-only-pass.json --asset-dir platform/generated --runtime metadata-only`

## Classification Matrix

- `release_asset_bootstrap_ready` -> `pass`: Release assets, pack digests, platform imports, and selected runtime replay are usable.
- `release_asset_missing` -> `block_release_claim`: Attach all required public release zip assets before announcing external adoption.
- `release_asset_digest_mismatch` -> `block_release_claim`: Delete local downloads and recreate the release asset from the matching main commit.
- `release_asset_pack_corrupted` -> `block_release_claim`: Re-download or regenerate the platform adoption pack.
- `release_asset_published_evidence_missing` -> `block_release_claim`: Regenerate published-image evidence before packaging the adoption pack.
- `release_asset_network_unavailable` -> `needs_independent_recheck`: Retry from another network or use a safely mirrored asset directory.
- `tool_manifest_invalid` -> `block_platform_submission`: Regenerate platform tool assets and adoption pack before importing into Kimi/Codex/WorkBuddy.
- `local_api_unavailable` -> `runtime_recheck_required`: Launch Skill Mode or Docker self-host before running live platform tools.
- `published_image_unavailable` -> `runtime_recheck_required`: Check GHCR manifest and docker-images workflow before claiming published-image readiness.
- `non_ascii_path_risk` -> `operator_environment_warning`: Use Skill Mode or published images, or move source builds into an ASCII-only path.
- `bootstrap_failed` -> `needs_triage`: Run the lower-level release asset verifier and attach the redacted transcript to GitHub.

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, local absolute paths, private support payloads, or browser/video/app
private context are included.
