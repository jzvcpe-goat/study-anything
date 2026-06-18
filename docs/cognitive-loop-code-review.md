# Cognitive Loop Code Review Loop v0.1

## English

The Code Review Loop is the first advisory review flow for Cognitive Loop System. It turns a git diff or redacted PR summary into structured, local evidence that Codex, Kimi, WorkBuddy, or a private platform Agent can read:

- `ReviewRun`: the review session, source, changed paths, findings, test gaps, security gate, decision, and metrics.
- `ReviewFinding`: up to five deterministic high-confidence findings, each with file path, diff ref, risk level, confidence, and a verification command.
- `ReviewTestGap`: metadata-only test coverage gaps when implementation or script paths change without a paired test path.
- `ReviewSecurityGate`: v0.1 advisory security gate. `blocking`, `merge_blocked`, and `hard_gate_enabled` stay `false`.
- `ReviewDecision`: operator-facing recommendation and verification commands.
- `ReviewMetrics`: counts, highest risk, reviewer id, and privacy booleans proving no raw diff, file contents, model keys, or Agent endpoints are stored.

Run it locally:

```bash
python3 scripts/cognitive_loop_review.py --base main --head HEAD --html
```

This writes:

- `.cognitive-loop/events/cognitive-loop-review.json`
- `.cognitive-loop/artifacts/cognitive-loop-review.html`

Verify the flow:

```bash
python3 scripts/verify_cognitive_loop_review.py --check
```

The built-in reviewer is `fake-deterministic-reviewer`. It does not call a model and does not inspect file bodies. Real review ability must come from a BYO Agent or platform Agent outside Study Anything. That external Agent may read more context if the operator permits it, but Study Anything only stores the redacted review contract output.

Risk is mapped from `.cognitive-loop/risk.yaml`; release verification is mapped through `.cognitive-loop/evals.yaml`. The verifier is a blocking release check because the review feature must stay healthy, but the review result itself does not block merges in v0.1.

### Product Boundary

The Code Review Loop is developer/operator delivery assurance tooling. It is not a Study Anything end-user learning feature, not a code explainer for learners, and not a business feature generator. Its audience is maintainers, CI operators, Codex/Kimi/WorkBuddy-style platform Agents, and private review gateways.

There are two review layers:

- Built-in local CLI: `scripts/cognitive_loop_review.py` creates metadata-only advisory evidence, does not store raw diff bodies or file bodies, and caps deterministic path-level findings at five.
- External Review Agent: `platform/prompts/cognitive-loop-review-agent.json` is the JSON-only prompt contract for a user-owned CI or platform Agent that receives the real git diff from the operator. It must cite concrete diff lines or snippets, suppress low-confidence findings, and output 最多 8 findings sorted by risk.
- External report handoff: `platform/schemas/cognitive-loop-review-agent-report.schema.json` defines the final JSON report; `fixtures/review-agent` contains accepted and rejected examples; `python3 scripts/verify_cognitive_loop_review_agent_report.py --check` proves the schema, fixtures, evidence format, suppression rules, and privacy boundary.
- External handoff CLI: `scripts/cognitive_loop_review_agent_handoff.py prepare --base main --head HEAD` builds an ephemeral request for Kimi, Codex, WorkBuddy, or a private Review Agent. It includes the prompt, schema, operator instructions, and raw git diff. By default it prints to stdout and refuses to write raw-diff material inside the reviewed repo. After the external Agent returns JSON, run `scripts/cognitive_loop_review_agent_handoff.py validate --report REVIEW_AGENT_REPORT.json` to produce a redacted validation summary. `python3 scripts/verify_cognitive_loop_review_agent_handoff_cli.py --check` keeps this operator path healthy.
- External eval harness: `evals/review-agent` contains synthetic diff cases and golden reports for approved, needs-review, and needs-fix outcomes. `python3 scripts/verify_cognitive_loop_review_agent_eval_harness.py --check` proves decision-path coverage, critical security CWE evidence, low-confidence suppression, and privacy-leak rejection before trusting an external Review Agent.
- CI/PR receipt: after validating an external Agent report, run `python3 scripts/cognitive_loop_review_agent_receipt.py build --report REVIEW_AGENT_REPORT.json --provider-id PROVIDER --pr-ref PR --commit-sha SHA` to create a metadata-only receipt for PR evidence or CI logs. `python3 scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check` proves the receipt records provider/ref/report hash/decision/counts without storing raw diff, file bodies, finding evidence, report summary, Agent endpoint secrets, real model keys, or hidden chain-of-thought.
- PR comment pack: after generating a CI receipt, run `python3 scripts/cognitive_loop_review_agent_pr_comment.py build --receipt REVIEW_AGENT_CI_RECEIPT.json` to produce bilingual copy-ready PR comments and a Checks summary. `python3 scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check` proves the pack keeps only metadata, labels, commands, and human action, and rejects raw diff or report-body leakage.
- Acceptance bundle: for one-command operator handoff, run `python3 scripts/cognitive_loop_review_agent_acceptance_bundle.py build --report REVIEW_AGENT_REPORT.json --output-dir /tmp/review-agent-acceptance` to generate the receipt, PR comment pack, manifest, and `SUMMARY.md` together. `python3 scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check` proves the bundle is metadata-only and safe for PR or CI archival.
- GitHub workflow template: `platform/workflows/cognitive-loop-review-agent-manual.yml` is a copy-ready manual GitHub Actions template for validating a report or existing acceptance bundle and writing a metadata-only Checks/step summary. It is `workflow_dispatch` only, does not call real models, does not require external Agent secrets, and does not upload the raw report. `python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check` proves this workflow and its unsafe fixture.

