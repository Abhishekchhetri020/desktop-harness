# Contributing

Thanks for considering contributing! desktop-harness is small, opinionated, and
designed to be genuinely hackable. The bar for changes:

- **Make the common case shorter.** If a change adds 5 lines of API surface to
  save the average user 20 lines, that's a yes.
- **Don't break the AX tree assumption.** AX → AppleScript → OCR → pixels is
  the priority order. New helpers should pick the highest tier that works.
- **Every error tells the user how to fix it.** Add a remediation string to
  any new exception class.

## Setup

```bash
git clone https://github.com/abhishekchhetri/desktop-harness.git
cd desktop-harness
uv tool install -e . --with pytest --with pytest-timeout --with ruff
```

Run tests:

```bash
pytest tests/                         # unit tests only (no UI)
RUN_LIVE_TESTS=1 pytest tests/        # full suite (opens TextEdit, etc.)
```

Lint:

```bash
ruff check src/
```

## What I want PRs for

- **Domain skills** — markdown recipes for `agent-workspace/domain-skills/<app>.md`.
  Cover an app's most useful AppleScript snippets + the AX paths to its main UI.
  Apps especially wanted: Music, Reminders, Numbers, Pages, Keynote, Discord,
  Zoom, Arc browser, Linear, Things, Obsidian (drive, not be driven by).
- **MCP tools** — wrap a useful helper as a tool in `mcp_server.py`. Keep the
  schema tight; document the input shape.
- **Tests** — especially for the trickier modules (`observers.py`, `recorder.py`).
- **Window snap presets** — cmd-tilde behaviors, halve / quarter tiling, restore.
- **Electron AX shims** — anything that pulls structure out of Electron apps
  (eval JS via DevTools, etc.).
- **Cross-platform plans** — Linux (atspi/uinput) + Windows (UI Automation)
  ports. The MCP surface should be portable; the platform layer swaps.

## What I'd push back on

- Breaking API changes without a deprecation warning + a CHANGELOG entry.
- Adding heavy dependencies (we currently ship pyobjc only).
- "Helpful" abstractions that hide the AX / AppleScript layer instead of exposing it.
- Auto-sending behaviour in any messaging skill (Mail/Messages/Slack). Always
  require explicit user confirmation.

## Coding style

- Black-compatible (88 char lines).
- Type hints on public functions.
- Docstrings on every public function. First line ≤ 100 chars and standalone.
- No `try/except: pass`. Either handle it or let it propagate. The errors module
  exists for this.

## Releasing

1. Bump `__version__` in `src/desktop_harness/__init__.py`.
2. Bump `version` in `pyproject.toml`.
3. Add a section to `CHANGELOG.md`.
4. `git tag v0.x.0 && git push --tags`.
5. GitHub Actions builds + publishes to PyPI on tag.

## Code of Conduct

Be kind. Discuss decisions, not people. If your patch changes behaviour, explain
the user-visible reason.
