# Finder

Finder has a great AppleScript dictionary. Use it for anything that touches files
or windows; AX only when you need to drive a specific dialog.

## Open a path

```python
tell("Finder", 'open POSIX file "/Users/abhishekchhetri/Downloads"')
```

## Reveal a single file

```python
tell("Finder", '''
    set f to POSIX file "/Users/abhishekchhetri/Downloads/test.pdf"
    reveal f
    activate
''')
```

## List selected items

```python
out = tell("Finder", 'get POSIX path of (selection as alias list)')
paths = [p.strip() for p in out.split(",")]
```

## Move files to Trash (safe — recoverable)

```python
tell("Finder", '''
    delete (POSIX file "/Users/abhishekchhetri/Downloads/old.pdf" as alias)
''')
```

## Search via Spotlight from Finder

```python
activate("Finder")
key("cmd+f")
type_text("kind:pdf modified:today")
```

## Show hidden files toggle

```python
key("cmd+shift+.")
```

## Empty trash (DESTRUCTIVE — don't run silently)

```python
tell("Finder", "empty trash")
```
