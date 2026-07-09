# Unreleased Main Development Line

This file records changes on `main` after the tagged `v0.3.31-alpha` release.
It is not a release tag or published-image claim.

## Product

- Cognitive Black Box / Dual-Loop Trust Harness is the public product center.
- Study Anything remains the compatible learning adapter, Python package, API
  namespace, and repository distribution name.

## Security

- Docker API publication defaults to `127.0.0.1`.
- Browser cross-origin access is disabled unless exact trusted origins are set.
- Production or non-loopback exposure requires bearer-token mode.
- CLI requests can read the private API token from environment or `.env` and
  never place it in the API URL.
- Public status and plugin responses do not expose local absolute data paths.

## Claim Boundary

These changes harden a private local/self-host API. They do not implement
hosted accounts, tenant isolation, SSO, billing, paid services, production
mutation, or a realtime hosted console.

## Engineering Gates

- `generated_evidence_topology.py` now checks the complete declared release-distribution evidence
  chain in one run and reports every stale node instead of stopping at the first failure.
- Refresh mode orders hard dependencies and explicitly converges the adoption-pack consumer feedback
  edges over at most three passes. Its receipt excludes command output, environment values, secrets,
  source text, answers, and local paths.
- CI and the release gate now verify deterministic self-host soak aggregation; Compose smoke runs a
  short real health window before backup/restore rollback.
- `self-host-soak-receipt-v1` records availability, latency, failure categories, consecutive failures,
  and observed recovery without response bodies, tokens, URLs, source text, answers, or local paths.
- The self-host launcher now stops early with a non-destructive recovery message when a regenerated
  `.env` no longer matches an existing Postgres volume; it never resets the volume automatically.
- The soak command refuses to forward a locally loaded API token to a non-loopback host unless the
  operator explicitly confirms the destination with `--allow-network-token`.
- Health probes reject HTTP redirects instead of forwarding authorization to another origin.
- CI runs Ruff across the Python package, tests, scripts, and plugins.
- CI runs strict mypy for the two explicit local API security targets while
  skipping traversal into third-party dependency stubs.
- Full-package strict mypy is not claimed yet. Existing dynamic artifact and
  optional-integration modules still have tracked annotation debt; expanding
  the type-check scope must happen by fixing those errors, not by globally
  suppressing them.

The short soak does not prove a multi-hour production SLO, incident response, retention enforcement,
or disaster recovery across every source-build and published-image environment.
