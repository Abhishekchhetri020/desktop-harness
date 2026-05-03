# Calendar skill

Apple Calendar has a deep AppleScript dictionary. Prefer it over AX.

## List today's events

```python
osascript('''
tell application "Calendar"
    set today to current date
    set midnight to today - (time of today)
    set tomorrow to midnight + 1 * days
    set evs to every event of every calendar whose start date >= midnight and start date < tomorrow
    return evs
end tell
''')
```

## Create an event

```python
osascript('''
tell application "Calendar"
    tell calendar "Personal"
        make new event with properties {summary:"Stand-up", start date:date "Monday, May 5, 2026 9:00:00 AM", end date:date "Monday, May 5, 2026 9:30:00 AM"}
    end tell
end tell
''')
```

## Show an event in the UI

```python
osascript_app("Calendar", 'show event id "<event-id>"')
```

## Switch to month view via AX

```python
activate("Calendar")
btn = find("Calendar", role="AXButton", title="Month")
click_element(btn)
```
