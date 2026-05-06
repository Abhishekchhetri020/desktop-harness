# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.5.0] — 2026-05-07

### Added — production hardening (no daemon, intentionally)

- **Stable element refs (`refs.py`)** — replaces v0.4's volatile `ax_<n>`
  counter with structured fingerprints. Each ref now carries
  `app + bundle_id + pid + role + subrole + title + identifier + path
  + frame + fingerprint`. When the cached AXUIElement handle goes
  stale (window closed, view recycled, Electron re-render), `resolve_ref`
  walks the live AX tree to re-find the element by path-replay, then
  by identifier, then by role+title. Playwright's locator pattern,
  applied to macOS.
  - New API: `ElementRef`, `create_element_ref`, `resolve_ref`,
    `refresh_ref`, `re_find_element`, `is_stale`, `describe_element`,
    `element_bounds`, `list_refs`, `get_ref`.
- **Smart action engine (`smart.py`)** — structured-result wrappers
  with explicit tier reporting. Every call returns
  `{ok, tier, ref?, tried[], hint?, screenshot_path?}`. Native AX
  success path NEVER takes a screenshot; vision tier is reported
  explicitly when reached.
  - New API: `smart_click` (v2, supersedes the v0.4 vision.smart_click),
    `smart_type`, `smart_set_value`, `smart_menu`, `smart_open`.
- **Wait + verify primitives (`waiters.py`)** — agents no longer need
  blind `time.sleep` loops. Polling-with-deadline + structured timeout
  reports including `method`, `elapsed`, and a hint.
  - New API: `wait_for_app`, `wait_for_frontmost`, `wait_for_window`,
    `wait_for_element`, `wait_until_value`, `wait_for_text`,
    `verify_window_open`, `verify_text_present`, `verify_clicked`.
- **Safety layer (`safety.py`)** — `classify_action_risk` returns
  `safe | caution | destructive`. `confirmed_action` wrapper raises
  `ConfirmationRequired` for destructive ops without `confirm=True` /
  `dry_run=True`. Action log preserves the last 200 actions.
  - New API: `classify_action_risk`, `confirmed_action`, `recent_actions`,
    `clear_action_log`, `DESTRUCTIVE_KEYWORDS`, `DESTRUCTIVE_PRONE_APPS`.
- **App adapter registry (`adapters/`)** — three high-value adapters
  ship in v0.5: **Finder, Notes, Mail**. Each declares
  `safe_actions` vs `dangerous_actions` and routes destructive ops
  through the safety layer.
  - Finder: open_folder, reveal, selected_items, copy_selected_paths,
    front_window_path, current_folder; create_folder, move_to_trash,
    rename (gated).
  - Notes: list_folders, list_notes, search_notes, read_selected_note,
    current_note_title; create_note, append_to_note, delete_note (gated).
  - Mail: draft_email (safe — opens compose window only), list_inbox,
    search_mail, read_selected_email, list_mailboxes; **send_email**
    (always gated — programmatic send requires `confirm=True`).
  - New API: `Adapter`, `register_adapter`, `get_adapter`,
    `list_adapters`, `adapter_actions`, `perform_adapter_action`,
    `FinderAdapter`, `NotesAdapter`, `MailAdapter`.
- **Structured errors v2** — every `DesktopHarnessError` subclass now
  accepts `app`, `target`, `tried[]`, `hint` and exposes `.as_dict()`
  for MCP responses. New: `ConfirmationRequired`, `StaleElementRef`.
- **MCP server: 14 new high-level tools** (78 total, was 64):
  `desktop_smart_click`, `desktop_smart_type`, `desktop_smart_set_value`,
  `desktop_smart_menu`, `desktop_smart_open`,
  `desktop_wait_for_element`, `desktop_wait_for_window`,
  `desktop_classify_risk`, `desktop_recent_actions`,
  `desktop_list_adapters`, `desktop_adapter_actions`,
  `desktop_perform_adapter_action`,
  `desktop_resolve_ref`, `desktop_list_refs`.
  Destructive tools clearly marked in their description.
- **CLI subcommands**: `snapshot`, `click`, `type`, `menu`, `wait`,
  `adapter` — all backed by smart_* / waiters / adapter registry.
- **`--setup` wizard** — walks Accessibility / Screen Recording /
  Automation / Input Monitoring panes, opening each System Settings
  pane and re-checking after the user grants permission.
- **63 new tests** (101 passed total, 11 live-only skipped). New files:
  `test_refs.py`, `test_smart.py`, `test_waiters.py`, `test_safety.py`,
  `test_adapters.py`, `test_errors_v2.py`, `test_mcp_server_v05.py`.
- Added **Google Antigravity** (`com.google.antigravity`) and
  **Open CoDesign** (`ai.opencowork.codesign`) to the `ELECTRON_APPS`
  classifier so `smart_click` skips unreliable AX tiers and goes faster
  to OCR/vision fallback.

