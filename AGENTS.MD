# AGENTS instructions (update this header whenever scope or guidance changes)

- Scope: applies to the entire repository. Update this file whenever workflows, commands, or architectural conventions change so future agents stay in sync.
- Preferred stack: Flask + SQLAlchemy + SQLite; keep dependencies minimal and pin them in `requirements.txt`.
- Comments: add short comments near non-obvious logic and update them when behavior changes. Remove stale comments promptly.
- UX: Bootstrap or similarly lightweight CSS/JS from CDNs is acceptable. Use clear labels, descriptions, and basic validation.
- Data model: preserve two-table design (granular items + monthly totals). Keep helper functions that reconcile totals with items.
- Tests/checks: when possible run lightweight sanity commands such as `python -m compileall app.py` before committing.
