# Locked Python Requirements

These files are generated from the universal `uv.lock` by
`scripts/generate_python_supply_chain.py`. Do not edit them by hand.

- `locked-skill.txt`: local Skill Mode and crypto support.
- `locked-full.txt`: the self-host API and full infrastructure adapters.
- `locked-dev-full.txt`: CI, release gates, and the full runtime.
- `locked-policy.txt`: lightweight repository policy and verifier jobs.

Every package is pinned and carries one or more SHA-256 hashes. The local Study Anything package
is installed separately with `--no-deps --no-build-isolation` after the locked dependencies.

Refresh with uv 0.11.18 or newer:

```bash
python3 scripts/generate_python_supply_chain.py --refresh
```

Verify without resolving new versions or using the network:

```bash
python3 scripts/generate_python_supply_chain.py --check
```

After downloading a reviewed `uv.lock` candidate from CI, rebuild every projection offline:

```bash
python3 scripts/generate_python_supply_chain.py --refresh-from-lock
```
