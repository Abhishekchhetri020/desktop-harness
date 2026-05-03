# Slack skill

Slack is Electron — AX tree is mostly empty. Use OCR to find UI, keystrokes
to drive it. No useful AppleScript dictionary.

## Send a message in the active channel

```python
activate("Slack")
key("cmd+k")                          # quick switcher (channel jump)
type_text("engineering"); key("return")
key("escape")                          # close any modal
# message composer is focused after channel switch
type_text("Hello from desktop-harness")
key("return")                          # ⚠️ this SENDS — confirm with user first
```

## Find the channel sidebar via OCR

```python
xy = find_text_on_screen("threads")
if xy: click_at(xy[0], xy[1])
```

## Read the last message (OCR the visible window)

```python
results = ocr_window("Slack")
texts = [r["text"] for r in results if r["confidence"] > 0.8]
print("\n".join(texts[-20:]))
```

## Mark all as read (cmd+shift+esc)

```python
activate("Slack"); key("cmd+shift+escape")
```

## DM a person

```python
activate("Slack"); key("cmd+shift+k")  # DM picker
type_text("alice"); key("return")
type_text("hi")  # DON'T press return — let user confirm
```

⚠️ Slack messages send on `return`. Always preview text before pressing it.
