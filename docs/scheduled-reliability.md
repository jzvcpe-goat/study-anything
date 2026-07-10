# Scheduled Source-Build And Published-Image Reliability

The `reliability-soak` GitHub workflow checks two equal release paths every week and on manual
dispatch:

1. `source-build` builds the API from the checked-out repository in an isolated Compose project.
2. `published-image` pulls the selected GHCR API tag and runs the same isolated Compose project.

Each job completes the deterministic fake-Agent API flow, starts a real-time bounded health soak,
stops the API container once, starts it again, and requires a successful health probe after the
failure window. It also reads the mastery state for the learning session created before the restart,
so health-only recovery is insufficient. The default schedule collects 721 samples ten seconds
apart, so the sampling window is two hours. Both modes must satisfy the same `0.99` success-ratio
threshold and maximum of eight consecutive failed probes.

## Manual Short Acceptance

Use GitHub Actions `reliability-soak` > **Run workflow** and reduce the four timing inputs for a short
acceptance run. Keep enough samples for the interruption to finish before the final probe. You may
lower the success ratio or raise the consecutive-failure budget only for this diagnostic run. A
short or relaxed-threshold run proves only that the workflow and recovery mechanics operate; it is
not equivalent to the default two-hour window.

The same source-build path can be exercised locally:

```bash
python3 scripts/self_host_reliability_matrix.py \
  --mode source-build \
  --samples 20 \
  --interval-seconds 2 \
  --fault-after-seconds 4 \
  --fault-duration-seconds 6 \
  --min-success-ratio 0.4 \
  --max-consecutive-failures 10 \
  --output .cognitive-loop/artifacts/reliability/source-build-short.json
```

For the published path, add `--mode published-image`, `--tag TAG`, and `--api-image IMAGE:TAG`.
The runner always pulls the named published API image first. Compose may still pull missing dependency
images such as Postgres on a clean runner; there is no API image skip-pull mode.

Compose startup is retried at most three times with a ten-second delay to absorb transient registry
or build failures. The receipt records the actual attempt count. Exhausting the retries blocks the
job with a classified `*_after_retries` failure; retries never weaken soak or recovery thresholds.

## Longitudinal Evidence Index

After both matrix jobs finish, a separate GitHub job downloads their metadata-only receipts and
builds `self-host-reliability-index-v1`. The index records the workflow run ID, event, head commit,
canonical receipt hashes, source commit or published image digest, requested thresholds, aggregate
sampling results, restart/recovery state, and the run decision. It never copies workflow logs,
Docker output, endpoints, image repository references, source text, learner answers, or secrets.

The index classifies a run as `strict_dual_pass` only when both modes use the exact default profile:
721 samples, ten-second intervals, a fault at 600 seconds for 45 seconds, a 0.99 minimum success
ratio, at most eight consecutive failures, observed recovery, and at least 7,200 seconds of elapsed
evidence. Short runs are `diagnostic_only`; a strict/diagnostic mix is blocked. Source-build and
published-image evidence have equal weight.

The index artifact is retained for 90 days. One strict dual pass proves one bounded run. The index
requires three strict dual passes before setting its limited `longitudinal_trend_claimable` signal,
and it always keeps `production_slo_claimable=false`.

### Replay An Index From A Completed Run

If both mode jobs completed and uploaded passing receipts but the index job itself failed for an
infrastructure or workflow-policy reason, dispatch `reliability-soak` again with only
`evidence_run_id` set to the completed source run. The source-build and published-image jobs are
skipped. The index job downloads only same-repository artifacts from that exact completed
`reliability-soak` run, resolves its event and head SHA from the GitHub API, revalidates both
receipts, and uploads `reliability-index-SOURCE_RUN_ID`.

Replay does not repair or replace a failed mode receipt and does not turn a short run into strict
evidence. A missing artifact, different workflow path, unfinished run, source-commit mismatch,
mixed profile, failed receipt, or privacy violation still blocks the index.

To rebuild or append an index offline from downloaded receipts:

```bash
python3 scripts/reliability_evidence_index.py \
  --run-id RUN_ID \
  --event schedule \
  --head-sha COMMIT_SHA \
  --source-receipt source-build.json \
  --published-receipt published-image.json \
  --previous-index previous-index.json \
  --output .cognitive-loop/artifacts/reliability/self-host-reliability-index.json
```

Omit `--previous-index` for the first run. Add `--require-strict-pass` only when a caller explicitly
needs to reject valid diagnostic or blocked evidence.

## Receipt And Privacy Boundary

Each job uploads one `self-host-reliability-matrix-receipt-v1` JSON artifact for 14 days. The receipt
contains mode, timing, aggregate probe results, classified failure phase, build/pull completion,
source commit or pulled image digest, controlled restart state, and recovery state. It excludes the
image repository reference, Compose project name,
environment path, API URL, response bodies, Docker logs, command output, secrets, source text,
learner answers, and local absolute paths. The isolated Compose project and its test volumes are
removed after the run unless a local operator explicitly requests failure preservation.

A passing receipt proves only that selected source or image completed that one isolated elapsed-time
window. It is not a production SLO, disaster-recovery certification, customer availability promise,
or proof that a scheduled run occurred before the corresponding GitHub artifact exists.

## 中文说明

每周任务会分别验证“当前源码构建”和“已发布 GHCR 镜像”。两边都必须完成学习 API
闭环、经历一次真实 API 容器停止与重启，并在故障后重新观察到健康响应。收据只保存汇总
metadata，不保存密钥、URL、日志、正文、答案或本机路径。短时手动运行不能替代默认两小时
运行，GitHub 收据不存在时也不能宣称定时可靠性验证已经完成。工作流会额外生成纵向索引；
只有两种模式都满足严格默认参数才记为一次严格双通过，至少三次才允许声称存在有限趋势，
并且无论运行多少次都不会自动升级为生产 SLO。如果双路径已成功、但索引作业因基础设施或
工作流策略失败，可以用原始 run ID 重放索引；重放不会重新执行或放宽双路径收据。
