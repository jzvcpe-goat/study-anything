# Phase 30 CBB Protocol Positioning And V1 Plan Audit

Audit date: 2026-07-10 PDT

Project: Cognitive Black Box Protocol positioning, compatibility boundary, and
Protocol v1 development plan

Repo: `jzvcpe-goat/study-anything`

Worktree: `study-anything-cbb-protocol-positioning`

Branch: `codex/v0.3.290-cbb-protocol-positioning`

Audit base: `b7d00487157d`

Preview: none; this phase changes protocol documentation, package metadata,
generated distribution assets, and deterministic verification rather than a UI
surface.

Auditor: Codex

Authority: `通用质检方案.md`, reviewed in S0-S15 order.

## 1. Executive Conclusion

Decision: **Pass for this positioning and migration-plan slice after protected
CI**.

The repository now presents Cognitive Black Box Protocol as the product and
protocol identity, CBB Reference Harness as the local implementation, Study
Anything as the Human Reconstruction / Learning Adapter, and Cognitive Loop as
an internal evidence and evolution workflow. A deterministic positioning gate
prevents the old top-level framing from returning.

This decision does not mean that canonical Protocol v1, production customer
delivery, hosted commercial readiness, or an independent security audit has
been completed.

Largest remaining risks:

1. The independent human-led security audit is still pending; the repository
   only produces an audit-ready metadata package.
2. The final local release run used `--skip-clean-clone`; its receipt explicitly
   forbids a full clean-clone release claim.
3. Canonical Protocol v1 models, provenance/signing, outcome-driven trust
   degradation, isolated agentic evolution, and open conformance governance are
   development milestones, not shipped claims.

Next required work:

1. Merge this positioning boundary only after protected `api-tests` and
   `compose-smoke` pass.
2. Implement PR 1 from `docs/cbb-protocol-v1-development-plan.md`: canonical
   protocol models plus an explicit v0 compatibility map.
3. Rebind the independent audit coordination issue and pack digest to the
   resulting main commit without marking the audit complete.

Do not:

1. destructively rename compatibility identifiers before wrappers, migration,
   and downstream consumers exist;
2. build an agentic self-evolution runtime before the deterministic Trust
   Kernel and provenance layer are independently verifiable;
3. describe local receipts, AI review, or a human approval click as production
   certification.

## 2. Delivery Boundary Audit

| Category | Items | Evidence | Risk |
| --- | --- | --- | --- |
| Included | Protocol-first README and core docs; naming/compatibility policy; v1 roadmap and Codex goal; deterministic positioning verifier; package/API branding; refreshed platform/plugin assets | `README.md`, `docs/protocol.md`, `docs/naming-and-compatibility.md`, `docs/cbb-protocol-v1-development-plan.md`, `scripts/verify_cbb_positioning.py` | Low after CI |
| Excluded | Canonical v1 runtime implementation, production mutation, customer sending, hosted control plane, payment, legal/security certification, external audit execution | Explicit claim boundaries in README, protocol, roadmap, trust model, and release receipt | Must remain excluded |
| Claimed but unproven | Open ecosystem adoption, independent interoperability, production customer outcome improvement, signed public receipt network | Roadmap M2-M7 only | P1 if presented as shipped |
| Leaking into product | Historical `study-anything` package/repository names and `cognitive_loop_*` compatibility identifiers | `docs/naming-and-compatibility.md` | Controlled compatibility debt, not current product identity |

Verdict: **Pass**. The delivery states what changed and what remains future
work. No local or generated evidence is presented as production proof.

## 3. Source Of Truth Audit

| Area | Current Truth | Evidence | Risk |
| --- | --- | --- | --- |
| Active repository | `jzvcpe-goat/study-anything` | Git remote and release assets | None |
| Active worktree | `study-anything-cbb-protocol-positioning` | Isolated worktree status | None |
| Active branch | `codex/v0.3.290-cbb-protocol-positioning` | `git branch --show-current` | None |
| Base commit | `b7d00487157d` | `git rev-parse HEAD` before phase commit | Protected CI still pending |
| Product truth | Protocol, trust model, architecture, roadmap, naming boundary | Core docs are cross-linked from README | Low |
| Runtime truth | Existing Dual Loop and delivery trust implementation remains v0 reference-harness evidence | Existing contracts, scripts, fixtures, and verifiers | Must not be confused with complete v1 |
| Deprecated mirrors | Historical product framing in release notes and audit history | Excluded from current-framing gate but retained as history | Low; intentional |

Verdict: **Pass**. The `/Users/james/Documents/学习系统` workspace was not
modified by this phase.

## 4. Product Contract Audit

