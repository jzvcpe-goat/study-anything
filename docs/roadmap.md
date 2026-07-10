# Roadmap / 路线图

## North Star

CBB Protocol should become a vendor-neutral way to answer one question:

> Given this candidate, policy, evidence, human capability, model capability,
> recipient, affected parties, and history, how far may the result propagate now?

认知黑箱协议要成为一个厂商中立的回答方式：在当前候选物、策略、证据、人类能力、
模型能力、接收者、受影响者和历史条件下，这个结果现在可以传播到哪一层现实？

The protocol succeeds when implementations can reduce repeated review friction
without weakening evidence, hiding failure, or letting an Agent authorize itself.

## Current Baseline

The repository already contains a broad deterministic alpha:

- Dual-Loop contracts and negative fixtures;
- Delivery Trust Receipt and Customer Handoff Package;
- CBB claim-boundary, trust-root, reviewer, risk-owner, decision, receipt-chain,
  self-intake, and delivery-scenario receipts;
- local API, Skill, platform-Agent, Docker, and static artifact adapters;
- release, adoption, security, and external-audit preparation evidence.

This breadth is useful, but Protocol v1 requires convergence. The next phase reduces
parallel terminology, defines canonical schemas, adds provenance and outcome
semantics, and isolates intelligent evidence discovery from deterministic authority.

The public tagged binary/image line remains `v0.3.31-alpha` until another tag is cut.
Current `main` is later development, not a published-image claim.

### Historical Distribution Evidence

The following v0.3 distribution contracts remain compatibility evidence for the
Study Anything adapter and published alpha assets. They are maintained and verified,
but they do not define the Protocol v1 roadmap:

- `platform-field-adoption-rehearsal-v1`;
- `platform-support-triage-v1`;
- `platform-onboarding-readiness-v1`;
- `public-support-status-v1`;
- `published-image-evidence-v1`;
- `adopter-evidence-archive-v1`.

## Priority Rule

Until Protocol v1 core gates exist, pause expansion of:

- standalone frontend or realtime console productization;
- new platform plugin families;
- new learning-experience features;
- hosted account, billing, or marketplace products;
- automatic production mutation or customer sending.

Existing adapters remain supported and verified. New work must strengthen the
protocol spine or close a release, security, conformance, or real-adoption gap.

## M0: Positioning And Compatibility Boundary

**Goal:** make every public entry point describe the same protocol-first contract.

Deliver:

- canonical README, product positioning, architecture, trust model, and roadmap;
- naming and compatibility registry;
- Study Anything documented only as Human Reconstruction / Learning Adapter;
- Cognitive Loop documented only as an internal evidence/evolution workflow;
- generated HTML branding updated to CBB Protocol;
- `verify_cbb_positioning.py --check` in the CBB release gate;
- GitHub description and topics aligned after merge.

Exit criteria:

- no current public source uses the obsolete Cognitive Loop top-level brand;
- first-view copy leads with open protocol and local reference harness;
- compatibility identifiers remain documented and tested;
- historical release notes and audit records remain unchanged as history.

## M1: Canonical Protocol v1 Core

**Goal:** converge the current receipt families into a minimal public schema set.

Canonical objects:

- `cbb.trust-policy.v1`;
- `cbb.evidence-bundle.v1`;
- `cbb.qualified-reconstruction.v1`;
- `cbb.gate-decision.v1`;
- `cbb.delivery-trust-receipt.v1`;
- `cbb.receipt-provenance.v1`.

Deliver:

- schema definitions and canonical JSON serialization;
- deterministic Trust Kernel library;
- compatibility mappings from existing Dual Loop and CBB v0 receipts;
- migration verifier and negative fixtures;
- a protocol CLI independent of the Study Anything workflow;
- conformance receipt showing current adapters can emit or map to v1.

Progress:

- canonical schemas, deterministic JSON, v0 compatibility adapters, and the
  pass/missing/hard-deny/stale/secret/malformed/naive-timestamp/invalid-state/
  scope-expansion fixture matrix are implemented in PR 1;
- the deterministic policy evaluator, hard-deny and evidence-state matrix,
  static runtime-isolation gate, and v0 gate routing are implemented in PR 2;
- the protocol CLI and independent conformance consumer remain later milestones.

Exit criteria:

- policy plus evidence deterministically reproduces a gate decision;
- v0 mappings cannot expand scope or weaken claim boundaries;
- unknown fields, secret-like content, stale evidence, and hard-boundary violations fail;
- model calls are impossible in the kernel path.

## M2: Provenance, Signing, And Tamper Evidence

**Goal:** make a receipt more than another AI-generated report.

Deliver:

- subject, policy, evidence, verifier, and package digests;
- unsigned development mode and locally signed attestation mode;
- signature verification and tamper tests;
- receipt-chain ordering, expiry, and revocation references;
- signer and verifier identity boundary;
- offline package verification.

