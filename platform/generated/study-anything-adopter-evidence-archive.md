# Study Anything Adopter Evidence Archive

Schema: `adopter-evidence-archive-v1`
Version: `v0.3.26-alpha`
Status: `pass`

This archive is a public, metadata-only handoff bundle for external adopters and
platform maintainers. It links release commands, CI expectations, Docker image
manifest checks, platform pack checksums, public support status, and maintainer
handoff steps without copying private learning data.

## Archive

- Archive: `platform/generated/study-anything-adopter-evidence-archive.zip` sha256 `627666569b8b7120c0a4823958225fbb18bbc50a91af65a62d7c0c406e9906c6`

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

- `successful-release`: `fc91018264096b31532c62c31893406ced03540dc4cb25459e2f87ea2e542d4e`
- `local-ghcr-pull-timeout`: `8eebe95a0266f265f0c4d3b3a19500576320d08e4a50e408773a7845610a3e92`
- `needs-repro-issue`: `3fbcb4bc9b10275a7ecf945edf2bad6dcce7d3d47c0e25c3caf454e012f2a217`
- `release-blocker`: `232a1e988fe4bba711ec861b8a4da19e714b6f6226d65d5ecabb15913c5c3995`
- `platform-blocked`: `93af4defb9620e0bcd6e04e0205a34a817401271d364ce05325b5558c86fe58c`
- `resolved-support-case`: `7da7b336bd07061e28fdda3e76cb3933ce388f6e1312f0bb1f23da857801c995`

## Privacy

No raw source text, learner answers, Agent prompts, Agent endpoint secrets, real
model keys, personal profile data, support bundle private payloads, or private
browser/video/app context are included. Real model credentials remain inside the
user-owned Agent or platform runtime.
