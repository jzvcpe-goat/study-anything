# Validation Assets

This directory stores committed, metadata-only outputs from reproducible Delivery
Clearance validation runs.

`results/real-project-v0.1/` replays four real repository states from one development
sequence. Rebuild it with:

```bash
.venv/bin/python scripts/delivery_clearance_project_scenarios.py --replace
```

The committed result excludes source text, raw check output, local paths, credentials, and
human answers. Human sessions are written only to the ignored `.delivery-clearance/`
directory and must not be synthesized by an Agent.
