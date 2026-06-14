# Study Anything Adopter Evidence Archive

Schema: `adopter-evidence-archive-v1`
Version: `v0.3.24-alpha`
Status: `pass`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

- Archive: `platform/generated/study-anything-adopter-evidence-archive.zip` sha256 `ed678b336053d180d817ab2426bc8b5e8f7435c7fe92a798cf63e012dadf96ca`

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

- `successful-release`: `b993e36823f12454ba9a78e7d7a409c38be2fd591f3b9b8989dc879670a014ad`
- `local-ghcr-pull-timeout`: `5fa0647a71d951ab5d9c2f8004c49268b6e5741ea0d87074c2e18ce382a90a6c`
- `needs-repro-issue`: `76bf3217a0f19a143b17f5d2ff1efa2d6378178ea43825d434e9097c276c6ed6`
- `release-blocker`: `0d65dc31702c35e187074a6d854c129e353149368f1c089e560d7adbaee54fd5`
- `platform-blocked`: `7213112abca050a15b00d90fd50698d0021add82f4937d0002fa610364caa400`
- `resolved-support-case`: `e952c9b64e339d02e929c9d35582f88c2479b8a74c16b2325867bceac5b47fd1`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
