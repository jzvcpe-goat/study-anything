# Public Support Status

Study Anything v0.3.22-alpha adds `public-support-status-v1` as the
publishable maintainer status layer. It turns the private support desk and
onboarding dashboard into a public summary that early adopters can read without
sharing learning content or Agent secrets.

Run:

```bash
python3 scripts/generate_platform_public_support_status.py --check
python3 scripts/verify_platform_public_support_status.py --check
python3 scripts/verify_platform_public_support_status.py \
  --pack platform/generated/study-anything-platform-adoption-pack.zip
```

The machine-readable public report is:

```text
platform/generated/study-anything-public-support-status.json
```

The public maintainer dashboard views are:

```text
platform/generated/study-anything-public-maintainer-dashboard.json
platform/generated/study-anything-public-maintainer-dashboard.md
```

## What Can Be Public

- platform id and public status
- schema names and release version
- copyable verification commands
- release-blocker fixture ids and fixture hashes
- SLA labels and next public action
- documented platform limitations

## What Must Stay Private

- raw source text
- learner answers
- Agent prompts
- real Agent endpoints
- real model keys or judge keys
- browser, video, app, or personal profile context
- full support bundle payloads

## Status Linkage

Each maintainer label has a `public-status-linkage-fixture-v1` fixture under:

```text
fixtures/platform-status-links/
```

These fixtures prove that `intake`, `needs-repro`, `confirmed`,
`blocked-by-platform`, `docs-fix`, `release-blocker`, and `resolved` can be
published as public status without exposing private support fields.

## Acceptance

Public support status is ready only when:

- `public-support-status-v1` passes.
- `public-maintainer-dashboard-v1` passes.
- every `public-status-linkage-fixture-v1` fixture is present and privacy-safe.
- the adoption pack includes the public status generator, verifier, dashboard,
  docs, and fixtures.
- no private learning material or user-owned Agent secret appears in public
  status evidence.
