# Adopter Evidence Archive

Study Anything v0.3.21-alpha adds `adopter-evidence-archive-v1` as a
metadata-only handoff bundle for external adopters, platform maintainers, and
reviewers.

The archive turns release proof into one reproducible package:

- public support status and maintainer dashboard hashes
- platform adoption pack checksum
- Kimi, Codex, and WorkBuddy pack checksums
- CI and docker image verification commands
- local GHCR pull-timeout fallback evidence
- `adopter-evidence-fixture-v1` fixtures for common support states
- maintainer handoff checklist and release reproduction commands

Generate and verify it with:

```bash
python3 scripts/generate_adopter_evidence_archive.py --check
python3 scripts/verify_adopter_evidence_archive.py --check
python3 scripts/verify_adopter_evidence_archive.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip
```

The generated files are:

- `platform/generated/study-anything-adopter-evidence-archive.json`
- `platform/generated/study-anything-adopter-evidence-archive.md`
- `platform/generated/study-anything-adopter-evidence-archive.zip`
- `platform/generated/study-anything-adopter-evidence-archive.sha256`

## Privacy Boundary

The archive may publish schema names, release version, file hashes, command
strings, fixture ids, platform labels, known limitations, and checklist items.

It must not include raw source text, learner answers, Agent prompts, Agent
endpoint secrets, real model keys, personal profile data, support bundle private
payloads, or private browser/video/app context. Real model credentials remain
inside the user's own Agent or platform runtime.

## Fixture Mapping

The `adopter-evidence-fixture-v1` fixtures map public support situations into
safe archive evidence:

- `successful-release`
- `local-ghcr-pull-timeout`
- `needs-repro-issue`
- `release-blocker`
- `platform-blocked`
- `resolved-support-case`

Each fixture includes only a public status, a required public command, allowed
public fields, and false privacy flags.
