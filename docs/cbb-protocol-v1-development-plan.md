# CBB Protocol v1 Development Plan

## 1. Objective

Build a credible Protocol v1 from the existing deterministic receipt ecosystem
without turning the project back into a standalone learning product, a static policy
checklist, or an Agent that approves itself.

Protocol v1 must make this decision reproducible:

```text
Given:
  candidate + scenario + policy + evidence + human capability
  + model capability + recipient + affected parties + history

Decide:
  the maximum delivery scope allowed now

Emit:
  a portable, claim-bounded, verifiable, expiring, revocable receipt
```

The implementation must preserve existing Dual Loop, Study Anything, Cognitive Loop,
platform pack, and release interfaces as compatibility adapters until migration
evidence supports removal.

## 2. Current Baseline

Current `main` already proves these local deterministic capabilities:

- Controlled Failure and Attention Reconstruction artifacts;
- Dual-Loop gate and Delivery Trust Receipt;
- Customer Handoff Package and offline package verification;
- CBB claim-boundary, trust-root, reviewer, risk-owner, decision, chain, and
  self-intake receipts;
- delivery-class and scenario matrices;
- local API, Skill, platform-Agent, Docker, static artifact, release, and security
  evidence;
- an external security audit preparation package;
- a deterministic conformance ZIP and package-independent second consumer.

What this baseline does not yet prove beyond the canonical contract and kernel
milestones:

- third-party implementation or standards-body adoption beyond this repository;
- independent human security audit completion;
- production or customer outcome trust.

## 3. Engineering Principles

1. **Protocol before product surface.** New UI, plugins, and hosted services wait
   unless they are needed to prove a protocol contract.
2. **Kernel before intelligence.** Deterministic schemas, canonicalization, policy,
   and verification precede RAG or Agentic automation.
3. **Proposal is not authority.** Models can discover, plan, call typed tools, and
   propose changes. They cannot approve a gate or modify hard denies.
4. **Trust can decrease.** Expiry, revocation, incidents, rollback failure, and
   counter-evidence are first-class.
5. **No receipt inflation.** Reduce and compose schemas rather than adding another
   receipt for every feature.
6. **Compatibility is explicit.** Old identifiers stay only behind a documented map,
   deprecation boundary, and migration test.
7. **Claims match evidence.** Local deterministic, platform, external audit, and real
   outcome evidence remain separate.
8. **The protocol distrusts itself.** Verifier, memory, reviewer, signer, and policy
   changes all have provenance and challenge paths.

## 4. Target V1 Schema Set

The public Protocol v1 surface should converge on eight canonical schema documents:

| Object | Responsibility |
|---|---|
| `cbb.trust-policy.v1` | Scenario, scope, hard denies, risk budget, roles, required evidence |
| `cbb.evidence-bundle.v1` | Typed, attributable evidence bound to subject and policy |
| `cbb.qualified-reconstruction.v1` | Scope-qualified human reconstruction result |
| `cbb.gate-decision.v1` | Deterministic allow, block, or needs-evidence decision |
| `cbb.delivery-trust-receipt.v1` | Portable claim-bounded delivery attestation |
| `cbb.receipt-provenance.v1` | Shared canonical digest, signer, expiry, replay, and revocation bindings |
| `cbb.delivery-outcome-receipt.v1` | Post-delivery result, incident, rollback, and challenge |
| `cbb.evolution-gate-receipt.v1` | Governed policy, recipe, or runtime change decision |

`cbb.receipt-provenance.v1` is embedded in delivery receipts and also published as a
shared schema so independent implementations can verify the binding contract.

Existing v0 artifacts remain supported through deterministic adapters:

```text
failure-contract-v1 + sandbox-receipt-v1
  -> cbb.evidence-bundle.v1

attention-reconstruction-summary-v1
  -> cbb.qualified-reconstruction.v1

dual-loop-gate-receipt-v1
  -> cbb.evidence-bundle.v1

cbb.trust-policy.v1 + cbb.evidence-bundle.v1
  + cbb.qualified-reconstruction.v1
  -> cbb.gate-decision.v1

delivery-trust-receipt-v1 + cbb.gate-decision.v1
  -> cbb.delivery-trust-receipt.v1
```

