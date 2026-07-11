# Phase 36 Delivery Clearance Outcomes Audit

Audit date: 2026-07-10 PDT

Project: Delivery Clearance Protocol v1 post-delivery outcome receipts and trust
degradation

Repo: `jzvcpe-goat/study-anything`

Branch: `codex/v0.3.296-delivery-outcomes`

Audit base: `7826169d5b6cdc28550da56c6d6e277235b4e669`

Preview: canonical JSON schemas, deterministic fixtures, CLI output, generated
platform packs, and static documentation; no standalone frontend or hosted service is
introduced.

Auditor: Codex

Authority: operator-provided `通用质检方案.md`, reviewed in S0-S15 order.

## Executive Conclusion

Decision: **Pass locally after two P1 corrections. Canonical checks, generated-pack
convergence, all bounded/skip-clean-clone release modes, and the full 980-test API
suite pass; a single full clean-clone release run, protected CI, merge, and the
independent human audit remain pending.**

The implementation closes the Protocol v1 post-delivery loop with
`cbb.delivery-outcome-receipt.v1`. It verifies an allowed, locally signed source
clearance package; records a bounded sample, typed outcome events, affected-party
challenges, and rollback status; then deterministically emits one of:

- `maintain_current_ceiling`;
- `narrow_scope`;
- `freeze_recipe`;
- `revoke_clearance`.

No action can increase the source scope. Failed rollback and substantiated claim or
evidence violations revoke the original source handle. Open affected-party challenges
freeze the recipe and require follow-up. A bounded sample containing only confirmed
clean observations maintains only the existing ceiling and does not prove customer
success.

The Contract-First audit found and removed one P1 defect before packaging: the first
implementation bound the signed source package but did not sign the Outcome Receipt
itself. The final design separately signs the outcome envelope with local Ed25519
provenance, expiry, replay nonce, verifier identity, and an independently revocable
outcome handle. A source revocation update is returned only after both source and
outcome receipts verify offline.

The final code-level review found a second P1 defect: a valid local signer could create
an under-degraded outcome because verification checked the signature but did not replay
the deterministic degradation policy. The evaluator and verifier now share one pure
policy derivation. Verification rejects signed policy drift, resolved adverse events
cannot be treated as clean observations, and a source that expired after handoff may be
used only as a historical validity anchor without regaining delivery authority.

No unresolved P0 or P1 finding remains. Residual P2 limits are explicit: fixtures are
synthetic, local signer identity is self-asserted, revocation is supplied-registry
local state, sampling evidence is metadata-only, and affected-party follow-up is a
required action rather than proof of completed redress.

## S0-S3 Source, Boundary, And Product Contract

| Check | Result | Evidence |
| --- | --- | --- |
| Active source | Pass | Isolated worktree on `codex/v0.3.296-delivery-outcomes` |
| No-touch boundary | Pass | Protected historical workspace was not modified |
| Product contract | Pass | Delivery Clearance remains the final protocol before responsibility transfer |
| Included delivery | Pass | Canonical outcome schema, evaluator, signing, fixtures, CLI, verifier, docs, and release/audit wiring |
| Excluded delivery | Pass | No production action, customer send, hosted service, policy auto-mutation, or global revocation |
| External checkpoint | Pending | Independent human security audit issue #414 remains open and incomplete |

Claimed and implemented:

- signed-source verification before outcome evaluation;
- separately signed outcome envelope;
- bounded sampling and explicit limitations;
- incident, complaint, near-miss, claim violation, evidence invalidation, and
  affected-party challenge types;
- rollback result and deterministic trust action precedence;
- source/outcome local revocation checks;
- counter-evidence refs and replay/reconstruction/risk-owner follow-up requirements.

Explicitly excluded:

- customer-success or quality-improvement claims;
- external signer identity, certificate authority, or globally synchronized
  revocation;
- legal, security, regulatory, or domain certification;
- real production deployment, real affected-party consent, appeal adjudication, or
  redress completion;
- Agentic authority to choose trust actions or mutate policy.

## S4-S8 Loop, Information, Data, And Action Surface

The implemented outcome loop is:

1. load an allowed offline provenance package;
2. verify its canonical digests, gate replay, signature, expiry, and supplied local
   revocation state;
3. validate the post-delivery sampling window, selection ref, counts, and limitations;
4. validate typed events and rollback evidence;
5. apply deterministic revoke/freeze/narrow/maintain precedence;
6. preserve or reduce the previous scope, never increase it;
7. sign the outcome envelope locally;
8. verify source binding, outcome signature, expiry, and outcome revocation before
   producing any source-registry revocation update.

| Core object | Storage/format | Lifecycle boundary |
| --- | --- | --- |
| Source clearance | Signed canonical offline package | Must be allow, current, unrevoked, and untampered |
| Sampling record | Strict metadata-only JSON | Bounded by time window, population, selection ref, and limitations |
| Outcome event | Strict metadata-only JSON | Reported, confirmed, resolved, or disputed |
| Rollback result | Strict metadata-only JSON | Not required, unattempted, succeeded, partial, or failed |
| Trust update | Nested canonical contract | Monotonic non-increasing scope only |
| Outcome provenance | Local Ed25519 metadata | Expiring, replay-bound, and locally revocable |
| Outcome receipt | Canonical JSON Schema | Binds source, observations, action, signature, privacy, and claims |

The CLI exposes only `build` and deterministic `demo`. `build` requires a signed source
package, observation input, owner-only local private key, signer/key refs, expiry, replay
nonce, and output path. It performs no model call, network request, production write,
or automatic customer action.