Study Anything may store the external Agent's redacted structured report, but it must not store raw diff bodies, file contents, real model keys, private Agent endpoints, hidden chain-of-thought, or business secrets.

Later phases:

- Soft gate: CI can warn on high-risk findings and require an explicit human note.
- Hard gate: selected repositories may opt into merge blocking for high/blocked risk findings.
- Agent eval: external review Agents can be judged against curated review fixtures and false-positive/false-negative criteria.

## 中文

Code Review Loop 是 Cognitive Loop System 的第一个代码审查咨询流。它把 git diff 或脱敏 PR 摘要转换成本地结构化证据，供 Codex、Kimi、WorkBuddy 或私有平台 Agent 读取：

- `ReviewRun`：一次审查会话，包含来源、变更路径、发现、测试缺口、安全门、决策和指标。
- `ReviewFinding`：最多五条确定性高置信发现，每条包含文件路径、diff ref、风险等级、置信度和建议验证命令。
- `ReviewTestGap`：当实现或脚本路径变化但没有配套测试路径时，生成只含元数据的测试缺口。
- `ReviewSecurityGate`：v0.1 咨询式安全门，`blocking`、`merge_blocked`、`hard_gate_enabled` 都保持 `false`。
- `ReviewDecision`：面向操作者的建议和验证命令。
- `ReviewMetrics`：变更数量、最高风险、reviewer id，以及证明不保存 raw diff、文件内容、模型 key 或 Agent endpoint 的隐私布尔值。

本地运行：

```bash
python3 scripts/cognitive_loop_review.py --base main --head HEAD --html
```

它会写入：

- `.cognitive-loop/events/cognitive-loop-review.json`
- `.cognitive-loop/artifacts/cognitive-loop-review.html`

验证该流程：

```bash
python3 scripts/verify_cognitive_loop_review.py --check
```

内置 reviewer 是 `fake-deterministic-reviewer`。它不调用模型，也不读取文件正文。真实代码审查能力必须来自 Study Anything 之外的 BYO Agent 或平台 Agent。外部 Agent 可以在操作者授权下读取更多上下文，但 Study Anything 只保存脱敏后的 review contract 输出。

风险来自 `.cognitive-loop/risk.yaml`；发布验证接入 `.cognitive-loop/evals.yaml`。review verifier 是发布检查的一部分，因为这个功能本身必须保持健康；但 v0.1 的审查结果不会阻塞合并。

### 产品边界

Code Review Loop 是 developer/operator 交付验收工具。它不是 Study Anything 面向终端用户的学习功能，不负责给学习者解释代码如何工作，也不生成业务功能代码。它的受众是维护者、CI operator、Codex/Kimi/WorkBuddy-style 平台 Agent 和私有审查网关。

这里分成两层：

