# 真实 Agent 交付候选评测集 v0.1

本评测集从冻结的 SWE-bench-Live 官方提交中选择 12 个真实 GitHub 任务和真实
Agent 补丁。选择按通过/失败各 6 例分层，并在每个分层中限制为每个仓库最多
1 例。排序只由固定 seed、功能结果分层和任务 ID 的 SHA-256 决定，不读取补丁
内容进行挑选。

| Case | 上游任务 | 任务标题 | 文件数 | 行变更 | 已发布功能结果 |
| --- | --- | --- | ---: | ---: | --- |
| agent-passed-01 | `mikro-orm__mikro-orm-7464` | fix(core): fix wrong column name for nested inline embeddables when parent is null | 2 | +94/-14 | passed |
| agent-passed-02 | `antvis__G2-7021` | fix: tooltip pick logic | 2 | +65/-3 | passed |
| agent-passed-03 | `mui__mui-x-22062` | [pickers] Use `convertToMeridiem` utility in `transferDateSectionValue` | 2 | +16/-2 | passed |
| agent-passed-04 | `openapi-ts__openapi-typescript-2365` | fix(#2364): Add support for passing parameters to @ApiOperation | 5 | +74/-2 | passed |
| agent-passed-05 | `owid__owid-grapher-5115` | 🐛 fix interpolation of irregular time intervals. | 2 | +30/-4 | passed |
| agent-passed-06 | `Milkdown__milkdown-2041` | fix: 🐛 html in blockquote error | 3 | +61/-1 | passed |
| agent-failed-01 | `taiga-family__taiga-ui-11501` | fix(kit): `ComboBox` should recompute stringified textfield value on new value of `stringify` handler | 2 | +88/-1 | failed |
| agent-failed-02 | `honojs__hono-4249` | fix(ssg): invoke callback when it's only a dynamic route | 4 | +102/-16 | failed |
| agent-failed-03 | `assistant-ui__assistant-ui-3866` | feat(react-langchain): add useLangChainState hook | 2 | +25/-1 | failed |
| agent-failed-04 | `mui__base-ui-2269` | [navigation menu] Support inlined nesting | 5 | +236/-35 | failed |
| agent-failed-05 | `maplibre__maplibre-gl-js-6216` | Prevent original input style from being mutated by `Style.set*` | 2 | +25/-6 | failed |
| agent-failed-06 | `RocketChat__Rocket.Chat.ReactNative-6382` | fix: emoji not getting rendered as avatar | 2 | +8/-2 | failed |

## 当前结论

- 已验证：公开预测文件与结果文件哈希、12 个任务身份、公开 issue/PR 快照、补丁
  非空性、补丁统计、分层选择规则、盲化 reviewer packet 和本地材料绑定。
- 未验证：本机重新执行官方 scorer、四组 Agent 配对审核、真人盲评、误放行率、
  误阻塞率、认知负担和成本效果。
- 因此，本结果只证明“真实候选评测集已经可复现地建立”，不证明 Delivery
  Clearance 已经有效，也不授权任何候选进入客户或生产范围。

## 放行边界

功能测试通过不等于交付放行。12 个案例的最终 clearance reference 都保持为
`pending_blinded_human_adjudication`。原始补丁和 issue/PR 正文只写入本地忽略目录，
仓库中仅保留哈希、统计量、来源与盲化包。
