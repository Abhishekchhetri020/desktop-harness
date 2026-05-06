"""Notes.app adapter — create / search / read notes via AppleScript."""
from __future__ import annotations

from typing import Optional

from .base import Adapter


def _escape_as(s: str) -> str:
    """AppleScript string escape — quotes + backslashes."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


class NotesAdapter(Adapter):
    name = "Notes"
    bundle_ids = ("com.apple.Notes",)
    app_class = "applescript"
    safe_actions = (
        "list_folders", "list_notes", "search_notes",
        "read_selected_note", "current_note_title",
    )
    dangerous_actions = (
        "create_note", "append_to_note", "delete_note",
    )

    def do_list_folders(self) -> dict:
        from ..applescript import osascript
        try:
            out = osascript(
                'tell application "Notes"\n'
                '  set names to ""\n'
                '  repeat with f in folders\n'
                '    set names to names & (name of f) & linefeed\n'
                '  end repeat\n'
                '  return names\n'
                'end tell'
            )
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "action": "list_folders",
                "folders": [n for n in (out or "").splitlines() if n.strip()]}

    def do_list_notes(self, folder: Optional[str] = None, limit: int = 50) -> dict:
        from ..applescript import osascript
        folder_filter = f'in folder "{_escape_as(folder)}"' if folder else ""
        script = (
            'tell application "Notes"\n'
            '  set out to ""\n'
            f'  set theNotes to notes {folder_filter}\n'
            f'  set N to (count of theNotes)\n'
            f'  if N > {limit} then set N to {limit}\n'
            '  repeat with i from 1 to N\n'
            '    set t to name of (item i of theNotes)\n'
            '    set out to out & t & linefeed\n'
            '  end repeat\n'
            '  return out\n'
            'end tell'
        )
        try:
            out = osascript(script)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "action": "list_notes",
                "folder": folder, "titles": [n for n in (out or "").splitlines() if n.strip()]}

    def do_search_notes(self, query: str, limit: int = 20) -> dict:
        from ..applescript import osascript
        q = _escape_as(query)
        script = (
            'tell application "Notes"\n'
            f'  set theMatches to (notes whose name contains "{q}" or body contains "{q}")\n'
            '  set out to ""\n'
            f'  set N to (count of theMatches)\n'
            f'  if N > {limit} then set N to {limit}\n'
            '  repeat with i from 1 to N\n'
            '    set t to name of (item i of theMatches)\n'
            '    set out to out & t & linefeed\n'
            '  end repeat\n'
            '  return out\n'
            'end tell'
        )
        try:
            out = osascript(script)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "action": "search_notes", "query": query,
                "titles": [n for n in (out or "").splitlines() if n.strip()]}

    def do_read_selected_note(self) -> dict:
        from ..applescript import osascript
        try:
            out = osascript(
                'tell application "Notes" to get body of selection as string'
            )
        except Exception as e:
            return {"ok": False, "error": str(e),
                    "hint": "Notes must be frontmost with a note selected."}
        return {"ok": True, "action": "read_selected_note", "body": out or ""}

    def do_current_note_title(self) -> dict:
        from ..applescript import osascript
        try:
            out = osascript('tell application "Notes" to get name of selection as string')
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "action": "current_note_title", "title": (out or "").strip()}

    # ----- dangerous-ish (creates content) -----

    def do_create_note(
        self,
        title: str,
        body: str = "",
        folder: Optional[str] = None,
        *,
        confirm: bool = False,
        dry_run: bool = False,
    ) -> dict:
        from ..safety import confirmed_action

        def _create():
            from ..applescript import osascript
            t = _escape_as(title)
            # Notes.body wants HTML — convert newlines to <br>.
            body_html = body.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")
            b = f"<h1>{t}</h1><div>{body_html}</div>"
            if folder:
                f = _escape_as(folder)
                script = (
                    'tell application "Notes"\n'
                    f'  set theFolder to folder "{f}"\n'
                    f'  make new note at theFolder with properties {{name:"{t}", body:"{b}"}}\n'
                    'end tell'
                )
            else:
                script = (
                    'tell application "Notes"\n'
                    f'  make new note with properties {{name:"{t}", body:"{b}"}}\n'
                    'end tell'
                )
            osascript(script)
            return {"title": title, "folder": folder, "body_chars": len(body)}

        # create_note isn't dangerous in itself, but it WRITES — caution.
        return confirmed_action(
            "create_note", _create,
            confirm=True, dry_run=dry_run, target=title, app="Notes",
        )

    def do_append_to_note(self, title: str, body_to_add: str, *,
                          confirm: bool = False, dry_run: bool = False) -> dict:
        from ..safety import confirmed_action

        def _append():
            from ..applescript import osascript
            t = _escape_as(title)
            extra = body_to_add.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")
            script = (
                'tell application "Notes"\n'
                f'  set theNote to first note whose name is "{t}"\n'
                f'  set body of theNote to (body of theNote) & "<br>{extra}"\n'
                'end tell'
            )
            osascript(script)
            return {"title": title, "added_chars": len(body_to_add)}

        return confirmed_action(
            "append_to_note", _append,
            confirm=True, dry_run=dry_run, target=title, app="Notes",
        )

    def do_delete_note(self, title: str, *, confirm: bool = False, dry_run: bool = False) -> dict:
        from ..safety import confirmed_action

        def _delete():
            from ..applescript import osascript
            t = _escape_as(title)
            osascript(
                'tell application "Notes" to delete '
                f'(first note whose name is "{t}")'
            )
            return {"title": title}

        return confirmed_action(
            "delete_note", _delete,
            confirm=confirm, dry_run=dry_run, target=title, app="Notes",
        )
