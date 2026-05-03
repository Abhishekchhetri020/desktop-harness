# Apple Mail

AppleScript dictionary covers compose, send, search, and per-account access.

## Compose a draft (don't send)

```python
tell("Mail", '''
    set msg to make new outgoing message with properties {
        subject: "Hello",
        content: "Body text",
        visible: true
    }
    tell msg
        make new to recipient at end of to recipients with properties {address:"someone@example.com"}
    end tell
''')
```

`visible:true` opens a window; the user can review/edit/send.

## Send (only after user explicit-approval — DON'T do this autonomously)

```python
tell("Mail", '''
    set msg to make new outgoing message with properties {
        subject:"Subj", content:"Body", visible:false
    }
    tell msg to make new to recipient at end of to recipients with properties {address:"x@y.com"}
    send msg
''')
```

## Search Inbox

```python
out = tell("Mail", '''
    set msgs to (messages of inbox whose subject contains "invoice")
    set out to ""
    repeat with m in msgs
        set out to out & subject of m & " | " & sender of m & "\n"
    end repeat
    return out
''')
print(out)
```

## Read latest email body

```python
body = tell("Mail", '''
    set m to first message of inbox
    return content of m
''')
```

## Reply to currently selected message

```python
tell("Mail", '''
    set sel to selection
    if sel is {} then return "no selection"
    set m to item 1 of sel
    set r to reply m with opening window
''')
```
