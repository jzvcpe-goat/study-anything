# Study Anything Adopter Evidence Archive

Schema: `adopter-evidence-archive-v1`
Version: `v0.3.23-alpha`
Status: `pass`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

- Archive: `platform/generated/study-anything-adopter-evidence-archive.zip` sha256 `b7b5310a8f10e4f32ec48da8b31db4a5976c5006dc64c55977956cc0a65105dc`

## Reproduction Commands

- `python3 scripts/verify_adopter_evidence_archive.py --check`
- `python3 scripts/generate_adopter_evidence_archive.py --check`
- `python3 scripts/verify_published_image_evidence.py --check`
- `python3 scripts/generate_published_image_evidence.py --check`
- `python3 scripts/verify_release_asset_adoption.py --fixture fixtures/release-asset-adoption/asset-only-pass.json --asset-dir platform/generated --runtime metadata-only`
- `python3 scripts/generate_release_asset_adoption.py --check`
- `python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree`
- `python3 scripts/verify_platform_public_support_status.py --check`
- `scripts/release_check.sh`

## Known Limitations

- Localhost access depends on the host platform.
- Real model credentials stay inside the user's own Agent or platform runtime.
- Local GHCR pulls can be slower than CI and may need manifest-backed timeout evidence.

## Fixture Hashes

- `successful-release`: `08fd5bdc0d711cf0d658e88935967ef0ee502d7868ea4b3a8933ea9cf7a5c87c`
- `local-ghcr-pull-timeout`: `63343dee489195be68b295b7a2240b3de3f4a5bdf87de38667773ea8cae0c11d`
- `needs-repro-issue`: `5999991504607ced979742118db53db9185b58b095f47d94f7693ce91190fcda`
- `release-blocker`: `fc71e06b598ebb73e851355830667b53498488ab6fc1cc1fcae32a8b33fba9f2`
- `platform-blocked`: `353d05c515e82b00a10729a5e753dbdb493313ae7952bfb686af3a8732033823`
- `resolved-support-case`: `54769d613f36367010f65e22cd998bd7045d9ee6c01069f615b649ebd4851bc5`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