- 内置本地 CLI：`scripts/cognitive_loop_review.py` 生成 metadata-only 咨询证据，不保存 raw diff 或文件正文，确定性 path-level findings 最多五条。
- 外部 Review Agent：`platform/prompts/cognitive-loop-review-agent.json` 是用户自有 CI 或平台 Agent 的 JSON-only 提示词契约，由 operator 把真实 git diff 提供给它。它必须引用具体 diff 行号或代码片段，抑制 low-confidence findings，并且最多 8 条发现，按风险排序。
- 外部报告交接：`platform/schemas/cognitive-loop-review-agent-report.schema.json` 定义最终 JSON 报告；`fixtures/review-agent` 包含通过和拒绝样例；`python3 scripts/verify_cognitive_loop_review_agent_report.py --check` 验证 schema、fixtures、证据格式、低置信抑制规则和隐私边界。
- 外部交接 CLI：`scripts/cognitive_loop_review_agent_handoff.py prepare --base main --head HEAD` 生成给 Kimi、Codex、WorkBuddy 或私有 Review Agent 的临时请求，里面包含 prompt、schema、操作说明和 raw git diff。默认输出到 stdout，并拒绝把 raw-diff 材料写入被审查 repo。外部 Agent 返回 JSON 后，用 `scripts/cognitive_loop_review_agent_handoff.py validate --report REVIEW_AGENT_REPORT.json` 生成脱敏验证摘要。`python3 scripts/verify_cognitive_loop_review_agent_handoff_cli.py --check` 负责验证这条操作者路径。
- 外部 eval harness：`evals/review-agent` 提供合成 diff cases 和 golden reports，覆盖 approved、needs-review、needs-fix 三条路径。`python3 scripts/verify_cognitive_loop_review_agent_eval_harness.py --check` 验证决策覆盖、安全 critical/CWE、低置信抑制和隐私泄漏拒绝，用来在信任外部 Review Agent 前做离线验收。
- CI/PR receipt：外部 Agent 报告验证通过后，运行 `python3 scripts/cognitive_loop_review_agent_receipt.py build --report REVIEW_AGENT_REPORT.json --provider-id PROVIDER --pr-ref PR --commit-sha SHA`，生成可贴到 PR 证据或 CI 日志里的 metadata-only 收据。`python3 scripts/verify_cognitive_loop_review_agent_ci_receipt.py --check` 验证该收据只记录 provider、ref、报告 hash、决策和计数，不保存 raw diff、文件正文、finding evidence、报告 summary、Agent endpoint secret、真实模型 key 或隐藏推理链。
- PR comment pack：生成 CI receipt 后，运行 `python3 scripts/cognitive_loop_review_agent_pr_comment.py build --receipt REVIEW_AGENT_CI_RECEIPT.json`，生成中英文可复制 PR 评论和 Checks 摘要。`python3 scripts/verify_cognitive_loop_review_agent_pr_comment_pack.py --check` 验证它只保留元数据、标签、命令和人工动作，并拒绝 raw diff 或报告正文泄漏。
- Acceptance bundle：如果需要一条命令完成 operator handoff，运行 `python3 scripts/cognitive_loop_review_agent_acceptance_bundle.py build --report REVIEW_AGENT_REPORT.json --output-dir /tmp/review-agent-acceptance`，一次生成 receipt、PR comment pack、manifest 和 `SUMMARY.md`。`python3 scripts/verify_cognitive_loop_review_agent_acceptance_bundle.py --check` 验证该 bundle 是 metadata-only，适合 PR 或 CI 归档。
- GitHub workflow 模板：`platform/workflows/cognitive-loop-review-agent-manual.yml` 是可复制的手动 GitHub Actions 模板，用来校验 report 或已有 acceptance bundle，并写出 metadata-only Checks/step summary。它只允许 `workflow_dispatch`，不调用真实模型，不需要外部 Agent secret，也不会上传 raw report。`python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check` 负责验证该 workflow 和 unsafe 负例 fixture。

Study Anything 可以保存外部 Agent 输出的脱敏结构化报告，但不得保存 raw diff、文件正文、真实模型密钥、私有 Agent endpoint、隐藏推理链或业务秘密。

后续阶段：

- Soft gate：CI 可以对高风险发现发出警告，并要求显式 human note。
- Hard gate：特定仓库可选择对 high/blocked 风险发现启用合并阻断。
- Agent eval：外部 review Agent 可用 curated review fixtures、误报/漏报标准进行评估。
