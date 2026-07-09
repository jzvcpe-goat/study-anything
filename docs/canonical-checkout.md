# Canonical Checkout And Worktree Boundary

GitHub `main` is the source of truth. Use one ASCII-only checkout for Docker,
release validation, and product changes. Additional worktrees are disposable
feature or audit surfaces and must not be treated as newer merely because their
folder name looks familiar.

Before development:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git rev-list --left-right --count HEAD...origin/main
```

The expected development flow is:

1. Start from a clean worktree at current `origin/main`.
2. Create one `codex/` feature branch.
3. Preserve unrelated untracked files and old branches; do not copy them into a
   new feature by accident.
4. Run focused gates, the full release check, and GitHub CI from the same
   checkout.
5. After merge, return that worktree to clean `main` and verify the merge SHA.

If a local workspace is on a branch whose upstream is `[gone]`, stop product
work there. Preserve its branch and untracked files, then use a current
ASCII-only checkout. A detached `origin/main` checkout is acceptable as a
read-only compatibility surface, but new commits belong on a named `codex/`
branch in the canonical development worktree.