Exit criteria:

- changed subject, policy, evidence, or receipt bytes invalidate verification;
- an unsigned receipt cannot claim portable attestation status;
- replayed or expired receipts are rejected outside policy;
- key material and private payloads never enter public receipts.

## M3: Scenario, Qualification, And Affected-Party Policy

**Goal:** replace static roles with scoped, evidence-backed capability and delivery
requirements.

Deliver:

- scenario classification and delivery-scope ordering;
- recipient, risk owner, affected party, disclosure, appeal, and redress fields;
- project- and boundary-scoped reviewer qualification;
- human and model capability evidence with expiry and counter-evidence;
- Minimum Reconstructable Unit templates;
- vibe-coded app fixtures from personal demo through production candidate.

Exit criteria:

- creation permission never implies production delivery permission;
- qualification is local, evidence-backed, challengeable, and expiring;
- new recipient, model, affected party, or impact forces policy reevaluation;
- high-scope delivery blocks without the required independent roles.

## M4: Outcome Receipts And Trust Degradation

**Goal:** connect pre-delivery claims to real outcomes so trust can go down as well as
up.

Deliver:

- `cbb.delivery-outcome-receipt.v1`;
- incident, rollback, complaint, near-miss, and claim-violation fields;
- autonomy ceiling reduction;
- receipt expiry, revocation, and recipe freeze;
- bounded post-delivery sampling;
- counter-evidence and outcome-to-policy feedback.

Exit criteria:

- a recorded incident can revoke or narrow later handoff authority;
- failed rollback blocks recipe promotion;
- trust never increases solely from elapsed time or accumulated pass count;
- affected-party outcomes can challenge the original risk-owner decision.

## M5: Isolated Agentic Evolution Runtime

**Goal:** use modern model capabilities to reduce evidence friction without turning
the runtime into the trust root.

Deliver:

- typed, allowlisted function-call registry;
- scenario and evidence-planning Agents;
- quarantined RAG over receipt and failure memory;
- provenance, expiry, and source-trust levels for memory;
- boundary-update and Trust Recipe proposals;
- bounded replay, canary, and rollback;
- `cbb.evolution-gate-receipt.v1` for CBB-on-CBB changes.

Exit criteria:

- Agent output cannot directly approve a gate or modify hard denies;
- untrusted RAG cannot overwrite policy;
- tool output is typed, bounded, attributable, and redacted;
- every self-change is a proposal until deterministic and required human gates pass.

## M6: Conformance And Open Governance

**Goal:** let independent implementations interoperate without trusting this
repository as the only authority.

Deliver:

- public conformance suite and signed fixtures;
- protocol versioning and deprecation policy;
- extension and compatibility rules;
- independent implementation guide;
- security disclosure and spec-change process;
- vendor-neutral compatibility language and trademark policy;
- reproducible external-audit package for the protocol core.

Exit criteria:

- a second implementation can produce receipts accepted by the reference verifier;
- no vendor-specific runtime is required for conformance;
- spec changes include migration, negative fixtures, and an evolution receipt;
- independent reviewers can reproduce the conformance result offline.

## M7: Controlled Real-World Adoption

**Goal:** gather outcome-backed evidence without overstating production trust.

Deliver:

- shadow and dogfood scenarios;
- limited canary handoffs with explicit risk owners and affected-party handling;
- independent human security audit execution and signed report intake;
- outcome, incident, rollback, and revocation drills;
- external adopter interoperability reports;
- scope-specific readiness decisions.

Exit criteria:

- local deterministic proof, platform proof, independent audit, and real outcome
  evidence remain separate in every claim;
- customer or production scope is never inferred from a lower-scope pass;
- failures and revocations are published with the same rigor as passes;
- no broad “AI trusted” claim is made.

## Release Gates

Every milestone must add or strengthen:

1. contract/schema validation;
2. positive and negative fixtures;
3. deterministic verifier output;
4. privacy and secret rejection;
5. claim-boundary checks;
6. compatibility and migration evidence;
7. release-check wiring;
8. a quality audit using the project Contract-First framework.

`--cbb-protocol-only` and `--skip-clean-clone` are partial modes. Their receipts must
remain explicit about skipped work. A full release claim requires every full release
phase, including clean clone and dependency installation, to complete.

## Detailed Plan

The PR-level implementation sequence, acceptance matrix, risk register, and next
Codex goal are in [CBB Protocol v1 Development Plan](cbb-protocol-v1-development-plan.md).

Canonical contracts, the deterministic Trust Kernel, and local provenance/signing
are implemented. The next ordered milestone is scenario and qualification policy;
outcome-driven trust degradation and isolated Agentic evolution follow it.
