# Safari skill

Safari has a rich AppleScript dictionary AND a sparse AX tree (web content
isn't in the AX tree by default — only the chrome). Use AppleScript or JXA
to reach the DOM.

## Read the current URL + title

```python
osascript_app("Safari", 'return URL of current tab of front window')
osascript_app("Safari", 'return name of current tab of front window')
```

## Open a URL

```python
osascript_app("Safari", 'open location "https://example.com"')
# or via AX:
activate("Safari")
key("cmd+l")
type_text("example.com")
key("return")
```

## Run JS in the active tab (the killer feature)

```python
js = "document.title"
osascript_app("Safari", f'do JavaScript "{js}" in current tab of front window')

# Get all link hrefs:
js = 'Array.from(document.querySelectorAll("a")).slice(0,10).map(a => a.href).join("\\n")'
osascript_app("Safari", f'do JavaScript "{js}" in current tab of front window')
```

⚠️ "Allow JavaScript from Apple Events" must be enabled in
Safari → Develop → Allow JavaScript from Apple Events. The Develop menu
itself must be enabled in Safari → Settings → Advanced.

## Find a button on the page (DOM-aware click)

```python
js = '''
const btn = [...document.querySelectorAll("button")].find(b => b.innerText.includes("Sign in"));
if (btn) { const r = btn.getBoundingClientRect(); JSON.stringify({x: r.left + r.width/2, y: r.top + r.height/2}) }
else "null"
'''
out = osascript_app("Safari", f'do JavaScript "{js}" in current tab of front window')
import json; coords = json.loads(out)
# coords are page-relative; add the window content area offset to click.
```

## Tabs

```python
osascript_app("Safari", 'set name of every tab of front window to "x"')  # smoke test
osascript_app("Safari", 'tell front window to make new tab')
osascript_app("Safari", 'close current tab of front window')
```
