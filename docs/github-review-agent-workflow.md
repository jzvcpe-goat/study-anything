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
then writes a Checks/step summary from the safe PR comment pack.

Recommended local dry-run:

```bash
python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check
```

The verification report is:

```text
platform/generated/study-anything-cognitive-loop-review-agent-github-workflow.json
```

Privacy boundary:

- Do not commit real raw diffs, source bodies, finding evidence, model keys, endpoint secrets, or
  hidden chain-of-thought.
- Do not upload the external Review Agent raw report as a workflow artifact.
- Upload only `manifest.json`, `SUMMARY.md`, `review-agent-ci-receipt.json`,
  `review-agent-pr-comment-pack.json`, and `review-agent-checks-summary.md`.
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
bundle，或者校验一个已有的 acceptance bundle，然后从安全的 PR comment pack 写出
Checks/step summary。

本地 dry-run：

```bash
python3 scripts/verify_cognitive_loop_review_agent_github_workflow.py --check
```

验证报告：

```text
platform/generated/study-anything-cognitive-loop-review-agent-github-workflow.json
```

隐私边界：

- 不提交真实 raw diff、源码正文、finding evidence、模型密钥、端点 secret 或 hidden
  chain-of-thought。
- 不把外部 Review Agent 的 raw report 上传为 workflow artifact。
- 只上传 `manifest.json`、`SUMMARY.md`、`review-agent-ci-receipt.json`、
  `review-agent-pr-comment-pack.json` 和 `review-agent-checks-summary.md`。
- 真实模型路由和工具调用继续留在用户自己的外部 Agent 内部。
