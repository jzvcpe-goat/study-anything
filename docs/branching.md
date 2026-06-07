# Branching

Study Anything uses a small trunk-based workflow that keeps `main` release-ready while leaving room for focused API, Skill, agent-integration, docs, and future UI work.

## Permanent Branches

- `main`: protected, release-ready trunk. Every merge should pass API tests and the relevant API/Skill/Docker smoke checks.
- `release/vX.Y.Z`: short-lived stabilization branches for public tags when a release needs final validation.

## Working Branches

- `codex/ui-*`: isolated future UI feature branches. Use these only when the product delivery layer is being rebuilt outside the launch-critical API/Skill path.
- `feature/*`: contributor feature branches.
- `fix/*`: bug fixes and regressions.
- `docs/*`: documentation-only changes.
- `dependabot/*`: automated dependency updates.

Keep branches scoped to one shippable change. Delete merged branches after the PR is merged; keep release tags and active release branches.

## Pull Request Gates

Every PR should include:

- A short product-facing summary.
- Test evidence for the touched surface.
- Screenshots for visible UI changes when a PR intentionally touches a future UI branch.
- Security and privacy notes when data, agent configuration, plugin permissions, or deployment behavior changes.

Required checks for normal code changes:

- API unit tests.
- Docker or full-stack smoke test when the PR touches compose, release scripts, API startup, or agent integration paths.
- Skill demo or Agent smoke test when the PR touches CLI, Skill, or Bring Your Own Agent behavior.

## Dependency Branches

Dependencies are grouped by ecosystem so peer dependencies move together:

- GitHub Actions runtime: `actions/*`, `docker/*`.

If Dependabot opens split PRs that conflict with peer dependencies, close the split PRs after the grouped branch exists and keep the grouped PR as the source of truth.

## Releases

- Public releases are tagged as `vX.Y.Z` or `vX.Y.Z-alpha`.
- Do not move public tags after release publication.
- Release notes live under `docs/release-notes/`.
- Docker images are published from tags and `main`.
