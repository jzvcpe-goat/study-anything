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

Build the Product Loop Harness and connect it to the Dual Loop Trust Scenario
Harness.

The Product Loop Harness is the pre-handoff layer; the Dual Loop Trust Scenario Harness remains the customer-delivery layer.

The Product Loop Harness should show, with deterministic and metadata-only
evidence first, how a product candidate moves across the three real development
loops before customer handoff:

- Agentic Coding Loop: coding agent to product spec/evals, roughly minutes.
- Developer Feedback Loop: developer vision to product spec/evals, roughly
  hours.
- External Feedback Loop: external feedback to developer vision, roughly days.

The Delivery Trust Harness should then show how an AI-generated customer
deliverable can become trustworthy without relying on either of these weak
patterns:

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
Product Loop Harness:
create deterministic product-loop fixtures, product-loop scenario/run
contracts, a CLI, a verifier, and generated evidence proving the Agentic
Coding, Developer Feedback, and External Feedback loops all have equal weight
before promotion to the Delivery Trust Harness.
```
