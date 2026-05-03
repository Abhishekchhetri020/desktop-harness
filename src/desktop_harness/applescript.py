"""AppleScript / JXA escape hatch.

Some apps expose powerful scripting dictionaries (Mail, Calendar, Notes, Music,
Messages, Finder, Safari, Reminders). For those, AppleScript is faster and more
reliable than walking the AX tree. This module is the bridge.
"""
from __future__ import annotations
import subprocess


def osascript(script: str, *, language: str | None = None, timeout: float = 30.0) -> str:
    """Run an osascript and return stdout. Raises RuntimeError on non-zero exit.
    Default language is AppleScript (osascript's default — pass language='JavaScript' for JXA)."""
    cmd = ["osascript"]
    if language:
        cmd += ["-l", language]
    cmd += ["-e", script]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"osascript failed ({r.returncode}): {r.stderr.strip()}")
    return r.stdout.rstrip("\n")


def jxa(script: str, *, timeout: float = 30.0) -> str:
    """Run JavaScript for Automation (JXA). Same surface as AppleScript but JS syntax."""
    return osascript(script, language="JavaScript", timeout=timeout)


def osascript_app(app_name: str, body: str, *, timeout: float = 30.0) -> str:
    """Wrap a body in `tell application "X" ... end tell` and run it."""
    script = f'tell application "{app_name}"\n{body}\nend tell'
    return osascript(script, timeout=timeout)


def tell(app_name: str, body: str, *, timeout: float = 30.0) -> str:
    """Alias for osascript_app — reads more naturally in scripts."""
    return osascript_app(app_name, body, timeout=timeout)


def type_via_se(text: str) -> None:
    """Type text via System Events `keystroke`.

    Use this for apps that ignore CGEventKeyboardSetUnicodeString — notably
    Telegram, Electron apps, and anything with custom input handling. Slower
    than CGEvent but more compatible. Sends to whatever has focus right now.
    """
    # Escape backslashes and double-quotes for embedding in the AppleScript string
    safe = text.replace("\\", "\\\\").replace('"', '\\"')
    osascript(f'tell application "System Events" to keystroke "{safe}"')


def key_via_se(combo: str) -> None:
    """Press a single key combo via System Events. Reliable when CGEvent isn't.
    Examples: 'return', 'cmd+a', 'cmd+shift+t', 'escape'."""
    parts = [p.strip().lower() for p in combo.split("+")]
    main = parts[-1]
    mods = parts[:-1]
    se_modmap = {
        "cmd": "command down", "command": "command down",
        "shift": "shift down",
        "alt": "option down", "option": "option down", "opt": "option down",
        "ctrl": "control down", "control": "control down",
    }
    se_keymap = {
        "return": 36, "enter": 36, "tab": 48, "space": 49, "escape": 53, "esc": 53,
        "delete": 51, "backspace": 51, "left": 123, "right": 124, "down": 125, "up": 126,
    }
    using = ""
    if mods:
        using = " using {" + ", ".join(se_modmap[m] for m in mods) + "}"
    if main in se_keymap:
        osascript(f'tell application "System Events" to key code {se_keymap[main]}{using}')
    elif len(main) == 1:
        safe_main = main.replace("\\", "\\\\").replace('"', '\\"')
        osascript(f'tell application "System Events" to keystroke "{safe_main}"{using}')
    else:
        raise ValueError(f"Unknown key for System Events: {main}")
