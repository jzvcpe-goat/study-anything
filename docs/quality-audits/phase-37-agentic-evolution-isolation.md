# Phase 37 Agentic Evolution Isolation Audit

Audit date: 2026-07-11 PDT

Project: Delivery Clearance Protocol v1 isolated Agentic evidence and proposal-only
evolution gate

Repo: `jzvcpe-goat/study-anything`

Branch: `codex/v0.3.297-agentic-evolution-boundary`

Audit base: `e81a5939ece11d8df7e4331b98b5f5ac6e9f8da9`

Auditor: Codex

Authority: operator-provided `通用质检方案.md`, reviewed in S0-S15 order.

## Executive Conclusion

Decision: **Local implementation, full API suite, generated-distribution convergence,
and full clean-clone release gates pass. Protected GitHub and independent-human
checkpoints remain pending.**

The implementation adds `cbb.evolution-gate-receipt.v1` as the eighth canonical
Protocol v1 object. Agentic planning is isolated behind three typed tools. Tool results
remain supporting evidence only. Retrieved memory is metadata-only, quarantined, and
classified by provenance, expiry, observation time, injection findings, policy-like
content, and counter-evidence. The deterministic evolution gate then requires replay,
canary, rollback, qualified human reconstruction, risk-owner acceptance, and maintainer
approval.

Even a passing gate emits only `approved_for_local_candidate`. It grants no delivery
scope, performs no policy apply, and requires an explicit maintainer-controlled apply
path that is outside this phase. A valid local signature cannot replace deterministic
decision replay.

No unresolved P0 or P1 finding is currently known. During code review, future-dated
memory and post-issuance plan/proposal timestamps were identified as a temporal evidence
gap and corrected before packaging. The verifier now ignores not-yet-observed memory,
and the canonical receipt rejects proposal, plan, or memory-query timestamps later than
issuance.

Residual P2 limits remain explicit:

- fixtures use a deterministic fake planner and do not execute a real model;
- memory source-trust and protected-impact classifications are supplied metadata refs,
  not independent source resolution or semantic patch analysis;
- local signer, proposer, approver, risk-owner, and maintainer identities are
  self-asserted references;
- tool contracts prove a pure local allowlist, not an operating-system or production
  sandbox;
- prompt-injection findings are metadata inputs, not proof that every injection can be
  detected;
- the receipt records a candidate but does not implement or verify the later apply
  mechanism;
- the generated-evidence topology proves its declared 21-node distribution graph, not
  every older generated handoff artifact; the full release gate surfaced and required
  explicit refreshes for those additional chains before passing;
- global revocation, cross-process replay prevention, second-implementation
  conformance, and independent audit completion remain outside this phase.

## S0-S3 Source, Boundary, And Product Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Active source | Pass | Isolated worktree on `codex/v0.3.297-agentic-evolution-boundary` |
| No-touch boundary | Pass | Protected historical workspace was not modified |
| Product contract | Pass | Delivery Clearance remains the final protocol; Agentic runtime is not the trust root |
| Included delivery | Pass | Eighth schema, tool registry, planner, memory quarantine, evolution gate, local signing, CLI, fixtures, tests, docs, and gates |
| Excluded delivery | Pass | No model call, RAG retrieval, network, policy apply, production mutation, customer send, or global revocation |
| External checkpoint | Pending | Independent human security audit issue #414 remains open and incomplete |

## S4-S8 Loop, Information, Data, And Action Surface

The implemented loop is:

1. create a typed proposal-only plan;
2. validate every call against the fixed tool registry;
3. classify quarantined memory without returning raw content;
4. emit a metadata-only evolution proposal;
5. check protected-boundary impact and actor separation;
6. require six deterministic/human controls;
7. emit block, needs-evidence, or approved-local-candidate;
8. sign the envelope locally;
9. replay tool, memory, and evolution decisions during verification;
10. perform no apply or release action.

| Surface | Authority boundary |
| --- | --- |
| Receipt lookup | Read metadata refs only |
| Memory search | Query quarantined metadata only |
| Evolution proposal | Candidate proposal only |
| Memory | Supporting evidence; never policy or truth |
| Evolution decision | Deterministic evaluator plus required human controls |
| Local signature | Integrity and embedded-key possession only |
| Approved candidate | Local candidate only; no delivery or automatic-apply authority |