### Claimed product identity

Cognitive Black Box Protocol is an open, local-first receipt protocol for
scoped AI delivery trust. The repository also contains the CBB Reference
Harness and adapters.

### Actual implemented identity

The current implementation supplies deterministic metadata contracts,
controlled-failure and human-reconstruction evidence, Dual Loop gates,
Delivery Trust and Customer Handoff receipts, release integration, platform
packs, and Study Anything learning flows. It is a local reference harness, not
an industry-wide trust authority.

### Intended primary users

- protocol implementers and verifier authors;
- AI delivery operators and risk owners;
- adapter and Agent-platform maintainers;
- humans reconstructing a delivery boundary.

### Intended core loop

1. Declare subject, scenario, policy, risk budget, and claim boundary.
2. Collect controlled-failure evidence and qualified human reconstruction
   evidence through physically isolated loops.
3. Run the deterministic gate.
4. Emit a scoped, provenance-bound receipt.
5. Observe outcomes, degrade or revoke trust when necessary, and propose
   bounded recipe evolution.

### Implemented loop

The repository implements the first four steps in v0 forms and provides
metadata-only handoff and audit packages. Outcome-based degradation and
self-evolution remain planned v1 work.

### Contract mismatch

No P0 mismatch exists for this positioning slice. The main remaining mismatch
is temporal: the product thesis is protocol v1, while several runtime objects
retain v0 or historical names. The compatibility map and staged PR plan make
that mismatch explicit instead of hiding it.

## 5. User Loop And Information Architecture Audit

The repository has no required standalone frontend. The primary journey is a
developer/operator loop:

1. read the protocol and select or define a scoped policy;
2. generate or ingest evidence through the reference harness;
3. run deterministic verifiers;
4. inspect the gate/receipt and its claim boundary;
5. pass a compatible package to an adapter or downstream Agent;
6. later attach an outcome receipt and update trust state.

Current documentation information architecture is now:

| Level | Role |
| --- | --- |
| Protocol | Normative objects, trust invariants, claim boundaries, conformance |
| Reference Harness | Deterministic local implementation, fixtures, verifiers, generated receipts |
| Adapters | Study Anything, platform Agents, plugins, and handoff/export bridges |
| Historical compatibility | Existing package names, script names, schemas, and release evidence |

Broken points are documented rather than concealed: there is no complete v1
outcome loop, no public conformance program, and no production customer control
plane.

## 6. Data And Local-First Audit

| Object | Current State | V1 Requirement | Gap / Action |
| --- | --- | --- | --- |
| Trust policy | Existing failure contracts and scenario policies | `cbb.trust-policy.v1` | Canonicalize in PR 1 |
| Evidence bundle | Dual Loop and delivery evidence references | `cbb.evidence-bundle.v1` | Add explicit source/provenance map |
| Qualified reconstruction | Attention/reconstruction summaries | `cbb.qualified-reconstruction.v1` | Preserve passive-vs-active evidence distinction |
| Gate decision | Dual Loop and delivery trust gate receipts | `cbb.gate-decision.v1` | Define scope ordering and compatibility projection |
| Delivery receipt | `delivery-trust-receipt-v1` | `cbb.delivery-trust-receipt.v1` | Add canonical wrapper without deleting v0 |
| Outcome receipt | Partial customer outcome evidence | `cbb.delivery-outcome-receipt.v1` | Implement trust degradation inputs |
| Evolution receipt | Existing Cognitive Loop evolution artifacts | `cbb.evolution-gate-receipt.v1` | Prevent self-authorization |

Current artifacts are local-first, metadata-only, schema-versioned, exportable,
and digest-bound where supported. The phase adds no browser state, cloud
database, raw source capture, or hidden upload path. Migration is additive:
v1 objects must project to or reference v0 objects until compatibility gates
prove downstream consumers have moved.

## 7. Protocol And Agent Action Surface Audit

| Surface | Current | Required Boundary | Result |
| --- | --- | --- | --- |
| Deterministic verifier | `verify_*.py --check` and release gates | Agent output cannot override gate result | Pass |
| Platform packs | Codex, Kimi, WorkBuddy, Hermes, OpenAPI bundles | Adapter instructions cannot expand receipt scope | Pass for current packs |
| Agentic reasoning | Existing review/eval/evolution helpers | Proposal and evidence discovery only | Bounded; v1 isolation still planned |
| Human reconstruction | Study Anything and attention reconstruction artifacts | Active reconstruction is stronger than dwell-time metadata | Pass as current contract |
| Customer handoff | Delivery Trust and Customer Handoff receipts | No automatic send, publication, or production mutation | Pass |
| Protocol self-update | Roadmap only | Evolution proposal, deterministic verifier, canary, rollback, human/risk-owner acceptance | Not shipped |

