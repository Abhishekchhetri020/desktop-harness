# Messages (iMessage) skill

The Messages app has a constrained AppleScript surface and a sparse AX tree
(it's heavily Catalyst). Sending works; reading history requires Full Disk
Access to chat.db.

## Send to a phone or Apple ID

```python
osascript('''
tell application "Messages"
    set targetService to 1st service whose service type = iMessage
    set targetBuddy to buddy "+15551234567" of targetService
    send "Hello from desktop-harness" to targetBuddy
end tell
''')
```

## Send to an existing chat by name

```python
osascript('''
tell application "Messages"
    set theChat to (1st chat whose name = "Family")
    send "Dinner at 7?" to theChat
end tell
''')
```

## Read recent messages (requires Full Disk Access)

Direct sqlite3 query against `~/Library/Messages/chat.db`. Don't use
AppleScript — the dictionary doesn't expose history.

```python
import sqlite3
con = sqlite3.connect("/Users/$USER/Library/Messages/chat.db")
rows = con.execute("""
    SELECT datetime(date/1000000000 + 978307200, 'unixepoch', 'localtime'),
           handle.id, message.text
    FROM message LEFT JOIN handle ON message.handle_id = handle.ROWID
    WHERE message.text IS NOT NULL
    ORDER BY message.date DESC LIMIT 20
""").fetchall()
```

## Compose UI via AX (when AppleScript routes fail)

```python
activate("Messages")
key("cmd+n")  # new message
# Recipient field
recipient = find("Messages", role="AXTextField", placeholder="To:")
focus(recipient); type_text("Mom")
key("return")
# Body field
body = find("Messages", role="AXTextArea")
focus(body); type_text("Sample"); key("return")
```

⚠️ Do NOT auto-send. Always preview the body and require user confirmation
before pressing return.
