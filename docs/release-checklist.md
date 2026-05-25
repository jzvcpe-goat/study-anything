# Release Checklist

## v0.1.0-alpha

- [ ] `python3 -m unittest discover apps/api/tests`
- [ ] `python3 -m compileall -q apps/api/neural_console scripts plugins`
- [ ] `python3 scripts/smoke_core.py`
- [ ] `python3 scripts/setup_env.py --force --output /tmp/neural-console.env`
- [ ] `python3 scripts/check_env.py --env /tmp/neural-console.env --strict`
- [ ] `python -m pip install -e .`
- [ ] `(cd apps/web && npm ci && npm run build && npm audit --audit-level=moderate)`
- [ ] Start API locally and run `API_BASE=http://127.0.0.1:8000 python scripts/verify_full_api_flow.py`.
- [ ] Start `scripts/mock_http_agent.py` and run `API_BASE=http://127.0.0.1:8000 AGENT_ENDPOINT=http://127.0.0.1:8787 ./scripts/verify_mock_http_agent_flow.py`.
- [ ] `docker compose -f infra/compose/docker-compose.yml config`
- [ ] `docker compose -f infra/compose/docker-compose.yml --profile smoke up --build mock-http-agent`
- [ ] `docker compose -f infra/compose/docker-compose.yml up --build`
- [ ] Open Web UI at http://localhost:5173
- [ ] Complete demo learning flow.
- [ ] Check http://localhost:8000/v1/system/status
- [ ] Check http://localhost:8000/v1/agents/status
- [ ] Check http://localhost:8000/v1/plugins
- [ ] Check Langfuse starts at http://localhost:3000
- [ ] Confirm `.env` is not committed.
- [ ] Confirm no secrets in logs, traces, docs, or screenshots.
- [ ] Confirm GitHub Actions `ci` passes.
- [ ] Confirm GHCR image publish workflow is enabled after first push.
- [ ] Tag `v0.1.0-alpha`.
