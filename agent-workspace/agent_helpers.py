"""Workspace helpers — your accumulated, task-specific shortcuts.

Anything you define here is available unprefixed inside `desktop-harness -c "..."`.
Same pattern as browser-harness: the agent grows this file over time, one helper
per recurring workflow.

Examples to start with (uncomment / adapt as needed):

    def in_telegram(text):
        \"\"\"Type into the focused Telegram message field and send.\"\"\"
        activate("Telegram")
        time.sleep(0.4)
        el = find("Telegram", role="AXTextField") or find("Telegram", role="AXTextArea")
        if el is None:
            raise RuntimeError("could not find Telegram message field via AX tree")
        focus(el)
        type_text(text)
        key("return")

    def quick_note(body):
        \"\"\"Append a new note in Apple Notes via AppleScript.\"\"\"
        from datetime import datetime
        title = datetime.now().strftime("%Y-%m-%d %H:%M")
        return tell("Notes", f'make new note with properties {{name:"{title}", body:"{body}"}}')
"""
