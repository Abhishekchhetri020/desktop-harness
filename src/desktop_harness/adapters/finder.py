"""Finder adapter — folder navigation, reveal, selection, safe file ops."""
from __future__ import annotations

import os
from typing import Optional

from .base import Adapter


class FinderAdapter(Adapter):
    name = "Finder"
    bundle_ids = ("com.apple.finder",)
    app_class = "applescript"
    safe_actions = (
        "open_folder", "reveal", "selected_items", "copy_selected_paths",
        "current_folder", "front_window_path",
    )
    dangerous_actions = (
        "create_folder", "move_to_trash", "rename",
    )

    # ----- safe -----

    def do_open_folder(self, path: str) -> dict:
        path = os.path.expanduser(path)
        if not os.path.isdir(path):
            return {"ok": False, "error": f"not a directory: {path}",
                    "hint": "Pass an absolute or ~-relative path that exists."}
        from ..applescript import osascript
        osascript(f'tell application "Finder" to open POSIX file "{path}"')
        from ..apps import activate
        try: activate("Finder")
        except Exception: pass
        return {"ok": True, "action": "open_folder", "path": path}

    def do_reveal(self, path: str) -> dict:
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return {"ok": False, "error": f"path not found: {path}", "hint": "Verify the path."}
        import subprocess
        subprocess.run(["open", "-R", path], check=False, timeout=5)
        return {"ok": True, "action": "reveal", "path": path}

    def do_selected_items(self) -> dict:
        from ..applescript import osascript
        # Returns POSIX paths separated by newlines.
        try:
            out = osascript(
                'tell application "Finder" to set theSel to selection\n'
                'set thePaths to ""\n'
                'repeat with anItem in theSel\n'
                '  set thePaths to thePaths & POSIX path of (anItem as alias) & linefeed\n'
                'end repeat\n'
                'return thePaths'
            )
        except Exception as e:
            return {"ok": False, "error": str(e),
                    "hint": "Grant Automation permission to control Finder."}
        paths = [p for p in (out or "").splitlines() if p.strip()]
        return {"ok": True, "action": "selected_items", "paths": paths, "count": len(paths)}

    def do_copy_selected_paths(self, separator: str = "\n") -> dict:
        sel = self.do_selected_items()
        if not sel.get("ok"):
            return sel
        text = separator.join(sel["paths"])
        from ..applescript import osascript
        # Set clipboard via shell to avoid AppleScript escape headaches.
        import subprocess
        subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
        return {"ok": True, "action": "copy_selected_paths",
                "count": len(sel["paths"]), "preview": text[:200]}

    def do_current_folder(self) -> dict:
        return self.do_front_window_path()

    def do_front_window_path(self) -> dict:
        from ..applescript import osascript
        try:
            out = osascript(
                'tell application "Finder"\n'
                '  if (count of windows) is 0 then return ""\n'
                '  try\n'
                '    return POSIX path of (target of front window as alias)\n'
                '  on error\n'
                '    return ""\n'
                '  end try\n'
                'end tell'
            )
        except Exception as e:
            return {"ok": False, "error": str(e)}
        path = (out or "").strip()
        if not path:
            return {"ok": False, "error": "no Finder window open"}
        return {"ok": True, "action": "front_window_path", "path": path}

    # ----- dangerous -----

    def do_create_folder(self, path: str, *, confirm: bool = False, dry_run: bool = False) -> dict:
        from ..safety import confirmed_action
        target = os.path.expanduser(path)

        def _make():
            os.makedirs(target, exist_ok=False)
            return target

        return confirmed_action(
            "create_folder", _make,
            confirm=confirm, dry_run=dry_run, target=target, app="Finder",
        )

    def do_move_to_trash(self, path: str, *, confirm: bool = False, dry_run: bool = False) -> dict:
        from ..safety import confirmed_action
        target = os.path.expanduser(path)

        def _trash():
            from ..applescript import osascript
            return osascript(
                f'tell application "Finder" to delete POSIX file "{target}"'
            )

        return confirmed_action(
            "move_to_trash", _trash,
            confirm=confirm, dry_run=dry_run, target=target, app="Finder",
        )

    def do_rename(self, path: str, new_name: str, *, confirm: bool = False,
                  dry_run: bool = False) -> dict:
        from ..safety import confirmed_action
        target = os.path.expanduser(path)

        def _rename():
            new_path = os.path.join(os.path.dirname(target), new_name)
            os.rename(target, new_path)
            return new_path

        return confirmed_action(
            "rename", _rename,
            confirm=confirm, dry_run=dry_run, target=target, app="Finder",
        )
