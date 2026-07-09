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

- CI runs Ruff across the Python package, tests, scripts, and plugins.
- CI runs strict mypy for the two explicit local API security targets while
  skipping traversal into third-party dependency stubs.
- Full-package strict mypy is not claimed yet. Existing dynamic artifact and
  optional-integration modules still have tracked annotation debt; expanding
  the type-check scope must happen by fixing those errors, not by globally
  suppressing them.
