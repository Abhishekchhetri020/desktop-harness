# Photos skill

Apple Photos has a small AppleScript dictionary (search, export, get info)
and a moderate AX tree.

## Search

```python
activate("Photos")
key("cmd+f")
type_text("dog")
```

## Get all album names

```python
osascript_app("Photos", 'return name of every album')
```

## Export selected photos via AppleScript

```python
osascript('''
tell application "Photos"
    set selectedPhotos to selection
    export selectedPhotos to POSIX file "/tmp/photo-export"
end tell
''')
```

## Switch to Library / Albums / People via AX

```python
activate("Photos")
btn = find("Photos", role="AXRadioButton", title="Albums")
click_element(btn)
```
