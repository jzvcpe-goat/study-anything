# Study Anything Adopter Evidence Archive

Schema: `adopter-evidence-archive-v1`
Version: `v0.3.28-alpha`
Status: `pass`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

- Archive: `platform/generated/study-anything-adopter-evidence-archive.zip` sha256 `1c2b6223d0fc7f87e1a56c825123c083a365d4f868cf03af4400c5ae23b298dc`

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

- `successful-release`: `70baea7547b1f96c7899b1fc8f77b94c49c912bf771974a051a00bdc1f3a0e53`
- `local-ghcr-pull-timeout`: `79f00eb378f32cc7d6abebfb0d47cb8049473140df2b8b6985aff16c8fae921f`
- `needs-repro-issue`: `2a86cfd687b7c045b3d43ec82b0324283b2d11c0e3e59ad447014671f1c216c3`
- `release-blocker`: `fa6f447c61b1f350caa50de01066b855d261a8709177ae4c5516602e24da2691`
- `platform-blocked`: `0e3dc29e3c47a31590a3d4104c1647ddcd05607442050c7de5925abed5dc34ae`
- `resolved-support-case`: `99660a3da6ce3cedc1cf7c44f01fc985eab0145c426a328434b57764ab71c71d`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
