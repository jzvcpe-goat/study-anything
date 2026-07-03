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

Package the completed Delivery Trust Case Harness into a ZIP-only external
consumer pack.

The Product Loop Harness is the pre-handoff layer; the Dual Loop Trust Scenario Harness remains the customer-delivery layer; the Delivery Trust Case Harness is
the end-to-end assembly layer. The next product proof is that another operator,
customer reviewer, or platform Agent can verify that assembly from a portable
metadata-only pack without trusting our prose or reading private source text.

The pack should show how an AI-generated customer deliverable can become
handoff-worthy without relying on either of these weak patterns:

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
Delivery Trust Case Consumer Pack:
create a portable delivery-trust-case-pack-v1 JSON/MD/ZIP/SHA256 bundle plus a
ZIP-only consumer walkthrough verifier proving an external adopter can inspect
the claim boundary, hash integrity, pass/blocked case matrix, and metadata-only
privacy rules without a repo checkout.
```

After that, move to the first real-domain delivery class: take one AI-generated
deliverable type, such as a code-review handoff or client report handoff, and
map it into the same case-pack contract without weakening the claim boundary.
