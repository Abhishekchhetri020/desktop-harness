# desktop-harness

Drive any macOS desktop app from a CLI or LLM agent. AX-tree-aware, AppleScript-aware,
pixel-aware. Hackable, self-extending — same pattern as `browser-harness`, but for
the entire desktop.

## Why this exists

Anthropic's `computer-use` MCP is good but pixel-only and cross-platform — it doesn't
exploit macOS's biggest gift to automation: **the Accessibility tree** (AX), which is
the DOM equivalent for native apps. With AX you can find a button by `role="AXButton"`
and `title="Send"` and press it without ever knowing where it is on screen.

`desktop-harness` layers four capabilities so you always have the right tool:

| Layer | When to use |
|---|---|
| **AX tree** (`find`, `click_element`, `set_value`) | First choice for any AppKit app. Survives window moves, dark mode, font changes. |
| **AppleScript / JXA** (`tell`, `osascript`, `jxa`) | Apps with rich scripting dictionaries: Mail, Calendar, Notes, Music, Messages, Finder, Safari, Reminders. |
| **CGEvent** (`click_at`, `type_text`, `key`, `scroll`) | Low-level mouse/keyboard. Last-resort for apps with no AX/AppleScript surface. |
| **Vision OCR** (`ocr`, `find_text_on_screen`) | Read text from any pixels. Useful for Electron apps with sparse AX trees. |

## Install

```bash
cd ~/desktop-harness
uv tool install -e .
```

The CLI is `desktop-harness` (alias `dh`).

## Permissions

This requires three TCC grants. The first run will trigger the prompts; you can
also set them ahead of time:

1. **Accessibility** — System Settings → Privacy & Security → Accessibility → enable
   the parent terminal/IDE/Claude Code.
2. **Screen Recording** — same panel, Screen Recording section. Required for
   screenshots and OCR.
3. **Automation** — granted on first AppleScript that targets each app.

Check status anytime:

```bash
desktop-harness --doctor
```

## Quick start

```bash
# What's running?
desktop-harness --list-apps

# What's in front?
desktop-harness --frontmost

# Dump the AX tree of an app (great for exploration)
desktop-harness --ax "Notes" --ax-depth 4

# Take a screenshot
desktop-harness --screenshot /tmp/screen.png

# One-liner: open Notes, create a note via AppleScript
desktop-harness -c 'open_app("Notes"); tell("Notes", '"'"'make new note with properties {name:"hi", body:"from desktop-harness"}'"'"')'

# Find Notes' search field via AX, focus it, type
desktop-harness -c 'el = find("Notes", role="AXTextField"); focus(el); type_text("compliance")'

# OCR text on screen
desktop-harness -c 'print([r["text"] for r in ocr_window("Telegram")])'
```

## What's where

```
desktop-harness/
├── pyproject.toml
├── README.md
├── src/desktop_harness/
│   ├── apps.py            list_apps, frontmost, open_app, activate, quit_app, …
│   ├── input.py           click_at, double_click_at, type_text, key, scroll, drag, …
│   ├── screen.py          screenshot, screenshot_window, screenshot_region, displays
│   ├── ax.py              find, find_all, click_element, get_value, set_value,
│   │                       ax_tree, ax_dump, focus, focused_element, descendants
│   ├── applescript.py     osascript, osascript_app, tell, jxa
│   ├── ocr.py             ocr, ocr_region, ocr_window, find_text_on_screen
│   ├── permissions.py     check_accessibility, check_screen_recording, doctor_permissions
│   └── cli.py             desktop-harness CLI entry point
└── agent-workspace/
    ├── agent_helpers.py        # Empty by design — accumulate your shortcuts here.
    └── domain-skills/
        ├── notes.md            # AppleScript recipes
        ├── telegram.md
        ├── finder.md
        └── mail.md
```

## The `agent_helpers.py` pattern

Every helper you define in `agent-workspace/agent_helpers.py` is auto-imported into
the `-c` namespace. You build up a vocabulary specific to your workflows:

```python
# in agent_helpers.py
def post_to_telegram(text):
    activate("Telegram")
    time.sleep(0.4)
    el = find("Telegram", role="AXTextArea")
    focus(el)
    type_text(text)
    key("return")
```

```bash
desktop-harness -c 'post_to_telegram("hi")'
```

## Comparison vs Anthropic computer-use MCP

| | computer-use MCP | desktop-harness |
|---|---|---|
| Sees UI as | Pixels only | AX tree (structured) + screenshot fallback |
| Acts via | Pixel coords | Element handles (preferred) or pixel coords |
| Apple Mail / Calendar / Notes | Pixel-clicks like a human | AppleScript — instant, reliable |
| Cross-platform | macOS + Windows + Linux | macOS only |
| Self-extends | No | `agent_helpers.py` + `domain-skills/` |
| Permission model | Per-session app allowlist | TCC grants (one-time, OS-level) |
| Speed of click on a button by name | ~5-15s (screenshot loop) | ~50ms (AX action) |

`computer-use` is fine for a quick task or unknown surface. `desktop-harness` is
what you want once you're driving the same app repeatedly and care about reliability.

## License

MIT.
