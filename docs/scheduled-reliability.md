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
运行，GitHub 收据不存在时也不能宣称定时可靠性验证已经完成。
