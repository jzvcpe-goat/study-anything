# Study Anything Adopter Evidence Archive

Schema: `adopter-evidence-archive-v1`
Version: `v0.3.21-alpha`
Status: `pass`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

- Archive: `platform/generated/study-anything-adopter-evidence-archive.zip` sha256 `8a3de5a5759fa717c5b8b9c65f2408c04183f8e6fcf1021488cb4f0e307d8e5c`

## Reproduction Commands

- `python3 scripts/verify_adopter_evidence_archive.py --check`
- `python3 scripts/generate_adopter_evidence_archive.py --check`
- `python3 scripts/verify_external_adoption.py --pack platform/generated/study-anything-platform-adoption-pack.zip --copy-worktree`
- `python3 scripts/verify_platform_public_support_status.py --check`
- `scripts/release_check.sh`

## Known Limitations

- Localhost access depends on the host platform.
- Real model credentials stay inside the user's own Agent or platform runtime.
- Local GHCR pulls can be slower than CI and may need manifest-backed timeout evidence.

## Fixture Hashes

- `successful-release`: `0b026c0c8984ed920f5b569865604a3590270571ce0f580fb452de842497c423`
- `local-ghcr-pull-timeout`: `cd5832798db34aff1a66a839a2516acee411b46b4f30603dc4c49272e8e278a9`
- `needs-repro-issue`: `f9f9fe636a70575cd0a7d0a8bc3f810399f625263b574a70c9eb6dfbead8b788`
- `release-blocker`: `dbb440437431aa10e5956d9314d2bccc3921785c20cda75570943e22fceb1eba`
- `platform-blocked`: `ebf2c90f53eed7cd7ec800145ddbb26de6278206619fa58988a8d44862b5b59c`
- `resolved-support-case`: `c1e430df763b04a7fc38043654b521a08d93d4fcfa3e3be41c224ebd592756ef`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
