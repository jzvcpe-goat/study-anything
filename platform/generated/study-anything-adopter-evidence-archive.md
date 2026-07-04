# Study Anything Adopter Evidence Archive

Schema: `adopter-evidence-archive-v1`
Version: `v0.3.31-alpha`
Status: `pass`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

- Archive: `platform/generated/study-anything-adopter-evidence-archive.zip` sha256 `c95e314098277051bffa238e6118d7d810f9bbf792dc1f4bd1d586bf110a2363`

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

- `successful-release`: `70fd70f5a30bf22242e3d7c199398a669ddb339ca470521dea70c8e1478668d4`
- `local-ghcr-pull-timeout`: `4458e2db322fcf369f6ecdb8ce6d7cb8a151b8e30793bdc1c6e4e32dba3945d0`
- `needs-repro-issue`: `610c54aa868c0986b7c9a3f632737738789080f1026197f64d4211b119cc8f10`
- `release-blocker`: `4525b07c381a4ca3994309a487cfc9610bacedc785113ed8e55223e325852c3d`
- `platform-blocked`: `7371a137bdf96325f80eb4273930bc195949915a870f56a1cc75eb173e0dd200`
- `resolved-support-case`: `c0e399190dd5ced7227b49339e41ac97df718d12cf99ccea6fdd4d3aa2a78723`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
