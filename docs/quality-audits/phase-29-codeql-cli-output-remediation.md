# Phase 29 CodeQL CLI Output Remediation Audit

Audit date: 2026-07-10 PDT

Scope: remove the four clear-text logging alerts left by main-branch CodeQL
analysis `1463582162` after Phase 28 merged.

Authority: `通用质检方案.md`, reviewed in S0-S15 order.

## Executive Conclusion

- Main-branch alert ledger before this change: **4 open alerts**.
- Local remediation: **Pass; protected CI pending**.
- Zero-alert repository claim: **Not allowed until this change merges and a
  fresh main-branch analysis reports zero open alerts**.
- Independent external audit: **Still pending**.

## S0-S9 Scope And Security Boundary

- Alert #3, #4, and #24 point to machine-readable or operator-facing output in
  `scripts/check_env.py` after issue and path redaction.
- Alert #6 points to a metadata-only Gateway verifier receipt after its explicit
  forbidden-value check.
- These outputs are CLI return channels, not application logs. They now use
  explicit stdout or stderr writes instead of the generic `print` logging sink.
- Redaction, forbidden-value checks, error exits, and release-gate behavior are
  unchanged. No CodeQL query, severity, path, or workflow exclusion is added.
- No model call, production mutation, credential storage, or UI change is added.

## S10-S14 Evidence

| Gate | Result |
| --- | --- |
| Ruff | Pass on both changed scripts |
| Environment script regression | Pass; 41 tests |
| Gateway contract-only verifier | Pass |
| Gateway localhost runtime verifier | Pass |
| Generated evidence topology | Pass; 21 of 21 nodes converged |
| PR CodeQL | Pending |
| Post-merge main alert ledger | Pending; must be zero |

## S15 Decision

Merge only after protected checks pass and the PR merge reference introduces no
new CodeQL alert. After merge, require a new analysis for the resulting main
commit, then run the live GitHub security posture verifier. A green PR check is
not a substitute for a zero-alert main-branch ledger.
