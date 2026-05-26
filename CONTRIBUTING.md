# Contributing

Thanks for helping build Study Anything.

## Development Loop

1. Open an issue or comment on an existing one.
2. Keep changes focused.
3. Add tests for behavior changes.
4. Run the core test suite:

```bash
python3 -m unittest discover apps/api/tests
```

5. For full-stack work, run:

```bash
python3 scripts/setup_env.py
./scripts/release_check.sh
STACK_PROFILE=smoke ./scripts/launch_self_host.sh
API_BASE=http://127.0.0.1:8000 python3 scripts/verify_full_api_flow.py
API_BASE=http://127.0.0.1:8000 AGENT_ENDPOINT=http://mock-http-agent:8787 python3 scripts/verify_mock_http_agent_flow.py
./scripts/stop_self_host.sh
```

## Project Boundaries

- Core learning workflow belongs in `apps/api/study_anything/core`.
- HTTP transport belongs in `apps/api/study_anything/api`.
- UI state should come from public APIs, not duplicate backend logic.
- Real model providers must be user-configured and observable.
- Do not commit secrets, model credentials, private traces, or user data.

## Plugin Contributions

Plugins must include a manifest, declare permissions, and document data access. See `docs/plugins.md` and `plugins/example-exporter`.
