# Operating Model / 工程闭环模型

Delivery Clearance is not only a protocol concept. It is also an operating
model for building AI-delivered systems without letting speed outrun trust.

AI 交付放行协议不只是一个协议概念，也是一套工程运行方式：让 AI 可以快速交付，但不能让
速度越过信任边界。

This model turns the operator-supplied "3 key product development loops" diagram
into repository rules. Every pull request must declare which loop it belongs to,
what evidence it produced, what claim boundary it keeps, and whether it can
enter the release stack.

这份模型把“三个产品开发闭环”的图落成仓库规则。每个 PR 都必须说明自己属于哪个
loop、产出了什么证据、保留了什么 claim boundary，以及是否可以进入 release-stack。

## The Three Loops

```text
Agentic Coding Loop       Developer Feedback Loop       External Feedback Loop
~minutes                  ~hours                        ~days

coding agent <->          product spec/evals <->        developer vision <->
product spec/evals        developer vision              external feedback
```

### 1. Agentic Coding Loop

This is the minutes-scale loop between the coding agent and product spec/evals.
It is where code, fixtures, schemas, harness rules, and generated receipts are
changed.

这是分钟级闭环，发生在 coding agent 和 product spec/evals 之间。这里可以改代码、
fixture、schema、harness 规则和生成收据。

Required evidence:

- a declared `agentic_coding_loop` loop id;
- a product spec, eval, harness, or verifier reference;
- focused command output proving the changed behavior;
- metadata-only privacy statement;
- claim boundary statement.

It may enter the release stack only after focused verifiers pass and generated
evidence is current.

### 2. Developer Feedback Loop

This is the hours-scale loop between product spec/evals and developer vision.
It decides whether the repo is building the right thing, not only whether the
latest patch works.

这是小时级闭环，发生在 product spec/evals 和 developer vision 之间。它回答的是：
我们是不是在做正确的东西，而不只是“这次 patch 能不能跑”。

Required evidence:

- a declared `developer_feedback_loop` loop id;
- a DecisionCard, risk note, PRD delta, or acceptance-criteria change;
- evidence showing how the spec/evals changed because of developer judgment;
- explicit in-scope and out-of-scope boundaries;
- follow-up loop assignment if the decision creates implementation work.

It may enter the release stack when the decision changes public product
behavior, acceptance criteria, or release policy, and when the corresponding
verifier/docs are updated.

### 3. External Feedback Loop

This is the days-scale loop between developer vision and real external
feedback. It imports evidence from WorkBuddy, Kimi, Codex, Hermes, GitHub
issues, first adopters, support tickets, and release-asset adoption.

这是天级闭环，发生在 developer vision 和 external feedback 之间。它把 WorkBuddy、
Kimi、Codex、Hermes、GitHub issue、首批用户、支持工单、release asset adoption
等外部证据带回产品判断。

Required evidence:

- a declared `external_feedback_loop` loop id;
- external evidence references that are redacted and reproducible;
- support/adopter status or public issue linkage when available;
- product decision that explains what changes and what does not change;
- release-stack or roadmap effect.

It may enter the release stack only when the feedback has been converted into
metadata-only evidence and does not leak raw user content, secrets, model keys,
agent credentials, screenshots, keystrokes, or private logs.

## Equal Weight With Dual Loop

The three product-development loops are not a replacement for Dual Loop. They
are the operating cadence around it:

- Agentic Coding Loop produces controlled changes and verifier evidence.
- Developer Feedback Loop reconstructs why the evidence matters.
- External Feedback Loop checks whether the claim survives contact with users
  and platform agents.

三大产品开发闭环不是 Dual Loop 的替代品，而是 Dual Loop 外层的工程节奏：

- Agentic Coding Loop 负责产出受控变更和 verifier evidence。
- Developer Feedback Loop 负责重构为什么这些证据重要。
- External Feedback Loop 负责确认这个 claim 能否经受真实用户和平台 Agent 的反馈。

No loop may dominate the others. A green sandbox without human reconstruction
still blocks. A strong product intuition without bounded failure evidence still
blocks. External praise without reproducible evidence still blocks.

## Pull Request Rule

Every non-trivial PR should include:

```text
Loop: agentic_coding_loop | developer_feedback_loop | external_feedback_loop
Evidence: docs, fixtures, generated reports, verifier commands
Claim boundary: what this proves and what it does not prove
Privacy boundary: metadata-only, no secrets, no raw private payloads
Release-stack effect: none | candidate | intake | promotion | self-intake
```

If a PR touches release-stack assets, it must also state which group it belongs
to and which prior group or PR it self-intakes.

## Release-Stack Rule

A PR can become a release-stack candidate only when:

- it declares exactly one primary loop;
- generated evidence is current;
- relevant verifier commands pass;
- privacy boundaries are explicit;
- claim boundaries are explicit;
- any external feedback is represented as redacted metadata;
- the handoff package or receipt cannot expand trust beyond the underlying gate.

This is intentionally strict. The release stack is not a changelog. It is the
public chain of evidence for what the project can honestly claim.

## Machine Contract

The machine-readable contract is:

```text
.cognitive-loop/loops.yaml
```

The verifier is:

```bash
python3 scripts/verify_operating_model_loops.py --check
```

Generated evidence:

```text
platform/generated/study-anything-operating-model-loops.json
```

The verifier checks that all three loops exist, their cadences and actors match
the diagram, PR evidence rules are present, release-stack entry rules are
bounded, and the privacy model remains metadata-only.
