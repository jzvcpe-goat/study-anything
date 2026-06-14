# Study Anything Adopter Evidence Archive

Schema: `adopter-evidence-archive-v1`
Version: `v0.3.25-alpha`
Status: `pass`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

- Archive: `platform/generated/study-anything-adopter-evidence-archive.zip` sha256 `3f615c2b78f545cf8038b2839c98eed095bbe6b2a48fda338e772b3754c02f26`

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

- `successful-release`: `323dbbeaa637941b90829252a7bdfcb8b733d1388d68781cffb7ec9f25a5f5c0`
- `local-ghcr-pull-timeout`: `6552359cd990be6314a7b4e462d0bc9f6b8fa6d6d235b3848aaa782e331fa62d`
- `needs-repro-issue`: `09575eda8b23aff7255af662b611264056287ac8dfc95aa77514cf46c53a87e9`
- `release-blocker`: `c6bfc678ff94a1d081d705a2e284a71fa0d6deff2d6d3570bd0f1ddea6678370`
- `platform-blocked`: `6f7937178f58757181bee42bb62e06216e78e5f33215e28cfe77cd56f06d04e1`
- `resolved-support-case`: `63c34ac5fb1c3cb85bf7ad0b59011bf05db0087405ec27fb5aa7c67c2fe544f2`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
