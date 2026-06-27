# Cognitive Loop Review Agent GitHub Workflow

This is the safe GitHub Actions handoff for teams that already run a user-owned external Review
Agent in Kimi, Codex, WorkBuddy, or a private CI environment.

The template lives at:

```text
platform/workflows/cognitive-loop-review-agent-manual.yml
```

Copy it into `.github/workflows/` only after the external Review Agent report path is understood.
The workflow is manual-only through `workflow_dispatch`. It does not call a real model, does not
need external Agent secrets, and does not upload the raw Review Agent report. It either builds a
metadata-only acceptance bundle from a local report path or validates an existing acceptance bundle,
then runs the metadata-only policy gate and writes a Checks/step summary from the safe PR comment
pack plus the gate result.

Policy choices:

- `advisory`: always exits 0 and records the Review Agent decision.
- `soft`: exits nonzero for `needs-fix`, but lets `needs-review` reach maintainer review.
- `strict`: exits nonzero for both `needs-review` and `needs-fix`.

The workflow captures the policy gate exit code, uploads only safe metadata artifacts when enabled,
then applies the captured exit code in the final step. This preserves PR evidence even when the
policy blocks the job.

Recommended local dry-run:

```bash
python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check
```

Recommended adoption-pack install smoke:

```bash
python3 scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check
```

This smoke extracts `platform/generated/study-anything-platform-adoption-pack.zip`, copies the
workflow into a temporary `.github/workflows/` directory, builds metadata-only acceptance bundles
from synthetic fixtures, and reproduces `advisory`, `soft`, and `strict` policy gate exits using
only files shipped in the pack.

The verification report is:

```text
platform/generated/study-anything-cognitive-loop-review-agent-github-workflow.json
```

The install-smoke report is:

```text
platform/generated/study-anything-cognitive-loop-review-agent-workflow-install-smoke.json
```

Privacy boundary:

- Do not commit real raw diffs, source bodies, finding evidence, model keys, endpoint secrets, or
  hidden chain-of-thought.
- Do not upload the external Review Agent raw report as a workflow artifact.
- Upload only `manifest.json`, `SUMMARY.md`, `review-agent-ci-receipt.json`,
  `review-agent-pr-comment-pack.json`, `review-agent-policy-gate.json`, and
  `review-agent-checks-summary.md`.
- Keep real model routing and tool use inside the user-owned external Agent.

## 中文说明

这是给 GitHub Actions 使用的安全交接模板，适用于已经在 Kimi、Codex、WorkBuddy 或私有 CI
中运行用户自有 Review Agent 的团队。

模板位置：

```text
platform/workflows/cognitive-loop-review-agent-manual.yml
```

只有在明确外部 Review Agent report 路径之后，才把它复制到 `.github/workflows/`。这个
workflow 只支持 `workflow_dispatch` 手动触发，不调用真实模型，不需要外部 Agent secret，
也不会上传原始 Review Agent report。它会从本地 report 路径生成 metadata-only acceptance
bundle，或者校验一个已有的 acceptance bundle，然后运行 metadata-only policy gate，并从安全
的 PR comment pack 和 gate result 写出 Checks/step summary。

策略选择：

- `advisory`：始终返回 0，只记录 Review Agent 决策。
- `soft`：仅在 `needs-fix` 时返回非零，`needs-review` 交给维护者判断。
- `strict`：`needs-review` 和 `needs-fix` 都返回非零。

workflow 会先捕获 policy gate 退出码，在允许上传时只上传安全 metadata artifact，最后一步再应用
捕获的退出码。这样即使策略阻断 job，也不会丢掉 PR 验收证据。

本地 dry-run：

```bash
python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check
```

adoption pack 安装验收：

```bash
python3 scripts/verify_cognitive_loop_review_agent_workflow_install_smoke.py --check
```

这个 smoke 会解压 `platform/generated/study-anything-platform-adoption-pack.zip`，把 workflow 复制到临时
`.github/workflows/` 目录，用合成 fixture 生成 metadata-only acceptance bundle，并且只使用 pack 中的文件
复现 `advisory`、`soft`、`strict` 三种 policy gate 退出码。

验证报告：

```text
platform/generated/study-anything-cognitive-loop-review-agent-github-workflow.json
```

安装验收报告：

```text
platform/generated/study-anything-cognitive-loop-review-agent-workflow-install-smoke.json
```

隐私边界：

- 不提交真实 raw diff、源码正文、finding evidence、模型密钥、端点 secret 或 hidden
  chain-of-thought。
- 不把外部 Review Agent 的 raw report 上传为 workflow artifact。
- 只上传 `manifest.json`、`SUMMARY.md`、`review-agent-ci-receipt.json`、
  `review-agent-pr-comment-pack.json`、`review-agent-policy-gate.json` 和
  `review-agent-checks-summary.md`。
- 真实模型路由和工具调用继续留在用户自己的外部 Agent 内部。
