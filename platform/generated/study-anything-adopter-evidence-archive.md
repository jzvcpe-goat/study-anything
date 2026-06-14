# Study Anything Adopter Evidence Archive

Schema: `adopter-evidence-archive-v1`
Version: `v0.3.22-alpha`
Status: `pass`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

- Archive: `platform/generated/study-anything-adopter-evidence-archive.zip` sha256 `83b21e35c467bf0ef79ef1767f50ecdad71a05def3e5570495041bcc43f32908`

## Reproduction Commands

- `python3 scripts/verify_adopter_evidence_archive.py --check`
- `python3 scripts/generate_adopter_evidence_archive.py --check`
- `python3 scripts/verify_published_image_evidence.py --check`
- `python3 scripts/generate_published_image_evidence.py --check`
- `python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree`
- `python3 scripts/verify_platform_public_support_status.py --check`
- `scripts/release_check.sh`

## Known Limitations

- Localhost access depends on the host platform.
- Real model credentials stay inside the user's own Agent or platform runtime.
- Local GHCR pulls can be slower than CI and may need manifest-backed timeout evidence.

## Fixture Hashes

- `successful-release`: `5740e24a238c7ac5dc25cfb9feba213de34445b96a8add34471053381dcbe9a5`
- `local-ghcr-pull-timeout`: `d691ddd9861cfd0756acffc92f7d8cd9a724b9c752b47737194a31d736227ee8`
- `needs-repro-issue`: `f01e49759a28320fddc561e68693b9c1267324a5291366a208a91576d7f9d3e6`
- `release-blocker`: `da85e9ef55aac1f17169b7c9fc2675c271d93896e1a78b5bb0b0afc4b19d1c01`
- `platform-blocked`: `931377d0a3d046ba359d8845e0b8793327d6d41ddf6c0088999b27eb4cd4294b`
- `resolved-support-case`: `7e656fdc0cec1603263e64491b9e7a966316251691371e77b7366f2db77122bd`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
