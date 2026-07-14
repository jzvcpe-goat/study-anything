# 真实 Agent 交付评测集 v0.1

## 一句话结论

仓库现在有一套由 **真实 GitHub 任务、真实 Agent 生成补丁和公开官方评测结果**
构成的 12 例评测输入；它解决了原 40 例机制演练中 gold/empty/nop 等控制样本
距离真实交付较远的问题，但尚未完成 CBB 与原生 Agent 的配对效果评测。

## 为什么必须新增这套评测

此前的 `pilot-v0.1` 主要回答“协议和隔离机制能否按设计工作”：

- SWE-bench-Live 使用 gold patch 与 empty patch；
- TUA-Bench 使用 oracle 与 nop 控制；
- tau-bench 使用固定安全/越权轨迹；
- AgentDojo 使用固定 utility/security 轨迹。

这些样本适合检查 scorer、盲化、门控和收据，但不能代表真实 Agent 交付中常见的
“补丁非空、结构完整、看起来合理，却可能没有真正解决任务”的候选物。因此它们
不能单独支持“CBB 对真实 AI 交付有效”的结论。

## 最接近的公开基准

本轮选择以下公开来源作为主干：

1. [SWE-bench](https://github.com/SWE-bench/SWE-bench)：真实 GitHub issue、代码仓库和
   可执行测试，是代码任务真实性和功能 oracle 的基础。
2. [SWE-bench-Live](https://github.com/microsoft/SWE-bench-Live)：持续更新、多语言、
   多操作系统，并提供可执行容器环境，更适合降低静态题集污染。
3. [SWE-bench-Live submission](https://github.com/SWE-bench-Live/submission)：公开
   Agent 预测补丁、实验说明和评测结果，最接近“固定真实 AI 交付候选，再比较不同
   审核/放行机制”的需求。
4. [SWE-Lancer](https://openai.com/index/swe-lancer/)：其真实自由职业任务和经济价值
   设计可用于后续成本效果评价，但本轮不将其作为代码放行主数据源。

这些上游基准评的是任务完成或 Agent 能力，不直接评估“是否应该放行”。本项目只
借用真实候选物和独立功能结果，再增加放行范围、责任、盲化真人判断和认知成本层。

## 冻结来源

| 字段 | 冻结值 |
| --- | --- |
| 上游仓库 | `SWE-bench-Live/submission` |
| revision | `894eaa94d702e39cda24beaf464df687e50736ad` |
| submission | `multilang/js_ts/20260629-sapient-slingshot-gpt-5.5/ts` |
| Agent | Sapient Slingshot 2.6.0 |
| Model | GPT-5.5 |
| rollout | 每题 1 次，greedy decoding（来自上游 README） |
| 语言 | TypeScript |
| 评测范围 | `personal_local` |

完整机器可读协议见
[`real-agent-v0.1-protocol.json`](real-agent-v0.1-protocol.json)。

## 选择方法

评测集采用病例对照式分层，不用于估计上游 Agent 的自然通过率：

1. 从同一 submission 的非空预测中分别读取 `success_ids` 和 `failure_ids`；
2. 以 `sha256(selection_seed + outcome + task_id)` 排序；
3. 每个功能结果分层最多选择同一仓库 1 例；
4. 各取 6 例，共 12 例、12 个不同仓库；
5. 选择过程不读取补丁内容，不按 CBB 或模型审核结果换题；
6. error、incomplete 或 empty patch 不进入本轮集合。

这样能平衡“功能通过/失败”，并减少单一仓库风格对小样本的支配。但由于它是平衡
病例对照集，不能把 6/12 解释为真实世界失败率。

## 真实材料与仓库边界

每个案例包含：

- 公开 GitHub issue/PR 标题与正文；
- 真实 Agent 生成的完整 Git patch；
- 上游任务、submission 和 revision；
- 已发布功能结果；
- 补丁、任务快照和组合材料的 SHA-256；
- 文件数、增加行和删除行；
- 盲化 reviewer packet。

原始 issue/PR 正文和补丁仅生成到：

```text
.delivery-clearance/benchmarks/real-agent-v0.1/reviewer-materials/
```

该目录被 Git 忽略。仓库提交的
[`validation/results/real-agent-v0.1/`](../../validation/results/real-agent-v0.1/)
只包含来源、哈希、统计量、功能 oracle 和盲化 packet，不包含原始补丁或正文。

## 可重复生成

### 1. 抓取冻结公开源

```bash
.venv/bin/python scripts/fetch_real_agent_case_sources.py \
  --output /tmp/delivery-clearance-real-agent-v0.1
```

脚本从固定 commit 的 GitHub Contents API 读取原始字节，并下载入选任务的公开
issue/PR 快照。环境中的 `GITHUB_TOKEN` 或 `GH_TOKEN` 只用于认证，不写入收据。

### 2. 生成评测集

```bash
.venv/bin/python scripts/delivery_clearance_real_agent_cases.py \
  --predictions /tmp/delivery-clearance-real-agent-v0.1/preds.json \
  --results /tmp/delivery-clearance-real-agent-v0.1/results.json \
  --issue-responses /tmp/delivery-clearance-real-agent-v0.1/issues \
  --replace
```

### 3. 离线验证提交资产

```bash
.venv/bin/python scripts/verify_real_agent_case_set.py --check
```

### 4. 使用公开原始材料重放验证

```bash
.venv/bin/python scripts/verify_real_agent_case_set.py --check \
  --predictions /tmp/delivery-clearance-real-agent-v0.1/preds.json \
  --results /tmp/delivery-clearance-real-agent-v0.1/results.json \
  --issue-responses /tmp/delivery-clearance-real-agent-v0.1/issues
```

## 当前结果

本轮已实际完成：

- 12 个真实 GitHub 任务；
- 12 个不同开源仓库；
- 12 个真实 Agent 非空补丁；
- 6 个上游发布结果 `passed`；
- 6 个上游发布结果 `failed`；
- 12 份公开任务快照；
- 12 份盲化 reviewer packet；
- 12 份隔离功能 oracle；
- 1 份有界的真人审核协议，可分别运行边界重构和全文参考复核；
- 公开源抓取、生成和 source replay 全链路通过。

详细案例见
[`report.zh-CN.md`](../../validation/results/real-agent-v0.1/report.zh-CN.md)。

## 真人审核入口

当本地原始材料已按上文流程生成后，可在仓库根目录启动中文真人审核台：

```bash
.venv/bin/delivery-clearance-review \
  --protocol docs/evaluation/real-agent-v0.1-human-protocol.json \
  --max-items 12
```

协议物理区分两个任务：

1. **边界重构**：只读取已提交的盲化 metadata packet，不能读取 issue
   正文或补丁；
2. **全文参考复核**：从 Git 忽略的本地目录读取原始 issue 和真实 Agent
   补丁，再回答同一组五个边界问题。

全文端点只绑定 `127.0.0.1`，必须同时通过 same-origin、每进程 review
token 和每题 item token。服务器读取材料后会重算补丁 digest 与
`review_material_digest_sha256`；材料缺失、越界、使用符号链接或字节被篡改时均失败关闭。

完成项只追加写入：

```text
.delivery-clearance/benchmarks/real-agent-v0.1-human-sessions.jsonl
```

收据仅保存汇总正确性、未解决数、主动复核时间和可选负担评分；不保存
原始回答、issue 正文或 patch。同一操作者先后完成两种模式只能用于本地
pilot 校准，必须披露顺序与记忆偏差；确证性实验需要分配独立审核者，或使用
有 washout 期的随机交叉设计。

## 一次真实发现

最初通过 `gh api` 将预测 JSON 打印到终端再重定向时，GitHub CLI 对其中的 ANSI
控制字符进行了安全转义，导致文件字节哈希不再等于 GitHub 原始对象。当前实现改为
直接读取固定 commit 的 Contents API 原始响应，并将原始字节 SHA-256 写入协议。

这说明“来源相同”不足以证明评测材料相同；评测输入必须绑定字节级 digest，且获取
工具造成的改写也应被视为状态漂移。

## 为什么目前仍不能证明 CBB 有效

当前只完成了真实评测输入，不是效果实验。以下证据仍缺失：

1. **本机官方 scorer 重跑**：目前使用上游已发布结果，尚未在本机重新执行 12 个
   容器 scorer；
2. **配对 Agent 决策**：尚未让 native、strengthened、internal-checklist、
   external-clearance 在同一补丁、上下文和预算上完成决策；
3. **真人参考判断**：交互协议和本地入口已就绪，但尚无已完成的真人 session；
   功能通过不等于可交付，仍需盲化真人判断交付范围与责任边界；
4. **真人认知成本**：尚未获得可比较的全文复核和边界重构主动时间、工作负担结果；
5. **统计效力**：12 例只能用于流程调试，不能支持显著性或跨模型泛化声明。

因此当前机器状态保持：

```text
local_official_scorer_reexecuted: false
paired_agent_review_completed: false
human_adjudication_completed: false
effectiveness_claim_allowed: false
release_authorized: false
```

## 下一阶段评测流程

同一批 12 个候选将依次完成：

```text
公开真实 Agent 补丁
  -> 本机官方 scorer 重放
  -> 四组等预算、隔离的 Agent 审核
  -> 真人盲化交付判断
  -> CBB 外部门控
  -> 错误放行 / 误阻塞 / 时间 / 成本配对分析
```

主要指标：

- 错误放行率；
- 误阻塞率；
- 相对 expert reference 的 scope expansion；
- 人工主动复核时间；
- 边界重构正确率；
- token、工具调用、延迟与费用；
- 阻塞理由是否能直接指向修复动作。

首轮 12 例只用于验证评测流程。若流程稳定，再冻结一个新的滚动时间窗，将样本扩大
到预注册功效分析要求的规模；不能在看到 CBB 结果后挑选或替换题目。

## Claim Boundary

本评测集证明的是：

> 已经建立了一套可重放的真实任务、真实 Agent 补丁评测输入。

它不证明：

- CBB 已显著降低错误放行；
- CBB 已降低人工时间或成本；
- 上游功能测试通过的补丁可以交付；
- 任何候选已获得客户、公开或生产放行；
- 该结果适用于其他模型、语言、领域或组织。
