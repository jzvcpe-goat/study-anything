# 真实项目交付评测 v0.1

English version: [Real Project Delivery Evaluation v0.1](real-project-validation.md)

## 为什么需要这套评测

如果协议只能识别人造样例，它就还不能证明自己能够约束真实开发流程。本评测回放
Delivery Clearance 自身开发历史中的四个真实交付状态。每个状态都在独立的临时 Git
克隆中接受检查，原始工作区保持只读。评测结果只保存哈希、退出码、有限的失败节点和
耗时，不保存源代码或原始命令输出。

本轮只回答一个可证伪问题：

> 预先声明的机器门禁，能否区分尚未完成的交付状态，以及可以进入真人边界重构的状态？

本轮不回答 Delivery Clearance 是否已经减少审核时间、认知负担或错误率。这些效果必须
通过真人会话和更强的配对实验获得。

## 评测集

四个案例来自同一条真实 PR 修复链：

| 案例 | 仓库状态 | 回放检查 | 预期机器状态 |
| --- | --- | --- | --- |
| `rp-01` | Human Review Cockpit 代码已经加入，但 Python 供应链收据过期 | Python 供应链检查 | `blocked` |
| `rp-02` | 供应链收据已刷新，但 6 个下游证据节点过期 | 生成证据拓扑检查 | `blocked` |
| `rp-03` | 下游证据只完成部分刷新，仍有 5 个拓扑节点失效 | 生成证据拓扑检查 | `blocked` |
| `rp-04` | 声明的 59 个证据节点全部收敛 | 生成证据拓扑检查 | `ready_for_human_review` |

冻结输入和预期结果位于
[`real-project-v0.1-scenarios.json`](real-project-v0.1-scenarios.json)。案例绑定完整
commit SHA、预期退出码和有限的失败节点集合。Oracle 来自仓库自身确定性检查产生的退出
状态与机器可读失败节点，不来自另一个模型的意见。

## 复现方法

在仓库根目录运行：

```bash
.venv/bin/python scripts/delivery_clearance_project_scenarios.py --replace
```

命令会重新生成：

```text
validation/results/real-project-v0.1/
  scenario-set.json
  result.json
  report.md
  check-receipts/
  reviewer-packets/
```

每个检查都在独立临时克隆中运行。Runner 会检查命令是否改变了 Git 可见项目状态。
超时、基础设施错误、输出不匹配、失败节点集合不匹配或项目状态变化都会使案例闭合失败。

## 已观察结果

2026 年 7 月 14 日提交的运行结果为：

- 4 个案例全部匹配冻结 Oracle；
- 3 个未完成的历史状态被阻断；
- 1 个收敛状态进入 `ready_for_human_review`；
- 没有任何案例在缺少真人复核时获得 release authorization；
- 4 次检查均未改变 Git 可见状态；
- 结果不包含原始源码、原始检查输出、本地绝对路径、模型调用或生产变更。

证据位于
[`validation/results/real-project-v0.1`](../../validation/results/real-project-v0.1/)。
它只覆盖一个项目和一条事故链，因此属于机制证据，不是通用效果估计。

## 完成真人对照

使用同一批真实 reviewer packet 启动本地审核界面：

```bash
.venv/bin/delivery-clearance-review \
  --protocol docs/evaluation/real-project-v0.1-human-protocol.json \
  --max-items 4
```

协议提供两个物理分离的任务：

1. 重构交付范围、接收者、风险负责人、可见失败、恢复方式和禁止用途；
2. 完成完整元数据复核，再回答同一组五个边界问题。

Cockpit 只记录聚合正确率、未解决问题数量、有效可见时间和可选工作负荷，不保存原始
答案或审核人身份。真人必须亲自完成这些会话；仓库当前没有为这套真实项目评测填写或
伪造任何真人结果。

## 分层评测策略

真实项目评测不会替代其他验证层，而是补齐场景层证据：

| 层级 | 当前资产 | 能够证明什么 |
| --- | --- | --- |
| 状态完整性 | Personal Clearance 的 14 个 verifier 场景和 12 个聚焦测试 | 过期、篡改、缺失、失败或污染项目的证据会闭合失败 |
| 真实项目回放 | 本文的 4 个历史交付状态 | 声明门禁可以重放一条真实的“未完成到收敛”序列 |
| Agent 对照 | 冻结的 40 案例 Native Agent vs Delivery Clearance harness | 提供公平比较审核机制的方法，真人证据仍未完成 |
| 用户价值 | 计划中的全文复核与边界重构真人对照 | 审核时间、工作负荷、错误放行、错误阻断和决策质量，目前尚未证明 |

下一步不应继续从同一事故复制更多变体，而应增加第二个项目和不同失败类型，然后执行
预注册的真人配对比较。

## 结论边界

本次运行只证明：在记录的仓库版本和本地环境中，声明检查复现了 3 个历史阻塞状态和
1 个机器就绪状态。机器就绪仍不能直接放行，必须由真人重构边界并接受责任。

这不是生产批准、客户验证、独立审计，也不是 Delivery Clearance 具有统计显著收益的证据。