Mappings may narrow claims. They may never expand delivery scope.

## 5. Workstreams

### Workstream A: Protocol Core Convergence

Deliver:

- `apps/api/study_anything/cbb/protocol/` for canonical models and serialization;
- `apps/api/study_anything/cbb/kernel/` for deterministic policy evaluation;
- `platform/schemas/cbb/` for vendor-neutral JSON schemas;
- v0-to-v1 compatibility adapters;
- `scripts/cbb.py` or equivalent protocol CLI;
- conformance and migration receipts.

Key tests:

- deterministic canonical bytes across repeated runs;
- unknown or unsafe policy fields rejected;
- hard deny beats all positive evidence;
- scope ordering cannot be inverted;
- v0 mapping cannot increase scope;
- the kernel imports no model, Agent, RAG, browser, or network runtime.

### Workstream B: Provenance And Signing

Deliver:

- SHA-256 subject, policy, evidence, verifier, and package digests;
- local Ed25519 signing behind the existing optional crypto extra;
- explicit unsigned-development status;
- offline signature verification;
- expiry, replay, revocation, and signer-identity checks;
- tamper-evident receipt chain.

Key tests:

- one changed byte invalidates verification;
- wrong subject or policy digest blocks;
- expired and revoked receipts block outside policy;
- unsigned receipts cannot claim portable attestation;
- private keys, bearer tokens, cookies, signed URLs, prompts, and raw payloads are
  rejected from receipts.

### Workstream C: Scenario And Qualified Reconstruction

Deliver:

- delivery scenario and scope registry;
- recipient, affected-party, risk-owner, disclosure, appeal, and redress contracts;
- Minimum Reconstructable Unit templates;
- local, expiring Human Capability Profile;
- evidence-backed Model Capability Profile;
- reviewer qualification matrix without permanent global labels;
- vibe-coded app fixtures.

Required scenario fixtures:

1. personal local prototype with fake data;
2. public demo with no real users or sensitive data;
3. limited beta with disclosure and rollback;
4. paid customer candidate requiring qualified technical and operational review;
5. production candidate blocked until domain, security, deployment, and affected-party
   requirements pass;
6. regulated or irreversible scenario blocked by default.

### Workstream D: Outcome And Degradation

Deliver:

- outcome receipt ingestion;
- incidents, complaints, near misses, rollback results, and claim violations;
- Trust Recipe freeze and autonomy-ceiling reduction;
- receipt expiry and revocation;
- counter-evidence and challenge workflow;
- post-delivery sampling policy.

Key tests:

- incident narrows later scope;
- failed rollback revokes recipe promotion;
- stale capability evidence forces reconstruction;
- affected-party challenge remains distinct from risk-owner acceptance;
- trust cannot monotonically increase from pass count alone.

### Workstream E: Agentic Evolution With Isolation

Deliver only after A-D pass:

- typed tool registry with explicit read/write risk;
- evidence planner and scenario classifier interfaces;
- untrusted-input and prompt-injection boundary;
- quarantined RAG memory with provenance, expiry, and counter-evidence;
- policy and Trust Recipe proposal objects;
- bounded replay, canary, rollback, and evolution gate;
- runtime isolation verifier.

Forbidden:

- Agent output writing the final gate decision;
- RAG text overriding policy;
- the same Agent proposing, approving, signing, and releasing its own change;
- automatic hard-deny modification;
- production or customer mutation in reference fixtures.

### Workstream F: Conformance And Governance

Deliver:

- public test vectors and negative fixtures;
- reference verifier independent of the Study Anything adapter;
- second-implementation walkthrough;
- extension registry and version negotiation;
- spec change, deprecation, and security disclosure process;
- independent audit intake and signed report verification;
- neutral compatibility language.

## 6. PR Sequence

### PR 1: Canonical Models And Compatibility Map