## S9 Security, Privacy, And Permission

| Boundary | Result |
| --- | --- |
| Source authority | Offline signature, digest, deterministic gate, expiry, and local revocation verified |
| Outcome authority | Separate local signature and source-binding digest verified |
| Outcome decision | Shared pure degradation policy replayed; local signature is not sufficient |
| Historical source | Expired source may anchor outcome history but cannot authorize new delivery |
| Scope growth | Structurally rejected |
| Failed rollback | Source clearance revoked |
| Substantiated claim/evidence violation | Source clearance revoked |
| Affected-party challenge | Future delivery frozen; follow-up required |
| Pass-count/time inflation | Unknown fields rejected; trust increase fixed false |
| Raw customer/source/report content | Excluded |
| Secrets and credentials | Safe-metadata rejection plus privacy literals |
| Automatic policy mutation | Not implemented and explicitly disclaimed |

Local signatures prove key possession and content integrity only. The source and
outcome revocation registries are caller-supplied local state; they are not represented
as global coordination. Outcome evidence may be collected by an Agent, but the Agent
cannot choose or override the deterministic action.

## S10-S13 Commercial, Production, UI, Copy, And Legacy

- Payment, entitlement, hosted tenancy, production deployment, customer notification,
  and real-world incident response are outside this phase.
- There is no new UI. Human-facing output remains short, claim-bounded JSON/docs while
  deep evidence stays machine-verifiable.
- Public wording remains Delivery Clearance / AI Delivery Clearance Protocol. `cbb.*`
  and `study_anything` remain compatibility schema and package namespaces only.
- The v0 receipt family is not deleted or expanded. Outcome receipts require the
  canonical signed source package, so legacy unsigned, tampered, revoked, or non-allow
  evidence fails closed. Later expiry permits only historical outcome binding and
  never restores delivery authority.
- Rollback is removal of the new schema/module/scripts plus restoration of the previous
  seven-to-six contract report. Existing stable v0 IDs and imports remain unaffected.

## S14 Automated Evidence

| Gate | Current result |
| --- | --- |
| Canonical schema/fixture freshness | Pass; seven schemas and nine pre-delivery fixtures |
| Outcome fixture freshness | Pass; five deterministic cases |
| Outcome verifier | Pass; fourteen negative/invariant checks |
| Outcome signature and local revocation | Pass |
| Source binding tamper | Pass; substituted digest detected |
| Trust inflation | Pass; scope and pass-count inflation rejected |
| Affected-party and rollback bypass | Pass; both rejected |
| Focused Protocol v1 tests | Pass; 43 tests |
| Ruff | Pass across `apps/api` and `scripts` |
| Strict mypy | Pass on ten protocol/outcome/CLI source files |
| Platform/adoption/audit pack convergence | Pass; generated topology converged and read-only check passed 21/21 |
| External audit preparation pack | Pass; 90 declared files, 92 ZIP entries, independent audit still incomplete |
| Full API suite | Pass; 980 tests in 75.361 seconds |
| Dual-Loop partial release | Pass; explicitly not full release validation |
| CBB Protocol partial release | Pass with dependency-backed v1 Outcome gates; explicitly not full release validation |
| Skip-clean-clone release | Pass across the complete local gate chain; explicitly partial |
| Full clean-clone release | Not completed; one run passed clean-clone then exposed stale generated evidence that is now fixed, and the retry hit the bounded 900-second dependency-install timeout |
| Protected GitHub checks | Pending PR |
| Independent human security audit | Pending issue #414 |

The first two full-suite attempts exposed stale Delivery Trust case-pack descendants,
and a later attempt exposed stale platform bundle/adoption manifests. They were
regenerated in dependency order and the final suite passed. The 21-node generated
evidence topology also passed, but its own claim boundary does not cover every
generated repository artifact; the release gates remain the authoritative backstop for
the case-pack consumer chain until that dependency is represented in the topology.

## Gate Matrix

| Rule | Gate | Merge blocking |
| --- | --- | --- |
| Signed source required | `verify_cbb_v1_outcomes.py --check` | Yes |
| Outcome envelope signed and untampered | outcome verifier and unit tests | Yes |
| Signed outcome action is deterministically replayed | shared policy verifier and malicious-signer test | Yes |
| Scope never increases | outcome schema, evaluator, and negative fixture | Yes |
| Resolved adverse event cannot restore scope | shared policy and unit test | Yes |
| Failed rollback revokes | outcome verifier | Yes |
| Affected-party challenge freezes | outcome verifier | Yes |
| Local revocation invalidates original package | provenance replay in outcome verifier | Yes |
| No trust from elapsed time/pass count | strict schema and negative fixture | Yes |
| Generated distribution current | platform/adoption/audit/topology gates | Yes |

## S15 Decision

Proceed to PR publication. Local merge gates are satisfied: the Outcome schema, docs,
five fixtures, generated verifier report, release receipt fields, platform/adoption
packs, and external-audit preparation pack converge; the bounded release modes pass;
the skip-clean-clone gate chain and full unit suite are green. Full release validation
is not claimed because no single clean-clone run completed every phase. Merge only
after protected GitHub checks pass. After merge, repin the external-audit issue to the
merge commit and final pack digest without changing the incomplete-audit boundary.

This audit authorizes only the next local milestone, isolated Agentic evidence and
evolution boundaries. It is not a production clearance, customer-outcome proof,
global revocation service, completed redress record, full-release claim, or independent
security audit.
