# Agent 能力准入检查 v0.1

## 结论

在人类审核实验开始前，本项目使用 **SWE-bench-Live/MultiLang TypeScript**
检查当前已绑定候选生成 Agent 的基础软件工程能力。

按仓库中的冻结协议，“当前 Agent”具体指：

- Agent：`Sapient Slingshot 2.6.0`
- Model：`GPT-5.5`
- Submission：`20260629-sapient-slingshot-gpt-5.5/ts`
- Source revision：`894eaa94d702e39cda24beaf464df687e50736ad`

检查结果分为四种用途，不能合并成一个“Agent 已达标”结论：

| 用途 | 结论 | 依据 |
| --- | --- | --- |
| 作为真人审核实验的真实候选来源 | **通过** | 111 个提交中有 46 个功能成功、64 个功能失败、1 个评测错误，且没有空补丁；能够提供非平凡的成功与失败候选。 |
| 作为可自主交付代码的 Agent | **不具备资格** | 全部提交口径下成功率为 `46 / 111 = 41.44%`；公开结果中仍有 64 个失败和 1 个错误。 |
| 作为“强原生审核 Agent”对照 | **尚未评估** | 当前结果评价的是补丁生成与修复能力，不是放行判断能力；四臂配对 Agent 审核尚未执行。 |
| 证明 Delivery Clearance 有效 | **尚未就绪** | 真人审核、盲法裁决、配对 Agent 决策和本地官方 scorer 重放均未完成。 |

因此，当前 Agent **足以作为 personal-local 真人审核实验的候选生成来源**，但不
足以支持自主交付、客户交付、生产放行或 Delivery Clearance 效果声明。

## 为什么选择这个基准

[SWE-bench](https://www.swebench.com/SWE-bench/faq/) 已成为软件工程 Agent 的
主流执行式评测框架。它使用真实 GitHub issue、固定仓库状态、Docker 环境和测试
结果判断补丁是否解决任务。SWE-bench Verified 进一步提供了 500 个经工程师确认
可解的问题，说明这一评测范式具有成熟、公开和可复验的基础。

本项目实际选择
[SWE-bench-Live](https://github.com/microsoft/SWE-bench-Live) 的 MultiLang
TypeScript 子集，而不是直接使用 Python 为主的静态 Verified 子集，原因是：

1. 当前冻结 Agent 提交本身就是 TypeScript；
2. Live 任务来自持续更新的真实仓库，降低静态题集污染风险；
3. 每个任务仍由可执行环境与测试 oracle 判分；
4. 论文已进入 NeurIPS 2025 Datasets and Benchmarks 轨道，公开论文、代码、数据、
   submission 与结果文件；
5. 当前产品首先审核代码交付，因此它比通用对话或浏览器 Agent 基准更贴近被测
   能力。

该选择只评价“Agent 能否生成解决真实 issue 的补丁”，不评价交付对象、用途、
责任、残余风险或是否应当放行。后者仍由 Delivery Clearance 自己的配对实验评价。

## 公开结果

冻结的上游
[README](https://github.com/SWE-bench-Live/submission/blob/894eaa94d702e39cda24beaf464df687e50736ad/submissions/multilang/js_ts/20260629-sapient-slingshot-gpt-5.5/ts/README.md)
声明 Agent 版本、模型、单次 rollout 和 greedy decoding；
[results.json](https://github.com/SWE-bench-Live/submission/blob/894eaa94d702e39cda24beaf464df687e50736ad/submissions/multilang/js_ts/20260629-sapient-slingshot-gpt-5.5/ts/results.json)
记录：

```text
submitted: 111
success: 46
failure: 64
error: 1
incomplete: 0
empty_patch: 0
success / submitted: 41.44%
non-success / submitted: 58.56%
```

`41.44%` 是由公开计数计算的描述性结果，不是 Delivery Clearance 的效果指标，
也不是基于本仓库重新执行全部官方 scorer 得出的新结果。

## 本地复核

本轮执行了：

```bash
.venv/bin/python scripts/fetch_real_agent_case_sources.py \
  --output /tmp/delivery-clearance-agent-qualification

.venv/bin/python scripts/verify_real_agent_case_set.py --check \
  --predictions /tmp/delivery-clearance-agent-qualification/preds.json \
  --results /tmp/delivery-clearance-agent-qualification/results.json \
  --issue-responses /tmp/delivery-clearance-agent-qualification/issues
```

验证结果：

- 上游 revision、submission path、predictions digest 和 results digest 匹配；
- 12 个冻结案例全部可以从公开来源重放；
- 12 个案例覆盖 12 个仓库，公开功能结果为 6 个通过、6 个失败；
- 原始 issue 与补丁未写入 Git；
- `human_adjudication_completed: false`；
- `paired_agent_review_completed: false`；
- `local_official_scorer_reexecuted: false`；
- `effectiveness_claim_allowed: false`。

本机 SWE-bench-Live preflight 还返回：

```text
execution_readiness: source_ready_execution_blocked
blocker: selected-runtime-images-unavailable
```

这意味着公开来源身份已复核，但本机没有完成官方容器 scorer 的独立重放。不得把
上游公开结果描述成本机复现实验。

## 对真人实验的准入决定

允许进入的下一步：

- 使用这 12 个真实、非空、结果混合的补丁进行 personal-local 审核界面试验；
- 比较边界重构与全文参考复核的正确数、未解决项、时间和负担；
- 保持上游功能结果对审核者盲化。

仍然阻断：

- 将该 Agent 称为“强原生审核 Agent”；
- 将 6/12 病例对照样本解释为 Agent 自然成功率；
- 报告错误放行率、误阻断率或 Delivery Clearance 效果；
- 客户、生产、公开发布或专业资格声明。

在四臂配对 Agent 审核和独立盲法裁决完成前，Agent 能力检查只能作为真人实验的
**候选来源准入证据**，不能作为 Delivery Clearance 的有效性证据。