- add the six pre-outcome canonical schemas;
- add canonical JSON encoding;
- map existing Dual Loop and delivery receipts to v1;
- add positive, blocked, stale, secret, and scope-expansion fixtures;
- keep all existing scripts working.

Gate:

```bash
python3 scripts/verify_cbb_v1_contracts.py --check
python3 scripts/verify_cbb_v0_compatibility.py --check
```

### PR 2: Deterministic Trust Kernel

- add policy evaluator and scope ordering;
- add hard denies, missing-evidence decisions, and claim-boundary checks;
- prove model/runtime imports are absent;
- route current CBB gate through the canonical kernel without changing compatibility
  output.

Gate:

```bash
python3 scripts/verify_cbb_v1_kernel.py --check
python3 scripts/verify_cbb_runtime_isolation.py --check
```

### PR 3: Provenance And Local Signing

- add digests, local signing, verification, expiry, and revocation references;
- add offline package verification and tamper fixtures;
- mark unsigned receipts as development-only.

Gate:

```bash
python3 scripts/verify_cbb_v1_provenance.py --check
python3 scripts/verify_cbb_v1_tamper_cases.py --check
```

### PR 4: Scenario And Qualification Policy

- add scoped reviewer, recipient, risk owner, affected party, disclosure, appeal, and
  redress fields;
- add Minimum Reconstructable Unit and capability profile contracts;
- add vibe-coding scenario fixtures from local demo to blocked production.

Gate:

```bash
python3 scripts/verify_cbb_v1_scenarios.py --check
python3 scripts/verify_cbb_v1_qualification.py --check
```

### PR 5: Outcome And Trust Degradation

- add outcome receipt, incidents, revocation, recipe freeze, and autonomy reduction;
- connect outcome evidence to later gate decisions;
- add post-delivery sample and counter-evidence fixtures.

Gate:

```bash
python3 scripts/verify_cbb_v1_outcomes.py --check
```

### PR 6: Agentic Evidence Runtime Skeleton

- add typed tool contracts and an isolated planner interface;
- add quarantined memory and proposal-only evolution flow;
- use deterministic fake planners first;
- prove Agent/RAG output cannot alter kernel decisions.

Gate:

```bash
python3 scripts/verify_cbb_agentic_tool_boundary.py --check
python3 scripts/verify_cbb_memory_quarantine.py --check
python3 scripts/verify_cbb_evolution_gate.py --check
```

**Status:** implemented as a deterministic metadata-only skeleton. The typed tool
allowlist, memory quarantine, six-control evolution gate, actor separation, local
signature, revocation, and deterministic decision replay are shipped. Approval stops
at `local_candidate`; no candidate is automatically applied.

### PR 7: Conformance Pack And Second Implementation

- publish schemas, vectors, verifier, migration map, and signed fixtures;
- prove a minimal independent consumer can verify receipts offline;
- add protocol governance and deprecation docs.

Gate:

```bash
python3 scripts/generate_cbb_v1_conformance_pack.py --check
python3 scripts/verify_cbb_v1_external_consumer.py --check
```

**Status:** implemented as local cross-implementation fixture conformance. The pack
contains all eight schemas, canonical and negative vectors, signed provenance and
evolution fixtures, version negotiation, extension authority rules, v0 migration, and
governance documents. The isolated second consumer imports no reference package code.

### PR 8: Controlled Real Adoption And Audit Intake

- pin exact release scope and external audit pack;
- ingest an independent signed audit report without self-certification;
- run shadow/dogfood/canary cases with outcome receipts;
- publish passes, blocks, incidents, and revocations separately.

Gate:

```bash
python3 scripts/verify_cbb_external_audit_intake.py --check
python3 scripts/verify_cbb_controlled_adoption_outcomes.py --check
```

## 7. Acceptance Matrix

