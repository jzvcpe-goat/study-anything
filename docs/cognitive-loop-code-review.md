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

Study Anything 可以保存外部 Agent 输出的脱敏结构化报告，但不得保存 raw diff、文件正文、真实模型密钥、私有 Agent endpoint、隐藏推理链或业务秘密。

后续阶段：

- Soft gate：CI 可以对高风险发现发出警告，并要求显式 human note。
- Hard gate：特定仓库可选择对 high/blocked 风险发现启用合并阻断。
- Agent eval：外部 review Agent 可用 curated review fixtures、误报/漏报标准进行评估。
