# NotebookLM-Style Fixtures

These fixtures model a NotebookLM-style handoff without depending on a NotebookLM official API.

- `notebooklm-style-context-package.json` is an import fixture a platform Agent can build after collecting user-approved web, document, video, app, Markdown, and Obsidian context.
- Study Anything validates the fixture as `learning-context-package-v1`, creates or expands a learning session, and later exports `learning-package-v1` for NotebookLM-style, platform-agent, Obsidian, or local archive workflows.
- Raw source excerpts are accepted only at the import boundary. Obsidian and learning-package exports keep references, hashes, teaching artifacts, review state, and bridge metadata without leaking the raw fixture excerpts.