| Area | Minimum passing condition | Evidence |
|---|---|---|
| Positioning | Public first view says open protocol and reference harness | `verify_cbb_positioning.py` |
| Contracts | Canonical schemas reject unsafe and ambiguous inputs | v1 contract verifier |
| Compatibility | Existing receipts map without scope expansion | v0 compatibility verifier |
| Kernel | Same inputs always produce same decision, with no model import | kernel/isolation verifier |
| Provenance | Tampering, expiry, replay, and revocation are detected | provenance verifier |
| Human control | Reconstruction is scope-qualified and not passive attention alone | qualification verifier |
| Scenario | New recipient, model, affected party, or impact reruns policy | scenario verifier |
| Outcomes | Incidents can lower or revoke trust | degradation verifier |
| Agentic runtime | Agent and RAG output cannot authorize or rewrite policy | runtime isolation verifier |
| Privacy | No secrets, raw payloads, prompts, hidden reasoning, or attention streams | privacy negative fixtures |
| Governance | Spec updates include migration, fixtures, rollback, and evolution receipt | conformance gate |
| External proof | Independent audit and real outcomes remain separate claims | audit/adoption receipts |

## 8. Quality Audit After Every PR

Use the Contract-First Product Audit Framework in `通用质检方案.md` as the
authoritative post-development checklist. Every PR quality note must cover:

- delivery boundary;
- source of truth;
- product contract;
- core user/release loop;
- data and receipt architecture;
- protocol/action surface;
- security, privacy, and permissions;
- legacy leakage classification;
- automated gates;
- migration and rollback;
- final Pass, Needs Changes, or Reject decision.

Do not replace this with a generic “tests passed” summary.

## 9. Risks And Countermeasures

| Risk | Countermeasure |
|---|---|
| Receipt becomes another pretty report | canonical digest, signature, verifier identity, tamper tests |
| Schema explosion | bounded eight-schema v1 surface and composition review |
| AI reviews itself | model-free final kernel and proposal/decision separation |
| Human gate becomes fatigue approval | Minimum Reconstructable Unit and scoped qualification |
| Memory poisoning | quarantine, provenance, expiry, counter-evidence, rollback |
| Trust only grows | incident feedback, revocation, recipe freeze, degradation |
| Protocol captured by one vendor | second implementation, public conformance, neutral governance |
| Old product framing returns | positioning gate and compatibility registry |
| Local pass overstated as production | explicit evidence classes and claim-boundary receipts |
| Independent audit treated as CI | external signed intake only; repository cannot self-certify |

## 10. Stop Conditions

Pause and require explicit human intervention when:

- a change would permit production mutation or automatic customer sending;
- a hard deny or Trust Kernel invariant is weakened;
- a compatibility break has no migration and rollback path;
- signing keys or private customer data would enter repository artifacts;
- an Agent would both propose and approve its own authority increase;
- legal, regulated, safety-critical, or irreversible use is proposed;
- external audit findings require risk acceptance rather than a clear remediation.

## 11. Next Codex Goal

```text
/goal Implement CBB Protocol v1 PR 8: controlled adoption and external audit intake.

Source of truth:
- README.md
- docs/protocol.md
- docs/trust-model.md
- docs/architecture.md
- docs/naming-and-compatibility.md
- docs/cbb-protocol-v1-development-plan.md

Objective:
Exercise the completed Protocol v1 stack in bounded shadow and dogfood scenarios,
while keeping independent audit intake and real-world outcomes distinct from local
conformance evidence.

Required:
1. Define metadata-only shadow and dogfood adoption receipts bound to exact Protocol v1
   package and conformance digests.
2. Add controlled pass, block, incident, rollback, revocation, and reopen fixtures.
3. Add an external-audit report intake contract that rejects self-certification,
   wrong commits, invalid signatures, incomplete scope, and open critical/high findings.
4. Keep audit-ready, audit-received, remediation-pending, and audit-closed states
   distinct; do not synthesize a passing external report.
5. Prove adoption evidence cannot expand customer or production scope.
6. Publish passes and failures with the same metadata-only outcome discipline.
7. Wire adoption and audit-intake verifiers into release and distribution packs.
8. Run the named Contract-First quality audit after implementation.

Claim boundary:
This PR may prove local shadow/dogfood workflow behavior and validate the structure of
an independently signed audit report if one is supplied. It must not invent an auditor,
claim the open audit is complete, authorize production, or generalize bounded outcomes.
```
