# Release Cleanroom Bootstrap

Study Anything v0.3.29-alpha adds a release-only cleanroom bootloader for
external operators and platform Agents. The goal is simple: start from the
GitHub Release page, not from a prepared repository checkout.

## What It Proves

`release-cleanroom-bootstrap-v1` verifies that an adopter can:

- Download the six required public release zip assets.
- Verify GitHub sha256 digests when release metadata provides them.
- Unpack and validate the platform adoption pack.
- Import Study Anything tools for Kimi, Codex, WorkBuddy, or generic OpenAPI.
- Run either metadata-only verification or a bounded runtime replay.
- Produce redacted JSON and Markdown reports that can be attached to a GitHub issue.

The bootloader does not store model API keys. Real model credentials stay inside
the user's own platform Agent or local Agent gateway.

## Metadata-Only

Use this when you only want to verify release assets and platform imports:

```bash
python3 study_anything_release_bootstrap.py \
  --tag v0.3.29-alpha \
  --platform kimi \
  --runtime metadata-only \
  --output-dir study-anything-cleanroom-report
```

This path uses Python standard library only. It does not start Study Anything.

## Skill Mode

Use this when you want the bootloader to run the minimal learning chain:

```bash
python3 study_anything_release_bootstrap.py \
  --tag v0.3.29-alpha \
  --platform kimi \
  --runtime skill-mode \
  --output-dir study-anything-cleanroom-report
```

For runtime replay, the bootloader downloads the matching GitHub tag source
archive into a temporary directory, then delegates to the release replay script.
No existing checkout is required. If the source archive is mirrored locally, pass
`--source-dir /path/to/study-anything`.

## Published Image

Use this when Docker is available and the release image should be checked:

```bash
python3 study_anything_release_bootstrap.py \
  --tag v0.3.29-alpha \
  --platform generic-openapi \
  --runtime published-image \
  --output-dir study-anything-cleanroom-report
```

If local pulls are slow, rerun with metadata-only first and attach the generated
Markdown report to an issue.

## Report Boundary

The report includes:

- Environment summary without local absolute paths.
- Release asset counts and digest status.
- Tool import status.
- Runtime status or a skipped marker.
- Failure classification and recovery steps.
- A copyable GitHub issue body.

The report must not include raw source text, learner answers, model keys, Agent
endpoint secrets, raw prompts, local absolute paths, or automatic uploads.

## Failure Classes

- `release_asset_missing`
- `release_asset_digest_mismatch`
- `release_asset_pack_corrupted`
- `tool_import_invalid`
- `platform_entrypoint_missing`
- `source_download_failed`
- `runtime_launch_failed`
- `api_unavailable`
- `schema_mismatch`
- `privacy_leak`
- `network_unavailable`
- `cleanroom_bootstrap_failed`
