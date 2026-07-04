# Product Runway

The project should now move from release-stack self-intake maintenance back to
the product core: Cognitive Black Box / Dual Loop as a trust protocol for AI
delivery.

## Current Reset

The release-stack chain is verifiable, but the next valuable work is not another
automatic self-intake. The release evidence machinery has done its job when it
can prove:

- what changed;
- which verifier covered it;
- which public evidence package carries it;
- which claim boundary is still honest.

After that, the project needs product proof.

## Current Product Objective

Move the delivery-trust chain from "evidence can be inspected" to "a platform
Agent can prepare a customer-delivery envelope without crossing the customer
send boundary."

The completed chain now has these layers:

- Delivery Trust Case Pack: portable metadata-only pack and ZIP consumer proof;
- Dual Loop Trust Scenario Harness: customer-delivery scenario layer;
- Delivery Class Registry: code-review and client-report handoff classes;
- Trust Evidence Handoff Pack: evidence bundle for external operators;
- Trust Evidence Acceptance Drill: allow/block rehearsal from packaged evidence;
- Controlled Handoff Runbook: controlled handoff preparation steps;
- Customer Delivery Trust Envelope: pre-customer-send envelope boundary.
- Customer Delivery Rehearsal: ready/block rehearsal before any customer-visible
  action.
- Code Review Operator Handoff Rehearsal: concrete code-review delivery-class
  operator decision before any PR comment, customer send, or production change.
- Client Report Operator Handoff Rehearsal: concrete client-report
  delivery-class operator decision before any customer send, external
  publication, or production change.
- Support Response Delivery Class and Operator Handoff Rehearsal: concrete
  support-reply delivery-class evidence before any requester-visible send,
  private ticket exposure, external publication, or production change.
- Operator Handoff Rehearsal Contract: shared metadata-only contract that proves
  code-review, client-report, and support-response handoffs obey the same
  operator boundary.
- External Feedback Receipt: bounded adopter/customer/operator feedback can
  re-enter the Product Loop as metadata-only backlog evidence, while raw
  feedback, requester identity, automatic customer replies, external
  publication, and production mutation stay blocked.
- External Feedback Backlog Bridge: accepted feedback receipts can create
  metadata-only Product Loop backlog items, while blocked feedback cannot enter
  backlog or skip product-owner prioritization.
- Product Owner Prioritization Gate: metadata-only backlog items can enter the
  spec/eval candidate queue only after active Product Owner boundary
  reconstruction, while automatic priority assignment, automatic execution,
  customer-visible action, external publication, and production mutation stay
  blocked.
- Product Spec/Eval Authoring Gate: metadata-only spec/eval candidates can
  become metadata-only Product Loop Harness briefs only after active
  authoring-boundary reconstruction, while raw specs, eval prompts, automatic
  execution, customer-visible action, Delivery Trust Harness skips, and
  production mutation stay blocked.
- Product Loop Brief Intake Gate: metadata-only Product Spec/Eval briefs can
  create Product Loop Harness scenario/run candidates only after active
  developer/product-loop boundary reconstruction, while missing briefs, invalid
  briefs, AI-review-only evidence, external scope expansion, Delivery Trust
  Harness skips, customer-visible action, and production mutation stay blocked.
- End-to-End Trust Chain Harness: metadata-only chain proof connects External
  Feedback Receipt, Backlog Bridge, Product Owner Prioritization, Product
  Spec/Eval Authoring, Product Loop Brief Intake, Delivery Trust Case, Customer
  Delivery Envelope, and Customer Delivery Rehearsal while automatic customer
  send, raw payload exposure, AI-review-only evidence, external publication,
  and production mutation stay blocked.
- Real-Adopter Scenario Import: a bounded WorkBuddy/Kimi/Codex/Hermes adoption
  issue summary can re-enter the Product Loop as metadata-only evidence,
  produce a concrete spec/eval brief candidate, and prove raw issue text,
  requester identity, AI-review-only evidence, customer-visible action, and
  production mutation are blocked.
- Spec/Eval Scenario Execution Rehearsal: a Real-Adopter Scenario Import
  spec/eval brief can authorize only a controlled-failure sandbox
  implementation rehearsal after Product Loop and Dual Loop gates pass, while
  missing sandbox evidence, missing human reconstruction, AI-review-only
  evidence, customer-visible action, and production mutation are blocked.
- Sandboxed Patch Proposal Rehearsal: an allowed Spec/Eval execution rehearsal
  can prepare only a metadata-only sandbox-local patch proposal envelope with
  rollback and test boundaries, while raw patch bodies, raw diffs, repository
  mutation, customer-visible action, external publication, and production
  mutation are blocked.
