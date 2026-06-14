# Study Anything Adopter Evidence Archive

Schema: `adopter-evidence-archive-v1`
Version: `v0.3.27-alpha`
Status: `pass`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

- Archive: `platform/generated/study-anything-adopter-evidence-archive.zip` sha256 `958d2d6c4a68ce6856a7130de1533216e5a1922d96c1e6aa05046bbc415ed700`

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

- `successful-release`: `2f5742568a326f43598ed269e60bcecf624b3318b93df32e35236e602249696f`
- `local-ghcr-pull-timeout`: `3f826a3f14d7f7516c21ab764c7e93044c9f10b53a5c33e5092d147e569f6221`
- `needs-repro-issue`: `dcbff6759035d9793a07240f725cfff1dcd9844a2f0fbb181b1ef1d59a7f6c12`
- `release-blocker`: `e9360b8675dc692db8cbb7d8478b86128514418f737eabbb9c076cf42ef7978e`
- `platform-blocked`: `776dfbad58fe73a2d136ed1f8e861f17548e9f4f03d9c58b036334453e3d4ced`
- `resolved-support-case`: `a004baf362ad2b89f58f5520a28f39ff665fc12146cb0f60f974820c6c8cd618`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