External eval receipts remain supporting evidence and cannot independently
approve a delivery. The deterministic Trust Kernel remains the final software
gate.

## 8. Security, Privacy, And Permission Audit

| Resource | Current Permission / Handling | Required | Risk |
| --- | --- | --- | --- |
| Model and Agent credentials | Owned by user/platform Agent; excluded from receipts | Never enter public CBB evidence | Pass |
| Raw source and customer payloads | Excluded from metadata packages | Explicit opt-in payload path plus separate verification if ever added | Pass for current scope |
| Attention stream | Physically isolated from AI sandbox; raw stream excluded | Only delayed, scoped reconstruction summary may cross bridge | Pass |
| Gate authority | Deterministic verifier | Agent may propose but not self-approve | Pass for current core |
| Production mutation | Disabled by current packages and receipts | Separate production control and risk owner required | Pass for current scope |
| Audit claim | `ready_for_independent_audit`, `audit_completed=false` | External human reviewer and signed report | Pending external checkpoint |

The phase does not weaken hard denies, hosted identity boundaries, secret
scanning, container policy, or receipt privacy. The protocol explicitly
distrusts AI self-review, human approval without reconstruction, trust memory,
and its own evolution proposals.

## 9. Backend, Payment, And Production Audit

No backend schema, database migration, payment flow, entitlement system, or
production deployment authority is added here.

| Area | Current | Required For Production | Decision |
| --- | --- | --- | --- |
| Deployment | Local reference harness, self-host artifacts, published-image evidence | Environment-specific operator approval and monitored rollout | Not claimed |
| Database | Existing application stores and hosted-tenancy contracts | Production datastore operations, backup, restore, and isolation validation | Not claimed |
| Monitoring | Metadata observability and reliability receipts | Production SLOs, alert ownership, incident response | Not claimed |
| Payment | No protocol payment requirement | Separate commercial product entitlement design | Out of scope |
| External audit | Audit-ready pack | Independent execution, signed report, remediation and retest | Pending |

Verdict: **Needs Changes for production or hosted commercial launch**, which is
compatible with the Pass decision for this bounded documentation and protocol
positioning phase.

## 10. UI And Product Copy Audit

No UI or design-system changes are part of this phase, so screenshot or
Playwright evidence would not answer the delivery blocker.

Current product-language replacements:

| Historical Top-Level Framing | Current Role |
| --- | --- |
| Study Anything as the product | Human Reconstruction / Learning Adapter |
| Cognitive Loop System as the product | Internal evidence and evolution workflow |
| Learning workflow kernel | Adapter-owned source-bound learning workflow |
| Neural Sync / Publish / Teams | Hosted sync / artifact publishing / team workspaces |
| Catalyst tier | Contributor sponsorship |

`scripts/verify_cbb_positioning.py --check` scans current documentation, source,
plugin, and generated surfaces while permitting historical text only in
explicit naming definitions, release history, and prior quality audits.

## 11. Legacy Leakage Audit

| File / Module Class | Category | Reason | Action | Gate |
| --- | --- | --- | --- | --- |
| `study-anything` repo/package/API routes | Preserve for compatibility | Existing users and release assets depend on identifiers | Document as compatibility-only | `verify_cbb_positioning.py` |
| `cognitive_loop_*` scripts and schemas | Adapt | Valuable evidence/evolution implementation, old top-level semantics | Keep entrypoints; wrap under canonical v1 objects | Protocol contract and compatibility tests |
| Study Anything learning flows | Adapt | Valid reconstruction adapter, not the protocol | Keep under adapter docs and packs | Adapter tests and pack verifiers |
| Historical release notes and audits | Preserve | Immutable evidence history | Exclude from current-framing ban | Positioning verifier allowlist |
| Neural commercial labels | Delete from current source | No compatibility contract requires them | Replaced with descriptive capability names | Positioning verifier banned terms |
| Old top-level README/architecture wording | Delete | Misstates product identity | Rewritten protocol-first | Positioning verifier required text |

Final technical renames require wrappers, migration documentation, downstream
consumer evidence, one compatibility release, and a rollback path. No rename is
allowed merely to make the tree look cleaner.

## 12. Automated Gate Matrix

