# Branching

Study Anything uses a small trunk-based workflow that keeps `main` release-ready while leaving room for focused UI, API, docs, and release work.

## Permanent Branches

- `main`: protected, release-ready trunk. Every merge should pass API tests, web build checks, and the relevant smoke checks.
- `release/vX.Y.Z`: short-lived stabilization branches for public tags when a release needs final validation.

## Working Branches

- `codex/ui-*`: Codex-built UI feature branches. Use these for larger frontend iterations, screenshots, and visual QA.
- `feature/*`: contributor feature branches.
- `fix/*`: bug fixes and regressions.
- `docs/*`: documentation-only changes.
- `dependabot/*`: automated dependency updates.

Keep branches scoped to one shippable change. Delete merged branches after the PR is merged; keep release tags and active release branches.

## Pull Request Gates

Every PR should include:

- A short product-facing summary.
- Test evidence for the touched surface.
- Screenshots for visible UI changes.
- Security and privacy notes when data, agent configuration, plugin permissions, or deployment behavior changes.

Required checks for normal code changes:

- API unit tests.
- Web build.
- Docker or full-stack smoke test when the PR touches compose, release scripts, API startup, or agent integration paths.

## Dependency Branches

Dependencies are grouped by ecosystem so peer dependencies move together:

- React runtime: `react`, `react-dom`, `@types/react`, `@types/react-dom`.
- Vite toolchain: `vite`, `@vitejs/*`.
- GitHub Actions runtime: `actions/*`, `docker/*`.

If Dependabot opens split PRs that conflict with peer dependencies, close the split PRs after the grouped branch exists and keep the grouped PR as the source of truth.

## Releases

- Public releases are tagged as `vX.Y.Z` or `vX.Y.Z-alpha`.
- Do not move public tags after release publication.
- Release notes live under `docs/release-notes/`.
- Docker images are published from tags and `main`.
