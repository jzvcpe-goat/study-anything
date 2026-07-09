# Self-Host Reliability And Recovery

This guide is for a single local operator. It proves a bounded self-host window and provides a
reversible recovery path. It is not a production SLO, disaster-recovery certification, or hosted
service guarantee.

## One-Command Health Soak

Start the core stack first:

```bash
python3 scripts/setup_env.py
./scripts/launch_self_host.sh
```

Then run a one-minute health window:

```bash
python3 scripts/self_host_soak.py \
  --samples 12 \
  --interval-seconds 5 \
  --output .cognitive-loop/artifacts/reliability/self-host-soak.json
```

The command reads the private local API token from the environment or `.env`. It never writes the
token, API URL, response body, Docker logs, source text, answers, or local absolute paths into the
receipt. The output file is created with local-user-only permissions.

- `status=pass`: this one bounded health window stayed inside the selected success and consecutive
  failure thresholds.
- `status=blocked`: inspect `blocked_reasons` and `failure_categories` before relying on the runtime.
- `recovered_after_failure=true`: at least one healthy probe followed a failed probe. This records an
  observed HTTP recovery only; it does not prove data recovery.

For a stricter or longer operator window, change the explicit thresholds:

```bash
python3 scripts/self_host_soak.py \
  --samples 120 \
  --interval-seconds 30 \
  --request-timeout-seconds 5 \
  --min-success-ratio 0.99 \
  --max-consecutive-failures 1 \
  --output .cognitive-loop/artifacts/reliability/self-host-soak.json
```

Loopback is the default. If an intentional private-network deployment requires bearer authentication,
verify the destination first and add `--allow-network-token`; without that explicit confirmation the
command refuses to send the token read from `.env` to a non-loopback host. Health probes also reject
HTTP redirects so an authorization header cannot be forwarded to a second origin.

## Five-Step Recovery Walkthrough

Use this order when the local service is unhealthy or before an upgrade:

1. Diagnose without changing data.

   ```bash
   ./scripts/doctor.sh
   docker compose --env-file .env -f infra/compose/docker-compose.yml ps
   ```

   If launch reports that Postgres credentials do not match the existing data volume, stop there.
   Recover the `.env` that initialized that volume or the `env.snapshot` from a trusted backup. Do
   not run `docker compose down -v` and do not regenerate the database password while the data matters.

2. Create a private backup before changing containers or volumes.

   ```bash
   python3 scripts/self_host_data.py backup
   ```

3. Restart only the self-host stack.

   ```bash
   ./scripts/stop_self_host.sh
   ./scripts/launch_self_host.sh
   ```

4. Run the short health soak above. Do not restore data merely because one probe failed.

5. If the canonical data is actually damaged, inspect the selected backup manifest and use the
   explicit destructive restore command documented in [Self-Hosting](self-hosting.md#backup-and-restore).
   There is intentionally no remote restore API.

To rehearse backup and rollback without touching the real project volumes, use the disposable Docker
drill:

```bash
python3 scripts/verify_backup_restore_drill.py
```

This drill owns a separate Compose project and removes its test volumes after success. It is still a
local rehearsal, not proof that every host, storage provider, or published image can recover.

## Trace Retention Boundary

Langfuse is optional and starts only with the `full` profile. Study Anything emits privacy-preserving
event observations; operators remain responsible for database backups, retention periods, access
control, and deletion in their own Langfuse deployment.

- Keep traces off when they are not needed.
- Do not add raw source text, learner answers, prompts, credentials, or response bodies to custom
  trace metadata.
- Define retention and deletion at the self-hosted Langfuse/Postgres/ClickHouse layer before exposing
  the service outside one machine.
- Back up the canonical Study Anything Postgres state independently. Langfuse traces are operational
  evidence, not the source of truth.
- Treat optional-service backups as sensitive and encrypt them at rest.

The repository now includes a scheduled source-build and published-image restart matrix; see
[Scheduled Reliability](scheduled-reliability.md). A two-hour result may be claimed only for a real
GitHub run that produced the corresponding passing receipts. Automated incident response, production
SLOs, and certified retention enforcement remain outside the current claim boundary.

## 中文速用

1. 先运行 `python3 scripts/setup_env.py && ./scripts/launch_self_host.sh`。
2. 运行上面的 `self_host_soak.py` 一分钟检查，`pass` 只代表这次短窗口通过。
3. 出问题先执行 `./scripts/doctor.sh`，不要直接删 volume。
4. 改动前执行 `python3 scripts/self_host_data.py backup`。
5. 只有确认数据损坏后才执行显式 restore；系统故意不提供远程恢复 API。

收据只保存统计 metadata，不保存健康响应正文、token、URL、源码、答案或本机绝对路径。
