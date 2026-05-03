# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] — 2026-05-03

### Added
- **MCP server** (`desktop-harness mcp`). Exposes 55 tools over stdio JSON-RPC,
  spec 2025-06-18. Drop-in for Claude Code, Hermes, Codex, Gemini CLI, etc.
- **Window management** — `list_windows`, `window_focus/move/resize/minimize/close`,
  `maximize`, `tile_left/tile_right`, `window_to_display`, `window_bounds`.
- **Live AX observers** — `observe(app, "AXValueChanged", cb)`, `wait_for(...)`,
  context manager `observing(...)`, `unobserve`, `stop_all`. Background CFRunLoop
  per subscription.
- **User-action recorder** — `Recorder().start()/.stop()` captures clicks + keys
  via CGEventTap. `to_json()` / `to_python()` emit replayable artefacts.
  CLI: `desktop-harness record --out replay.py --duration 30`.
- **Typed errors with remediation** — `AccessibilityNotGranted`, `AppNotRunning`,
  `ElementNotFound` etc. all carry one-line `remedy` strings.
- **Domain skills** — Safari, Messages, Calendar, VS Code, Slack, Photos,
  System Settings (added to existing Finder, Mail, Notes, Telegram).
- **Tests** — pytest suite with 38 cases; live tests opt-in via `RUN_LIVE_TESTS=1`.
- **GitHub Actions CI** — runs on macos-latest on every PR.

### Fixed
- `cli._build_namespace` no longer collides on `ocr` (function vs module).
- `osascript` only passes `-l` when `language=` is explicitly set.

## [0.1.1] — 2026-05-02

### Fixed
- `cli._build_namespace` re-export collision (`ocr`).
- `osascript` always-passes-`-l applescript` bug.

## [0.1.0] — 2026-05-02

Initial release.

- AX find / find_all / click / get_value / set_value / dump
- AppleScript bridge (`osascript`, `tell`, `jxa`)
- CGEvent input (mouse + keyboard, Unicode-clean type, scroll, drag)
- Screen capture (full / window / region)
- Vision OCR (`ocr`, `ocr_region`, `ocr_window`, `find_text_on_screen`)
- TCC permission probes (`doctor_permissions`)
- CLI: `-c "expr"`, `-f file.py`, `--doctor`, `--ax APP`, `--screenshot`