- Patch Proposal Operator Handoff Bridge: a sandbox-local patch proposal
  envelope can become only a metadata-only operator handoff bridge with active
  boundary reconstruction and delivery-class handoff refs, while raw patch
  bodies, raw diffs, automatic execution, repository mutation, customer-visible
  action, external publication, and production mutation are blocked.
- Patch Proposal Acceptance Drill: a ready operator handoff bridge can produce
  only a metadata-only allow/block continuation decision for an external
  operator, while raw patch evidence requests, apply-patch requests, PR actions,
  customer-visible action, external publication, and production mutation are
  blocked.
- Patch Proposal External Work Order Pack: an allowed acceptance drill can emit
  only a metadata-only work-order package for a host platform operator, while
  raw patch bodies, raw diffs, automatic application, PR opening/commenting,
  customer-visible action, external publication, and production mutation remain
  blocked inside this system.
- Patch Proposal External Operator Completion: a completed host-operator work
  summary can re-enter only as a metadata-level completion receipt, while raw
  patch bodies, raw diffs, repository file bodies, PR comments, customer-visible
  payloads, external publication payloads, production payloads, secrets, and
  model credentials remain blocked.
- Patch Proposal Customer-Handoff Boundary Gate: an accepted external-operator
  completion receipt can only prepare a metadata-only customer handoff boundary
  under a separate delivery-class control, while customer-visible drafts, raw
  patch returns, production payload returns, automatic sending, external
  publication, secrets, and model credentials remain blocked.
- Patch Proposal Customer Delivery Envelope: a ready customer-handoff boundary
  receipt can produce only a metadata-only customer delivery envelope for
  manual scope confirmation, while customer-visible draft bodies, raw
  patch/diff/repository file bodies, PR comments, external publication
  payloads, production payloads, secrets, model credentials, automatic sending,
  PR commenting, and production mutation remain blocked.
- Patch Proposal Customer Delivery Rehearsal: a ready customer delivery
  envelope can produce only a metadata-only ready/block manual handoff rehearsal
  after active operator boundary reconstruction, while customer-visible drafts,
  raw patch/diff requests, PR comment actions, automatic sending, external
  publication, production mutation, secrets, and model credentials remain
  blocked.
- Patch Proposal Customer Delivery Outcome Receipt: a ready manual handoff
  rehearsal can produce only a metadata-only record that a human operator or
  host platform Agent reports an external customer handoff action happened
  outside Study Anything, while customer-visible bodies, PR comment bodies,
  external publication payloads, production payloads, automatic sending, source
  mutation, secrets, and model credentials remain blocked.
- Patch Proposal Customer Feedback Intake Receipt: a recorded customer delivery
  outcome can produce only a metadata-only feedback signal receipt for customer,
  operator, or host platform Agent response signals, while raw customer replies,
  private customer data, PR comment bodies, external publication payloads,
  production payloads, automatic follow-up sending, source mutation, secrets,
  and model credentials remain blocked.

The next product proof should show how an AI-generated customer deliverable can
move toward handoff-worthiness without relying on either of these weak patterns:

- human over-review of every step;
- AI reviewing AI through an uninspectable black box.

## First Scenario Classes

Start with product-development loop scenarios:

- product spec/evals present;
- product spec/evals are represented as metadata-only refs before any execution;
- developer vision present;
- external feedback scope stays controlled;
- AI-review-only evidence is rejected;
- no single loop may dominate the others;
- promotion goes only to the Delivery Trust Harness, not to production.

Then continue with customer-delivery scenarios:

- define a bounded task and failure budget;
- run the task in a controlled failure environment;
- require human attention reconstruction at the boundary level;
- emit a delivery trust receipt;
- produce a customer handoff package with explicit claim limits.

## What Is Out Of Scope

Do not restart standalone frontend work as the default path.

Do not keep building release-stack recursion unless the release policy,
release-stack verifier, public evidence semantics, or current group changes in a
substantive way.

Do not claim production trust from local deterministic fixtures. The next runway
is to earn stronger scenario evidence, one customer-delivery class at a time.

## Suggested Next Goal

```text
Patch Proposal Customer Feedback Backlog Bridge:
consume an accepted Patch Proposal Customer Feedback Intake Receipt and emit a
metadata-only Product Loop backlog signal, while still blocking raw customer
replies, private customer data, automatic priority assignment, automatic
follow-up sending, source mutation, production mutation, secrets, and model
credentials.
```
