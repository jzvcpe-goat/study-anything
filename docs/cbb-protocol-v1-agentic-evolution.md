# Protocol v1 Agentic Evidence And Evolution Gate

Delivery Clearance may use models to reduce evidence work, but a model, retrieved
memory, or tool result is never the final trust source. Protocol v1 therefore isolates
Agentic discovery from deterministic authorization and publishes
`cbb.evolution-gate-receipt.v1` as the eighth canonical schema.

The governing rule is:

```text
Agent proposes.
Typed tools collect bounded metadata.
Quarantined memory supplies challengeable evidence.
Deterministic replay and distinct human roles decide.
The receipt records a local candidate; it never applies the change.
```

## Three Proof Surfaces

### Agentic Tool Boundary

The reference registry contains only three tool contracts:

| Tool | Effect | Authority |
| --- | --- | --- |
| `cbb.receipt.lookup` | read metadata refs | supporting evidence only |
| `cbb.memory.search` | query quarantined metadata | supporting evidence only |
| `cbb.evolution.propose` | emit a candidate proposal | proposal only |

Every contract forbids network access, filesystem writes, policy mutation, gate
decisions, and production mutation. Calls are bounded by input/output reference counts,
and untrusted inputs require an explicit quarantine acknowledgement. Unknown tools,
effect mismatches, oversized results, and attempts to request policy or gate authority
fail closed.

The deterministic fixture planner emits only typed calls. It cannot emit a final gate
decision and does not call a model. A future model-backed planner may produce the same
typed plan, but its authority remains identical.

## Memory Quarantine

Quarantined memory stores metadata, never raw retrieved content. Each entry carries:

- source and content digests;
- source trust level;
- verification or signature reference;
- observation and expiry timestamps;
- prompt-injection findings;
- policy-directive findings;
- counter-evidence references;
- an explicit supporting-evidence eligibility bit.

The query engine classifies every entry. An entry is ignored when it is expired,
untrusted, injected, policy-like, ineligible, or challenged by unresolved
counter-evidence. Counter-evidence is preserved rather than overwritten. Query output
always states:

```text
policy_override_allowed = false
trust_increase_allowed = false
raw_content_returned = false
```

Memory is evidence, not policy or truth. A retrieved instruction such as "ignore the
gate" is represented as a quarantine finding, not executed as an instruction.

## Evolution Proposal

An `EvolutionProposalV1` identifies the current and candidate digests, proposer,
target, evidence refs, memory refs, current/requested scope, and protected-boundary
impact flags. It contains no raw patch and is always `proposal_only=true`.

The local reference gate rejects a proposal that:

- touches hard denies;
- weakens required evidence;
- expands delivery scope or tool authority;
- changes verifier, signing, or revocation semantics;
- requests automatic apply or production mutation;
- uses an unknown or unsafe tool contract;
- lets the proposer provide its own reconstruction, risk acceptance, or maintainer
  approval.

Those changes require later protocol governance. They are not safely self-authorizable
inside this reference runtime.

## Required Controls

A proposal can reach `approved_for_local_candidate` only when all six controls pass:

1. deterministic replay;
2. bounded canary;
3. rollback rehearsal;
4. qualified human reconstruction;
5. risk-owner acceptance;
6. maintainer approval.

Failed controls block. Missing controls, unavailable proposal evidence, poisoned
memory, or unresolved counter-evidence return `needs_evidence`. The proposer must be
distinct from the human control actors. The local signer must also be distinct for an
approved candidate.

## Receipt Decisions

`cbb.evolution-gate-receipt.v1` has three decisions:

| Decision | Candidate state | Effect |
| --- | --- | --- |
| `block` | `rejected` | candidate cannot continue |
| `needs_evidence` | `pending` | evidence or control work is required |
| `approved_for_local_candidate` | `local_candidate` | eligible for explicit maintainer apply outside this receipt |

Every decision fixes these values:

```text
automatic_apply_allowed = false
production_apply_allowed = false
trust_kernel_mutation_performed = false
release_performed = false
explicit_maintainer_apply_required = true
```

The receipt and its local Ed25519 provenance both carry `maximum_scope=blocked`.
Approval therefore grants no AI delivery authority. It only records that a candidate
survived the declared local controls.

## Deterministic Replay And Signing

The evolution envelope is separately signed with local Ed25519 provenance. Offline
verification checks:

- envelope and decision digests;
- fixed verifier identity;
- deterministic tool and memory replay;
- deterministic evolution decision replay;
- signature and public-key fingerprint;
- validity window and supplied local revocation state;
- proposer/approver separation for approved candidates.

A valid signer cannot replace the computed decision with a weaker decision. Local
signatures prove only content integrity and embedded-key possession; they do not prove
third-party identity.

## CLI

Build from typed metadata input and an owner-only local private key:

```bash
python3 scripts/cbb_evolution_gate.py build \
  --input evolution-input.json \
  --private-key local-ed25519.key \
  --signer-id maintainer:local \
  --key-id key:local \
  --expires-at 2026-08-10T07:00:00Z \
  --replay-nonce evolution-replay-nonce-0001 \
  --output evolution-gate-receipt.json
```

Generate a deterministic fixture receipt:

```bash
python3 scripts/cbb_evolution_gate.py demo \
  --case approved-local-candidate \
  --output evolution-gate-receipt.json
```

## Verification

```bash
python3 scripts/generate_cbb_v1_agentic_assets.py --check
python3 scripts/verify_cbb_agentic_tool_boundary.py --check
python3 scripts/verify_cbb_memory_quarantine.py --check
python3 scripts/verify_cbb_evolution_gate.py --check
```

The deterministic fixtures cover:

- approved local candidate;
- missing human reconstruction;
- hard-deny modification;
- poisoned memory;
- proposer self-authorization;
- tool-authority expansion.

Negative checks also cover a correctly signed but deterministically incorrect decision,
signature tampering, local receipt revocation, output-bound inflation, raw-content
injection, and automatic-apply state inflation.

## Claim Boundary

This phase is a local, metadata-only reference skeleton. It performs no model call,
network request, policy apply, production mutation, customer action, or real memory
retrieval. It does not prove prompt-injection elimination, production sandboxing,
third-party signer identity, global revocation, safe autonomous self-evolution, protocol
conformance by another implementation, or independent security audit completion.
