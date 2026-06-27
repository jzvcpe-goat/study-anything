# Study Anything Adopter Evidence Archive

Schema: `adopter-evidence-archive-v1`
Version: `v0.3.29-alpha`
Status: `pass`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

- Archive: `platform/generated/study-anything-adopter-evidence-archive.zip` sha256 `f9429a00ba721833ef14abb47c9a016835b9e0e9b64876dbdcb55b61d8e98e59`

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

- `successful-release`: `02b8c93278865dbc9c7cc6ab0e66b44ed1e797d7f1a65022ad45439a4f3c54d1`
- `local-ghcr-pull-timeout`: `0a7a2efe1bbb7fb0e29297af9f070203b7db3a96658ea674534eae8b5ae4d3c6`
- `needs-repro-issue`: `349edd9bbddb5a761d75c0595e7330896c02dc428bfcfbc2a1848a655d677764`
- `release-blocker`: `d0aa6de4d84826f57dcaff90a4fb323abbc574305e83cfca403b43c519de8c27`
- `platform-blocked`: `df1cd6e5c191746a0e797c01d6acb6cff9916df1e69cbafaf54ff5c612443e04`
- `resolved-support-case`: `b1d3f23842d9474eb36a2eda3e3324ed347a46e41e071435625bff652d87964b`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
