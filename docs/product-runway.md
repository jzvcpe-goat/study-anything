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

The next product proof should show how an AI-generated customer deliverable can
move toward handoff-worthiness without relying on either of these weak patterns:

- human over-review of every step;
- AI reviewing AI through an uninspectable black box.

## First Scenario Classes

Start with product-development loop scenarios:

- product spec/evals present;
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
Customer Delivery Rehearsal:
create a metadata-only rehearsal that lets an external operator or platform
Agent inspect the customer-delivery trust envelope, confirm the human scope
boundary, and produce a blocked/ready decision without sending anything to a
customer, mutating production, or reading raw payloads.
```

After that, add stronger real-adopter feedback import/export only if it keeps
the External Feedback Receipt boundary: metadata-only evidence enters the
Product Loop, while raw customer content and customer-visible action stay out of
the protocol.
