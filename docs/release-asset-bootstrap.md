# Release Asset Bootstrap

Study Anything v0.3.26-alpha adds `release-asset-bootstrap-v1` as the
operator-friendly entrypoint for external platform Agents. It starts from the
GitHub Release page, not a local development checkout.

Use it when a Kimi, Codex, WorkBuddy, or generic HTTP-tool operator needs to
verify that the public release assets are enough to import and run Study
Anything.

Required release assets:

- `study-anything-platform-adoption-pack.zip`
- `study-anything-published-image-evidence.zip`
- `study-anything-adopter-evidence-archive.zip`
- `study-anything-platform-feedback-package.zip`
- `study-anything-release-asset-bootstrap.zip`
- `study-anything-platform-agent-replay.zip`

Schema contract:

- `release-asset-bootstrap-v1`: generated public evidence, Markdown, zip, and
  checksum for the bootstrap entrypoint.
- `release-asset-bootstrap-transcript-v1`: runtime transcript emitted by
  `scripts/bootstrap_from_release.py`.
- `release-asset-adoption-proof-v1`: lower-level proof reused for digest,
  pack, and runtime replay verification.

## Commands

Metadata-only bootstrap downloads release assets, checks GitHub sha256 digests,
extracts the adoption pack, verifies tool import manifests, and emits a
redacted transcript:

```bash
python3 scripts/bootstrap_from_release.py \
  --tag v0.3.26-alpha \
  --runtime metadata-only
```

Skill Mode bootstrap adds a disposable local Skill Mode replay after asset and
tool checks:

```bash
python3 scripts/bootstrap_from_release.py \
  --tag v0.3.26-alpha \
  --runtime skill-mode
```

Published-image bootstrap checks the release assets and then runs the published
Docker image verifier:

```bash
python3 scripts/bootstrap_from_release.py \
  --tag v0.3.26-alpha \
  --runtime published-image
```

Before the tag exists, maintainers can run the offline fixture path against the
current generated assets:

```bash
python3 scripts/bootstrap_from_release.py \
  --fixture fixtures/release-asset-adoption/asset-only-pass.json \
  --asset-dir platform/generated \
  --runtime metadata-only
```

## What It Proves

- Release assets are present and digest-verified when GitHub provides sha256
  metadata.
- The adoption pack manifest hashes match the files inside the zip.
- OpenAI-compatible tools and OpenAPI operations contain every required Study
  Anything tool.
- Kimi, Codex, and WorkBuddy pack entrypoints are present.
- The selected runtime mode is either skipped explicitly (`metadata-only`) or
  verified through bounded replay (`skill-mode` or `published-image`).

## Classification

- `release_asset_bootstrap_ready`: release assets, import manifests, and
  selected runtime replay are usable.
- `release_asset_missing`: a required release zip asset is missing.
- `release_asset_digest_mismatch`: a downloaded asset does not match GitHub
  sha256 metadata.
- `release_asset_pack_corrupted`: the adoption pack zip or manifest hashes are
  invalid.
- `release_asset_published_evidence_missing`: published-image evidence is not
  present in the adoption pack.
- `release_asset_network_unavailable`: GitHub release metadata or asset
  download is unavailable from the operator network.
- `tool_manifest_invalid`: OpenAI tools or OpenAPI paths cannot be imported by
  platform Agents.
- `local_api_unavailable`: runtime verification needs Skill Mode or Docker to
  be started.
- `published_image_unavailable`: GHCR manifest or image smoke needs an
  independent retry.
- `non_ascii_path_risk`: source-build Docker paths may be unsafe on the
  operator machine; use published images or Skill Mode.
- `bootstrap_failed`: uncategorized failure that needs maintainer triage.

## Privacy

Bootstrap evidence is metadata-only. It must not include raw source text,
learner answers, Agent prompts, Agent endpoint secrets, real model keys, local
absolute paths, private support payloads, or browser/video/app private context.
