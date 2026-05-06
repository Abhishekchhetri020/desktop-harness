# desktop-harness

> Drive any macOS app from a CLI or AI agent. AX-tree-aware. Built-in MCP server.

[![macOS](https://img.shields.io/badge/macOS-12%2B-blue)](https://www.apple.com/macos/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-2025--06--18-purple)](https://spec.modelcontextprotocol.io/)

`desktop-harness` is a hackable Python toolkit that drives native macOS apps the way they were
meant to be driven — through the **Accessibility API** (the DOM equivalent for native apps),
**AppleScript / JXA** (deep app dictionaries), **CGEvent** (raw mouse + keyboard), and
**Vision OCR** (when nothing else works). It ships with a first-class **MCP server** so any
LLM agent (Claude Code, Hermes, Codex, Gemini CLI, OpenAI Agent SDK, ...) can drive your Mac
through it without a single line of glue code.

```python
from desktop_harness import find, click_element, type_text, key

# Click "New Note" in Apple Notes — no pixel coords, no OCR
click_element(find("Notes", role="AXButton", title="New Note"))

# Type "Hello 🌎" into whatever's focused (works for emoji + CJK)
type_text("Hello 🌎")
key("cmd+s")
```

## Why this exists

Most "computer-use" tools today drive your machine by **looking at pixels**. They take a
screenshot, ask an LLM to reason about where a button is, then click coordinates. That's
slow, brittle, and falls over on Retina scaling, dark mode, app updates, dialog overlays.

macOS exposes a **structured tree of every UI element in every app** via the Accessibility
API. desktop-harness uses that tree directly. You can:

- `find("Slack", role="AXButton", title="Send")` and press it — exact coords irrelevant.
- `get_value(find("Terminal", role="AXTextArea"))` returns **963,513 chars of scrollback in
  milliseconds**. OCR cannot match this.
- Subscribe to `AXValueChanged` notifications and react when a text field is edited,
  without polling.

### Honest capability matrix

desktop-harness is **structured control first, screenshots last** — not "no screenshots
ever". macOS itself can't see inside Electron apps, so for those we fall through to
vision. Every smart action reports which tier it used.

| App category | Examples | AX-only path | Vision required? |
|---|---|---|---|
| Apple's own apps | Notes, Mail, Calendar, Safari, Finder, Messages, System Settings, TextEdit, Music, Photos | ✅ instant | no |
| Native Cocoa / SwiftUI | 1Password, Things 3, BBEdit, OmniFocus, MarsEdit | ✅ instant | no |
| AppleScript-driveable | Mail, Calendar, Music, Numbers, Pages, Word, Excel, OmniFocus | ✅ via `tell()` | no |
| Pure keyboard workflows | any app — `cmd+s`, `cmd+shift+p`, hotkeys | ✅ via CGEvent | no |
| Electron / Chromium-shell | Slack, VS Code, Cursor, Obsidian, Discord, Notion, Figma, Linear, Spotify, Zoom, Warp, Arc, Perplexity, Claude desktop | ⚠️ AX is sparse | **yes** (auto-falls-through) |
| Custom-rendered | Photoshop canvas, Final Cut timeline, Blender, games | ❌ AX empty | **yes** |
| Java/JVM without AX bridge | older JetBrains, some enterprise tools | ❌ AX empty | **yes** |

There is no API path on macOS to read DOM-level controls inside a Chromium frame. v0.5.0
ships with the Electron registry pre-populated, so `smart_click` skips AX tiers entirely
for those apps and goes straight to OCR/vision.

Compared to pixel-driving:

| | Pixel-based tools | **desktop-harness** |
|---|---|---|
| How it sees the UI | Screenshot only | **AX tree (structured)** + screenshot fallback |
| Read TextArea content | OCR (slow, lossy) | `get_value()` — instant, exact |
| Click button by name | Screenshot → reason → click pixel | `click_element(find(role="AXButton", title="Save"))` |
| AppleScript dictionaries | Not used | First-class via `tell()` / `jxa()` |
| Live event subscriptions | No | `observe(app, "AXValueChanged", cb)` |
| User-action recording | No | `desktop-harness record --out replay.py` |
| MCP server for agents | No | `desktop-harness mcp` exposes **78** tools |
| CLI eval mode | No | `desktop-harness -c "expr"` |
| Self-extending | No | `agent_helpers.py` + `domain-skills/*.md` |

## v0.5.0 highlights

- **Stable element refs** (`refs.py`). Refs survive across snapshots; they re-find by
  path-replay when the AX handle goes stale (Playwright locator pattern for macOS).
- **Smart action engine** (`smart_click` / `smart_type` / `smart_set_value` / `smart_menu`
  / `smart_open`). Every call returns `{ok, tier, ref, tried[], hint?}`. AX-success path
  never takes a screenshot; vision tier is reported explicitly when reached.
- **Wait + verify primitives** (`wait_for_element`, `wait_until_value`, `wait_for_window`,
  …). No more blind `time.sleep` loops.
- **Safety layer** (`classify_action_risk`, `confirmed_action`). Destructive actions
  (`send_email`, `delete_note`, `move_to_trash`, …) require `confirm=True` or
  `dry_run=True`.
- **App adapter registry** with three high-value adapters: Finder, Notes, Mail. Each
  declares safe vs dangerous actions explicitly.
- **78 MCP tools** (was 64) including `desktop_smart_click`, `desktop_perform_adapter_action`,
  `desktop_wait_for_element`, `desktop_classify_risk`. Destructive tools clearly marked.
- **CLI subcommands**: `snapshot`, `click`, `type`, `menu`, `wait`, `adapter`. `--setup`
  wizard walks the four System Settings panes.

### Why no daemon yet?

browser-harness ships a daemon because Chrome DevTools Protocol is a stateful WebSocket.
macOS Accessibility is **stateless RPC** — every call is independent and costs <5ms. A
daemon would impose IPC latency, force JSON serialisation of volatile AXUIElement
pointers (which don't survive across processes anyway), and add a process to manage —
all for **zero functional benefit**. The MCP server already holds session state across
tool calls; the CLI is intentionally stateless.

A daemon becomes justified only when (a) we need state shared across separate CLI
invocations, (b) macOS gains a CDP-equivalent persistent connection, or (c) parallel
agents must share AX observer subscriptions. None of those apply today; we'll add it
when reality demands it.

## Install

```bash
# Recommended (uv installs to an isolated venv with the CLI on $PATH)
uv tool install desktop-harness

# Or via pipx
pipx install desktop-harness

# Or plain pip (you'll need to add the script dir to PATH)
pip install desktop-harness
```

Then grant the harness three macOS permissions (one-time, ~30 seconds):

```bash
desktop-harness --doctor
```

It tells you exactly which switches to flip in **System Settings → Privacy & Security**:
- **Accessibility** (required for AX find/click and CGEvent input)
- **Screen Recording** (required for screenshots and OCR)
- **Automation** (required for AppleScript — granted per target app on first use)

For the action recorder, you also need:
- **Input Monitoring**

## Quick start

```bash
# Live demo — opens TextEdit, dumps its AX tree, takes a screenshot
desktop-harness demo

# Inspect any running app's UI tree
desktop-harness --ax Notes --ax-depth 4

# One-shot Python with all helpers pre-loaded
desktop-harness -c 'click_element(find("Calculator", role="AXButton", title="7"))'

# Take a screenshot
desktop-harness --screenshot /tmp/now.png

# Record yourself, then replay
desktop-harness record --out /tmp/replay.py --duration 20
python3 /tmp/replay.py
```

## Use it from any AI agent (MCP)

`desktop-harness mcp` runs a stdio MCP server exposing **55 tools** to any compliant agent.

### Claude Code

```bash
claude mcp add desktop-harness -- desktop-harness mcp
```

### Hermes Agent

`~/.hermes/config.yaml`:

```yaml
mcp_servers:
  desktop-harness:
    command: desktop-harness
    args: [mcp]
```

### Codex (OpenAI)

`~/.codex/config.toml`:

```toml
[mcp_servers.desktop-harness]
command = "desktop-harness"
args = ["mcp"]
```

### Gemini CLI

`~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "desktop-harness": {
      "command": "desktop-harness",
      "args": ["mcp"]
    }
  }
}
```

After wiring, ask the agent something like:

> *"Open System Settings, navigate to Bluetooth, and tell me what devices are paired."*

The agent will call `open_app`, `ax_find`, `ax_get_value`, etc. and answer with verified facts.

## API tour

```python
from desktop_harness import (
    # apps
    list_apps, frontmost, open_app, activate, quit_app,
    # AX (the killer module)
    find, find_all, click_element, get_value, set_value, ax_dump,
    perform_action, focused_element, focus,
    # input
    click_at, type_text, key, scroll, drag,
    # screen + OCR
    screenshot, screenshot_window, ocr, find_text_on_screen,
    # AppleScript / JXA
    osascript, osascript_app, jxa, tell,
    # windows
    list_windows, window_move, window_resize, maximize, tile_left, tile_right,
    # live events
    observe, observing, wait_for, unobserve,
    # action recorder
    Recorder,
)
```

### Find an element by role + title

```python
btn = find("Safari", role="AXButton", title="Reload Page")
click_element(btn)
```

### React to UI changes (no polling)

```python
from desktop_harness import observe, get_value

def on_change(el, info):
    print("Note content:", get_value(el))

handle = observe("Notes", "AXValueChanged", on_change, scope="focused")
# ... do stuff ...
unobserve(handle)
```

### Window management

```python
from desktop_harness import maximize, tile_left, window_to_display

maximize("Safari")             # full screen
tile_left("Terminal")          # half screen
window_to_display("Slack", display=1)
```

### Record + replay

```python
from desktop_harness import Recorder

rec = Recorder()
rec.start()
# ... user clicks/types ...
rec.stop()
rec.to_python("/tmp/replay.py")  # generates a runnable script
```

### AppleScript escape hatch (when AX is sparse — e.g. Electron apps)

```python
from desktop_harness import tell

tell("Mail", '''
    set u to URL of selected message of message viewer 1
    return u
''')
```

## Domain skills

The repo ships with markdown recipes for the trickiest apps:

- [`safari.md`](agent-workspace/domain-skills/safari.md) — open URLs, run JS in the active tab, scrape the DOM
- [`messages.md`](agent-workspace/domain-skills/messages.md) — send iMessage, read history via chat.db
- [`calendar.md`](agent-workspace/domain-skills/calendar.md) — list events, create events, switch views
- [`vscode.md`](agent-workspace/domain-skills/vscode.md) — drive Electron via the command palette
- [`slack.md`](agent-workspace/domain-skills/slack.md) — Quick Switcher + DMs, OCR-based reading
- [`photos.md`](agent-workspace/domain-skills/photos.md) — search, export, switch tabs
- [`system_settings.md`](agent-workspace/domain-skills/system_settings.md) — open any pane via URL, toggle switches
- [`finder.md`](agent-workspace/domain-skills/finder.md), [`mail.md`](agent-workspace/domain-skills/mail.md), [`notes.md`](agent-workspace/domain-skills/notes.md), [`telegram.md`](agent-workspace/domain-skills/telegram.md)

Drop your own under `agent-workspace/domain-skills/<app>.md` — the project will index them.

## Caveats (read these once)

- **Electron apps** (Slack, Discord, VS Code, Notion) have sparse AX trees. Drive them via
  the command palette (`cmd+shift+p` etc.) or fall back to OCR + pixel clicks.
- **Per-app Automation** — first `tell("X")` against any new app triggers a one-time
  macOS dialog. `--doctor` only checks System Events; Finder, Mail, Notes etc. each need
  separate user approval the first time.
- **Don't auto-send.** When driving Mail / Messages / Slack, always preview the body and
  require user confirmation before pressing the send key. Ship with a kill-switch.
- **Permissions persist on the parent process.** If you launch from Terminal, Terminal needs
  the permissions, not Python. Switching shells (zsh → fish) doesn't reset them; switching
  terminal apps (Terminal → iTerm) does.

## Compared to alternatives

| Tool | Native AX | AppleScript | MCP server | OCR | Recorder | Notes |
|---|:-:|:-:|:-:|:-:|:-:|---|
| **desktop-harness** | ✅ | ✅ | ✅ | ✅ | ✅ | This project |
| Anthropic computer-use | — | — | ✅ | model | — | Pixel-only; cross-platform |
| `pyautogui` | — | — | — | — | — | Pure pixel clicks |
| `atomacos` | ✅ | — | — | — | — | AX library; no MCP, no AppleScript layer |
| `pynput` | — | — | — | — | ✅ | Input recording, no UI inspection |
| Hammerspoon | ✅ | ✅ | — | — | — | Lua, not Python; no MCP |

## Development

```bash
git clone https://github.com/Abhishekchhetri020/desktop-harness.git
cd desktop-harness
uv tool install -e . --with pytest --with pytest-timeout
pytest tests/                           # unit tests (no UI)
RUN_LIVE_TESTS=1 pytest tests/          # full suite incl. live UI tests
```

CI runs on `macos-latest` via GitHub Actions on every PR.

## Contributing

PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Especially looking for:
- Domain skills for apps not yet covered (Music, Reminders, Numbers, Pages, Keynote, ...)
- Window-snap presets (cmd-tilde behaviors, halve-quarter)
- Better Electron AX shimming
- Linux + Windows ports (different APIs, same MCP surface would be valuable)

## License

MIT. See [LICENSE](LICENSE).

## Credits

Built by [Abhishek Chhetri](https://github.com/Abhishekchhetri020) with [Claude Code](https://www.anthropic.com/claude-code).
