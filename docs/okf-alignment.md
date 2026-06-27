# OKF Alignment Layer / OKF 对齐层

**认知黑箱 / Cognitive Black Box** uses an OKF-style bundle to turn a Study Anything learning session into a portable cognitive asset: Markdown notes with YAML frontmatter, a machine-readable manifest, and privacy checks that prove the bundle does not contain raw source text, learner answers, grading feedback, real model keys, or sensitive Agent metadata.

**认知黑箱 / Cognitive Black Box** 通过 OKF-style bundle，把一次 Study Anything 学习会话转成可迁移的认知资产：带 YAML frontmatter 的 Markdown notes、机器可读 manifest，以及能证明“不包含原始正文、学习者答案、评分反馈、真实模型密钥或敏感 Agent metadata”的隐私验证。

This is an alignment layer, not a claim that Study Anything implements a specific external OKF standard byte-for-byte. The project uses the OKF idea as a practical interoperability pattern: human-readable files first, stable metadata next, and platform-Agent validation around the edges.

这是一层对齐能力，不声称 Study Anything 已逐字节实现某个外部 OKF 标准。项目采用的是 OKF 的落地思想：先让人能读，再让 metadata 稳定，最后让平台 Agent 可以验证和消费。

## Why It Exists

- Kimi, Codex, WorkBuddy, Obsidian, and NotebookLM should not need a new standalone frontend to use the learning result.
- A learning session should become a durable knowledge folder, not only an API response.
- Platform Agents should be able to inspect the bundle, cite sources by reference/hash, and continue the workflow with their own tools and models.
- The bundle must keep user-owned secrets and private raw material outside the public handoff.

## 它解决什么

- Kimi、Codex、WorkBuddy、Obsidian、NotebookLM 不应该为了使用学习结果再学习一个新前端。
- 一次学习会话应该沉淀成长期可用的知识文件夹，而不只是 API response。
- 平台 Agent 应该能读取 bundle、按 reference/hash 引用来源，并用自己的工具和模型继续工作。
- bundle 必须把用户私有原文、答案、密钥和 Agent 内部细节留在边界外。

## Bundle Shape

```text
okf-bundle/
  manifest.json
  overview.md
  sources.md
  mastery.md
  decisions.md
  concepts/
    overview.md
    glossary.md
  questions/
    review.md
```

Every Markdown file starts with YAML frontmatter:

```yaml
---
schema_version: "cognitive-black-box-okf-note-v1"
bundle_schema_version: "cognitive-black-box-okf-bundle-v1"
brand: "认知黑箱 / Cognitive Black Box"
kind: "overview"
session_id: "..."
source_reference: "..."
source_excerpt_hash: "..."
consumers:
  - "kimi"
  - "codex"
  - "obsidian"
  - "notebooklm"
privacy:
  raw_source_text_included: false
  learner_answers_included: false
  grading_feedback_included: false
  agent_sensitive_metadata_included: false
  real_model_keys_included: false
---
```

## Export

From the checked-in demo session:

```bash
python3 scripts/export_okf_bundle.py --clean
python3 scripts/verify_okf_bundle.py --check
```

From a running local API:

```bash
python3 scripts/export_okf_bundle.py \
  --api-base http://127.0.0.1:8000 \
  --session-id <session_id> \
  --output-dir .cognitive-loop/okf/<session_id> \
  --clean
python3 scripts/verify_okf_bundle.py \
  --bundle-dir .cognitive-loop/okf/<session_id> \
  --source-session-json session.json
```

If the platform already has the session JSON, use:

```bash
python3 scripts/export_okf_bundle.py \
  --session-json session.json \
  --output-dir okf-bundle \
  --clean
```

## Consumer Modes

- **Kimi**: attach the Markdown folder or paste selected notes as structured context. Kimi should keep browsing, tools, and real model credentials outside Study Anything.
- **Codex**: import the folder as task context or include it in a Skill workflow when continuing implementation/eval work.
- **Obsidian**: copy the folder into a vault; backlinks and tags can be added by the user without changing the source session.
- **NotebookLM**: upload selected Markdown notes plus user-selected original sources. The bundle is ready for manual import, not a hidden NotebookLM API integration.

## Privacy Contract

The exporter intentionally excludes:

- raw source text;
- raw enrichment text, including browser or video transcript slices;
- learner answers;
- grading feedback;
- real model API keys;
- Agent endpoint secrets;
- sensitive Agent prompt/debug metadata.

The verifier checks the generated bundle against the source session and fails if exact private values or secret-like patterns appear.
