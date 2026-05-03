# Apple Notes

Notes has a rich AppleScript dictionary — almost always faster than driving the UI.

## Create a new note

```python
tell("Notes", '''
    make new note with properties {name:"Meeting prep", body:"<h1>Topics</h1><ul><li>Q3</li></ul>"}
''')
```

Body accepts a small subset of HTML (h1-h6, p, ul, ol, li, b, i).

## List recent notes

```python
out = tell("Notes", 'get name of every note of folder "Notes"')
# returns comma-separated string; split it
titles = [s.strip() for s in out.split(",")]
```

## Open a specific note by name

```python
tell("Notes", '''
    set theNote to first note whose name is "Meeting prep"
    show theNote
    activate
''')
```

## Append to an existing note (AppleScript can't append HTML; use text find/replace via JXA)

```python
jxa('''
    const Notes = Application("Notes");
    const n = Notes.notes.whose({name: "Meeting prep"})[0];
    n.body = n.body() + "<p>New line " + new Date().toISOString() + "</p>";
''')
```

## When AX is needed

If you want to drive the search bar (e.g. to find a note with full-text search instead
of by exact name), use AX:

```python
activate("Notes")
sb = find("Notes", role="AXTextField", placeholder="Search")
focus(sb)
type_text("compliance")
key("return")
```
