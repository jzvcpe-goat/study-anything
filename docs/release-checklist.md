# Release Checklist

## v0.2.3-alpha

- [ ] Create `.venv` with Python 3.11+ and run `.venv/bin/python -m pip install -e .`.
- [ ] `.venv/bin/python -m unittest discover apps/api/tests`
- [ ] `LANGGRAPH_STRICT_MSGPACK=true .venv/bin/python -m unittest discover apps/api/tests`
- [ ] `.venv/bin/python -m compileall -q apps/api/study_anything scripts plugins`
- [ ] `.venv/bin/python scripts/smoke_core.py`
- [ ] `./scripts/run_skill_mode_demo.sh`
- [ ] `python3 scripts/setup_env.py --force --output /tmp/study-anything.env`
- [ ] `python3 scripts/check_env.py --env /tmp/study-anything.env --strict`
- [ ] `(cd apps/web && npm ci && npm run build && npm audit --audit-level=moderate)`
- [ ] Start API locally and run `API_BASE=http://127.0.0.1:8000 python scripts/verify_full_api_flow.py`.
- [ ] Start `scripts/mock_http_agent.py` and run `API_BASE=http://127.0.0.1:8000 AGENT_ENDPOINT=http://127.0.0.1:8787 ./scripts/verify_mock_http_agent_flow.py`.
- [ ] `docker compose --env-file .env -f infra/compose/docker-compose.yml config`
- [ ] `./scripts/doctor.sh`
- [ ] Non-ASCII checkout paths produce an actionable Docker source-build diagnostic or use `USE_PUBLISHED_IMAGES=true`.
- [ ] `docker compose --env-file .env -f infra/compose/docker-compose.yml --profile smoke up --build mock-http-agent`
- [ ] `STACK_PROFILE=core ./scripts/launch_self_host.sh`
- [ ] `USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh`
- [ ] `WEB_BASE=http://127.0.0.1:5173 python3 scripts/verify_full_stack_web.py`
- [ ] Check http://localhost:8000/v1/metrics/pmf returns `schema_version=pmf-v1` without source text, answers, insights, or raw contact values.
- [ ] Record one local PMF intent with `POST /v1/pmf/interest` and verify `GET /v1/pmf/summary` increments without storing raw contact.
- [ ] Verify `POST /v1/pmf/export` returns `409` without consent and `schema_version=pmf-export-v1` with `consent_to_share=true`.
- [ ] `python3 scripts/self_host_data.py backup --output /tmp/study-anything-backup-check`
- [ ] Restore that backup in a disposable local stack with `python3 scripts/self_host_data.py restore /tmp/study-anything-backup-check --yes`.
- [ ] Open Web UI at http://localhost:5173
- [ ] Complete demo learning flow.
- [ ] Install a local example plugin with `python3 scripts/install_local_plugin.py plugins/example-exporter --destination /tmp/study-anything-plugin-check`.
- [ ] Check http://localhost:8000/v1/system/status
- [ ] Check http://localhost:8000/v1/agents/status
- [ ] Check http://localhost:8000/v1/plugins
- [ ] Check Langfuse starts at http://localhost:3000
- [ ] Confirm `.env` is not committed.
- [ ] Confirm no secrets in logs, traces, docs, or screenshots.
- [ ] Confirm local backups remain ignored by Git and are stored encrypted at rest.
- [ ] Confirm GitHub Actions `ci` passes.
- [ ] Confirm GHCR image publish workflow is enabled after first push.
- [ ] Tag `v0.2.3-alpha`.