### Architecture note — why v0.5.0 has NO daemon

browser-harness uses a daemon because Chrome DevTools Protocol is a
stateful WebSocket — closing the connection loses session state.
macOS Accessibility is **stateless RPC**: every PyObjC call into the
AX API is independent and costs <5ms. Adding a daemon would impose
IPC latency, force JSON serialisation of volatile AXUIElement pointers
(which don't survive across processes anyway), and add a process to
manage — for **zero functional benefit**. The MCP server is already a
long-lived process and holds state across tool calls; the CLI is
intentionally stateless.

A daemon becomes justified only when at least one of these is true,
none of which apply today:

1. We need to share AX state across **separate CLI invocations** (not
   covered by an MCP session). Today every CLI call boots fresh, runs,
   and exits — there's no state to share.
2. We need a **persistent CDP-like connection** to a long-lived OS
   subsystem. macOS doesn't have one; AX calls go directly to the
   target process via Mach IPC.
3. We need a **broker** for parallel agents that must NOT contend on
   the same AX events. Multiple MCP processes already give us this for
   free; if and when CLI-level parallelism becomes a real workflow
   we'd revisit.

If those constraints change (e.g. browser-use cloud expands to a remote
desktop relay, or agents need to share AX observer subscriptions) we
will add `daemon.py` + `_ipc.py` then. Not before.

### Backwards compatibility

- All v0.4.0 public API names continue to work.
- `vision.smart_click` (the v0.4 implementation) is preserved internally
  as `_vision_smart_click`; the public `smart_click` now refers to the
  v0.5 structured-result version.
- All 64 existing MCP tools still register and dispatch identically.

## [0.4.0] — 2026-05-03

### Added — the vision tier (closes the Electron gap vs computer-use)
- **`smart_click(target, app=?)`** — the new default click tool. Auto-falls-
  through AX → OCR → vision. ONE call, the harness picks the right tier and
  reports which won. Saves ~2s per call on Electron apps by skipping the
  doomed AX tries entirely.
- **`app_class(app)`** + **`ELECTRON_APPS`** registry — classifies apps as
  `electron`/`applescript`/`native_ax`/`unknown`. Obsidian, Slack, VS Code,
  Discord, Notion, Figma, Linear, Cursor, Spotify, Warp, Arc, Zoom,
  Perplexity, Claude desktop are all flagged Electron and skip AX.
- **`screenshot_with_grid(app=?, grid=12)`** — captures a screenshot with a
  labeled NxN coordinate grid burnt in (cells A1..L12 by default). Returns
  base64 PNG + a `cells` dict mapping each label to its (x,y) center pixel.
  The agent says "click G7" and we resolve to coords deterministically.
- **`click_cell(label, ...)`** — click the center of a labeled cell.
- **`vision_act(task, app=?)`** — wraps everything the agent needs to act
  visually: grid screenshot, OCR text+coords, AX summary if available, and
  heuristic next-step recommendations. Use when AX returns nothing.
- 5 new MCP tools (now 64 total).

### Background

The v0.3.0 Obsidian test took 7 minutes because the agent (me) kept retrying
AX queries on a sparse Electron tree. computer-use was faster because it
goes pixel-first. v0.4.0 closes that gap by giving the agent ONE primitive
(`smart_click`) that auto-picks the right tier per app, and ONE primitive
(`vision_act`) that hands back a screenshot the model can reason about
visually with ready-made click coords. Native apps still get the AX fast
path; Electron apps go straight to vision.

## [0.3.0] — 2026-05-03

### Added
- **`accessibility_snapshot`** — one-shot, structured JSON of every interactive
  element in an app, with stable refs (`ax_42`) you can pass to `ax_click` /
  `ax_get_value` / `ax_set_value`. The headline ergonomic upgrade: an LLM gets
  a compact, navigable view of the UI in one MCP call instead of needing to
  walk the tree node by node. Inspired by Playwright MCP's snapshot mode.
- **`click_text`** — hybrid AX + OCR helper. If `app` is given, finds the
  element whose title/value contains a needle and clicks via AX. Otherwise
  OCRs the screen and clicks the matched pixel center. The "just click the
  thing that says X" primitive every agent needs.
- **`scrape_app`** — extract an app's visible text content as Markdown by
  walking the AX tree (windows → headings, static text → paragraphs,
  text fields → fenced code blocks). Mirror of macOS-MCP's `Scrape` tool.
- **`batch_actions`** — run multiple actions sequentially in ONE MCP call.
  Cuts roundtrip latency for predictable sequences (click → type → enter).
  Stops on first failure unless `continue_on_error: true`.
- 4 new MCP tools (now 59 total).

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
