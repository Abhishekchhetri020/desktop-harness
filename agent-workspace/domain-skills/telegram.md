# Telegram (macOS desktop app)

Telegram Desktop is an Electron-ish app — its AX tree is sparser than native AppKit
apps, but the message composer and chat list are reachable.

**Bot API or Telethon are still better paths** if you want headless automation.
Use this only when you specifically need the desktop client (e.g. acting as your
personal account in private chats).

## Send a message to the currently open chat

```python
activate("Telegram")
time.sleep(0.4)
# AX dump first if unsure: print(ax_dump("Telegram", max_depth=6))
el = find("Telegram", role="AXTextArea") or find("Telegram", role="AXTextField")
focus(el)
type_text("hello from desktop-harness")
key("return")
```

## Switch to a chat by name

```python
activate("Telegram")
key("cmd+k")  # opens Telegram's "Jump to" search
time.sleep(0.2)
type_text("Mum")
key("return")
```

## Read the latest visible message

Vision OCR is the easiest path because the message bubbles aren't reliably AX-typed:

```python
activate("Telegram")
results = ocr_window("Telegram")
last = results[-3:]   # rough: last few text blocks bottom-up
print(last)
```

## Common pitfalls

- **AX tree is shallow** — many bubbles render as `AXGroup` with nested `AXStaticText`.
  Use `ax_dump("Telegram", max_depth=8)` to explore.
- **Sending uses Enter** — but if "Send by Cmd-Enter" is on in settings, switch to
  `key("cmd+return")`.
- **Multi-line messages** — type the body, then `key("shift+return")` between paragraphs.
- **Composer focus is fragile** — clicking into the chat list can lose focus. Always
  re-focus the text area before typing.
