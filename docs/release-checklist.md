# Release Checklist

## v0.2.2-alpha

- [ ] Create `.venv` with Python 3.11+ and run `.venv/bin/python -m pip install -e .`.
- [ ] `.venv/bin/python -m unittest discover apps/api/tests`
- [ ] `LANGGRAPH_STRICT_MSGPACK=true .venv/bin/python -m unittest discover apps/api/tests`
- [ ] `.venv/bin/python -m compileall -q apps/api/study_anything scripts plugins`
- [ ] `.venv/bin/python scripts/smoke_core.py`
- [ ] `python3 scripts/setup_env.py --force --output /tmp/study-anything.env`
- [ ] `python3 scripts/check_env.py --env /tmp/study-anything.env --strict`
- [ ] `(cd apps/web && npm ci && npm run build && npm audit --audit-level=moderate)`
- [ ] Start API locally and run `API_BASE=http://127.0.0.1:8000 python scripts/verify_full_api_flow.py`.
- [ ] Start `scripts/mock_http_agent.py` and run `API_BASE=http://127.0.0.1:8000 AGENT_ENDPOINT=http://127.0.0.1:8787 ./scripts/verify_mock_http_agent_flow.py`.
- [ ] `docker compose --env-file .env -f infra/compose/docker-compose.yml config`
- [ ] `docker compose --env-file .env -f infra/compose/docker-compose.yml --profile smoke up --build mock-http-agent`
- [ ] `STACK_PROFILE=core ./scripts/launch_self_host.sh`
- [ ] `USE_PUBLISHED_IMAGES=true ./scripts/launch_self_host.sh`
- [ ] `WEB_BASE=http://127.0.0.1:5173 python3 scripts/verify_full_stack_web.py`
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
- [ ] Tag `v0.2.2-alpha`.