## S9 Security, Privacy, And Permission

| Boundary | Result |
| --- | --- |
| Unknown or mismatched tool | Rejected |
| Network/filesystem/policy/gate/production tool authority | Structurally false |
| Untrusted input without quarantine | Rejected |
| Expired or future memory | Ignored |
| Prompt-injection or policy-directive memory | Ignored |
| Pending counter-evidence | Preserved and blocks evidence use |
| Hard-deny or verifier/signing change | Blocked |
| Scope or tool-authority expansion | Blocked |
| Proposer self-authorization | Blocked |
| Missing reconstruction/risk-owner/maintainer evidence | Needs evidence |
| Valid signer with altered decision | Deterministic replay fails |
| Automatic apply or delivery scope | Structurally absent/blocked |

The code-level pure boundary contains no model/provider, network, retrieval, subprocess,
filesystem I/O, or legacy runtime dependency. That static proof is not a production
sandbox or a complete prompt-injection defense.

## S10-S13 Commercial, Production, UI, Copy, And Legacy

- No payment, entitlement, hosted tenancy, deployment, or customer workflow is added.
- No new UI is added. JSON/docs keep human decisions short while machine evidence can
  remain deep.
- Delivery Clearance remains the public identity. `cbb.*` and `study_anything` remain
  compatibility namespaces.
- Existing Cognitive Loop evolution artifacts remain compatible evidence sources; they
  do not become canonical approval or automatic-apply paths.
- Rollback is removal of the Agentic package, eighth schema, fixtures, scripts, and
  generated reports. Existing seven canonical objects and v0 compatibility IDs remain
  unchanged.

## S14 Automated Evidence

| Gate | Current result |
| --- | --- |
| Canonical schemas | Pass; eight schemas |
| Agentic evolution fixtures | Pass; six deterministic cases |
| Agentic tool boundary | Pass; eleven checks |
| Memory quarantine | Pass; fifteen checks including future-evidence rejection |
| Evolution gate | Pass; thirteen checks |
| Focused Protocol v1 tests | Pass; 51 tests |
| Ruff | Pass across `apps/api` and `scripts` |
| Strict mypy | Pass on fourteen Protocol/Agentic/CLI source files |
| Runtime isolation | Pass on seven pure kernel/policy files |
| Platform/adoption/audit convergence | Pass; declared 21-node topology converged |
| Full API suite | Pass; 988 tests in 78.012 seconds |
| Partial release modes | Pass; CBB Protocol-only and Dual-Loop-only |
| Skip-clean-clone release | Pass; explicitly partial and not a full-release claim |
| Full clean-clone release | Pass; receipt records full, clean-clone, and dependency-install completion |
| Protected GitHub checks | Pending PR |
| Independent human security audit | Pending issue #414 |

## Gate Matrix

| Rule | Gate | Merge blocking |
| --- | --- | --- |
| Tool results are supporting evidence only | `verify_cbb_agentic_tool_boundary.py --check` | Yes |
| Poisoned/expired/future/contested memory cannot authorize | `verify_cbb_memory_quarantine.py --check` | Yes |
| Protected changes and self-authorization block | `verify_cbb_evolution_gate.py --check` | Yes |
| Six controls required for local candidate | evolution verifier and unit tests | Yes |
| Valid signature cannot override replay | evolution verifier | Yes |
| Approved candidate never auto-applies or gains delivery scope | schema, verifier, and unit tests | Yes |
| Generated distribution remains current | platform/adoption/audit/topology gates | Yes |

## S15 Decision

Do not publish or merge until the pending protected GitHub checks pass. After merge,
repin external-audit issue #414 to the merge commit and final audit-pack digest without
changing its incomplete-audit status.

This audit authorizes only the next local milestone after all merge gates pass:
vendor-neutral conformance fixtures and a second independent verifier. It is not a
production clearance, automatic policy-apply approval, safe autonomous self-evolution
claim, prompt-injection proof, external identity proof, or independent security audit.