| Rule | Script / Test | Blocks Merge? | Evidence |
| --- | --- | --- | --- |
| Canonical product identity | `python3 scripts/verify_cbb_positioning.py --check` | Yes through release check | Pass; 5,871 current and generated text files scanned, zero findings |
| Protocol contracts | `verify_cbb_protocol_contracts.py --check` | Yes | Pass in release receipt |
| Equal-weight Dual Loop | Four Dual Loop verifiers | Yes | Pass in release receipt |
| Delivery trust | Delivery Trust verifiers | Yes | Pass in release receipt |
| Customer handoff boundary | Customer Handoff verifiers | Yes | Pass in release receipt |
| Generated asset freshness | `generated_evidence_topology.py --check` | Yes | Pass; 21/21 nodes |
| Adapter marketplace semantics | `verify_workbuddy_plugin_marketplace.py --check` | Yes | Pass |
| API regression | `PYTHONPATH=apps/api/tests ... -m pytest apps/api/tests` | Yes | 939 passed; one deprecation warning |
| Python quality | `ruff check .` | Yes | Pass |
| Patch validity | `git diff --check` | Yes | Pass |
| Local release stack | `release_check.sh --skip-clean-clone` | Yes for this slice | Exit 0; partial claim only |
| Protected repository checks | `api-tests`, `compose-smoke`, security checks | Yes | Pending PR |
| Independent security audit | External human review and signed report | Blocks production claim | Pending |

Two exploratory pytest calls without `PYTHONPATH=apps/api/tests` failed during
collection because `_path.py` was not importable. No tests ran in those calls.
The canonical invocation then collected and passed all 939 tests. The existing
Starlette/httpx deprecation warning remains non-blocking and should be handled
as dependency maintenance rather than hidden.

The release receipt is authoritative:

```text
status=completed
exit_code=0
full_release_check_completed=false
clean_clone_completed=false
dependency_install_completed=false
cbb_protocol_verifiers_passed_individually=true
dual_loop_verifiers_passed_individually=true
delivery_trust_verifiers_passed_individually=true
customer_handoff_verifiers_passed_individually=true
```

Its claim boundary states that clean-clone adoption was skipped and a full
`release_check.sh` pass must not be claimed.

## 13. Migration And Rollback Audit

Migration path:

1. merge protocol-first language and the no-old-framing gate;
2. add canonical v1 models without deleting v0 schemas or commands;
3. emit compatibility projections and verify both representations;
4. migrate platform packs and adopters one surface at a time;
5. deprecate old entrypoints only after usage and release evidence show no
   remaining exclusive consumer;
6. delete an old identifier only after no-import/no-reference gates and a
   rollback release exist.

Rollback for this phase is document- and metadata-level: revert the positioning
commit and regenerate all platform/plugin evidence from the previous templates.
No user data migration or production schema rollback is required.

## 14. Acceptance Matrix

| Area | Minimum Passing Condition | Status |
| --- | --- | --- |
| Product | README first screen says Cognitive Black Box Protocol and distinguishes protocol, reference harness, and adapters | Pass |
| Naming | Study Anything and Cognitive Loop are scoped roles, not competing product identities | Pass |
| Compatibility | Historical identifiers remain usable and are explicitly documented | Pass |
| Protocol | Stable Trust Kernel and adaptive Evolution Layer are separated | Pass as contract |
| Trust | Controlled failure and human reconstruction retain equal weight | Pass |
| Privacy | Metadata-only defaults and no-secret/no-raw-attention boundaries remain enforced | Pass |
| Distribution | Generated platform, plugin, audit, and adoption assets match source docs | Pass |
| Verification | Positioning, topology, API, style, patch, and partial release gates pass | Pass |
| Clean clone | Full dependency install and release flow from a disposable clone | Not run in final release command |
| External audit | Independent reviewer returns signed commit-bound report | Pending |
| Protocol v1 | Seven canonical objects and compatibility map are implemented | Planned PR 1 onward |
| Production | Customer outcomes, incident feedback, monitoring, revocation, and operator approval are proven | Not claimed |

## 15. Recommended Build Order

1. Canonical v1 models and v0 compatibility map.
2. Deterministic Trust Kernel and scope algebra.
3. Receipt provenance, local signing, tamper tests, and revocation metadata.
4. Scenario policy, affected parties, qualified reconstruction, and risk owner.
5. Outcome receipts and trust degradation.
6. Isolated Agentic Runtime for proposal and evidence collection only.
7. CBB-on-CBB evolution gates and canary rollback.
8. Public conformance suite and vendor-neutral governance.

## 16. Bottom Line

This phase successfully removes the old product framing from current source and
distribution surfaces while preserving compatibility and historical evidence.
It also turns the next development step into an executable v1 plan with gates,
stop conditions, and a ready Codex goal. It passes as a protocol-positioning
and migration-plan change; it does not complete Protocol v1 or establish
production trust.
