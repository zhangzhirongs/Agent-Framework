# Development Guidelines

- Keep this starter focused on configurable chat, standard skills and MCP.
- Store credentials only in an ignored `.env` or external secret store.
- Keep SDK task execution in `app/runtime.py`, HTTP/auth in `app/api.py`, and persistence in `app/store.py`.
- Skills live directly in `skills/<name>/SKILL.md`; keep resources beside that file.
- MCP configuration uses the standard `mcpServers` object; reference secrets through environment variables.
- Preserve user ownership checks and CSRF protection when extending routes or tools.
- Use appropriately licensed assets and never commit credentials or runtime data.
- Verify with `uv run pytest -q`, `uv run ruff check app tests scripts`, `npm run build` and `npm test` in `web`.
- Do not publish or deploy without the project owner's instruction.
