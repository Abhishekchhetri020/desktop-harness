"""Window management primitives — list, focus, move, resize, minimize, close.

Built on a hybrid:
  - CGWindowList for fast enumeration (works without AX permission for read-only)
  - AX (AXPosition / AXSize / AXMain / AXMinimized / AXClose) for control

Examples:

    from desktop_harness import windows as W

    W.list_windows()                                    # all on-screen windows
    W.list_windows("Safari")                            # just Safari's
    W.window_move("Safari", 100, 100)                   # top window of Safari
    W.window_resize("Safari", 1280, 800, index=0)
    W.window_minimize("Safari")
    W.window_to_display("Safari", display=1)            # send to second monitor
    W.tile_left("Safari")                               # halve the screen
    W.maximize("Safari")                                # full active screen
"""
from __future__ import annotations

from typing import Optional

from ApplicationServices import (
    AXUIElementSetAttributeValue,
    AXValueCreate,
    kAXErrorSuccess,
    kAXPositionAttribute,
    kAXSizeAttribute,
    kAXMinimizedAttribute,
    kAXMainAttribute,
    kAXFocusedAttribute,
    kAXValueCGPointType,
    kAXValueCGSizeType,
    kAXWindowsAttribute,
    kAXMainWindowAttribute,
    kAXFocusedWindowAttribute,
)
from Quartz import (
    CGPoint,
    CGSize,
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowListExcludeDesktopElements,
    kCGNullWindowID,
    kCGWindowOwnerName,
    kCGWindowName,
    kCGWindowNumber,
    kCGWindowBounds,
    kCGWindowLayer,
    kCGWindowOwnerPID,
)

from .ax import (
    app_ax,
    get_attr,
    children,
    AXError,
    perform_action,
)
from .apps import pid_of, activate
from .screen import displays


def list_windows(app_name: Optional[str] = None, *, on_screen: bool = True) -> list[dict]:
    """Enumerate windows on screen.

    If app_name is given, filter to that app. layer 0 = normal app windows;
    higher layers are menu bar items, dropdowns, status icons.
    """
    opts = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
    info = CGWindowListCopyWindowInfo(opts, kCGNullWindowID)
    out = []
    for w in info:
        owner = str(w.get(kCGWindowOwnerName, "") or "")
        if app_name is not None and owner.lower() != app_name.lower():
            continue
        b = w.get(kCGWindowBounds, {})
        out.append({
            "id": int(w.get(kCGWindowNumber, 0)),
            "owner": owner,
            "owner_pid": int(w.get(kCGWindowOwnerPID, 0)),
            "name": str(w.get(kCGWindowName, "") or ""),
            "x": int(b.get("X", 0)),
            "y": int(b.get("Y", 0)),
            "width": int(b.get("Width", 0)),
            "height": int(b.get("Height", 0)),
            "layer": int(w.get(kCGWindowLayer, 0)),
        })
    return out


def windows_of(app_name: str) -> list[object]:
    """Return AX window elements of an app."""
    app = app_ax(app_name)
    wins = get_attr(app, kAXWindowsAttribute) or []
    return list(wins)


def main_window(app_name: str) -> Optional[object]:
    """The app's main window (or first if none designated)."""
    app = app_ax(app_name)
    w = get_attr(app, kAXMainWindowAttribute)
    if w is not None:
        return w
    wins = windows_of(app_name)
    return wins[0] if wins else None


def focused_window(app_name: str) -> Optional[object]:
    app = app_ax(app_name)
    return get_attr(app, kAXFocusedWindowAttribute)


def _nth_window(app_name: str, index: int):
    wins = windows_of(app_name)
    if not wins:
        raise AXError(f"no windows for app {app_name!r}")
    if index >= len(wins):
        raise AXError(f"window index {index} out of range (have {len(wins)})")
    return wins[index]


def window_move(app_name: str, x: float, y: float, *, index: int = 0) -> bool:
    """Move a window to (x, y) in screen coords (top-left)."""
    win = _nth_window(app_name, index)
    pt = AXValueCreate(kAXValueCGPointType, CGPoint(x, y))
    err = AXUIElementSetAttributeValue(win, kAXPositionAttribute, pt)
    return err == kAXErrorSuccess


def window_resize(app_name: str, width: float, height: float, *, index: int = 0) -> bool:
    """Resize a window."""
    win = _nth_window(app_name, index)
    sz = AXValueCreate(kAXValueCGSizeType, CGSize(width, height))
    err = AXUIElementSetAttributeValue(win, kAXSizeAttribute, sz)
    return err == kAXErrorSuccess


def window_set_bounds(app_name: str, x: float, y: float, width: float, height: float, *, index: int = 0) -> bool:
    return window_move(app_name, x, y, index=index) and window_resize(app_name, width, height, index=index)


def window_minimize(app_name: str, *, index: int = 0, restore: bool = False) -> bool:
    """Minimize (or restore) a window."""
    win = _nth_window(app_name, index)
    err = AXUIElementSetAttributeValue(win, kAXMinimizedAttribute, not restore)
    return err == kAXErrorSuccess


def window_close(app_name: str, *, index: int = 0) -> bool:
    """Close a window via the close button.

    macOS doesn't expose AXClose directly; we walk to the AXCloseButton
    descendant and press it. Falls back to cmd+W if none found and the app
    is frontmost.
    """
    win = _nth_window(app_name, index)
    # Try to find the close button (subrole AXCloseButton) on the window.
    for ch in children(win):
        if get_attr(ch, "AXSubrole") == "AXCloseButton":
            return perform_action(ch, "AXPress")
    # Fallback: activate app + send cmd+W
    activate(app_name)
    from .input import key
    key("cmd+w")
    return True


def window_focus(app_name: str, *, index: int = 0) -> bool:
    """Bring a specific window of app forward and focus it."""
    activate(app_name)
    win = _nth_window(app_name, index)
    err = AXUIElementSetAttributeValue(win, kAXMainAttribute, True)
    if err != kAXErrorSuccess:
        return False
    AXUIElementSetAttributeValue(win, kAXFocusedAttribute, True)
    return True


def window_to_display(app_name: str, *, display: int = 0, index: int = 0) -> bool:
    """Move a window so its top-left is at the origin of the Nth display."""
    disps = displays()
    if display >= len(disps):
        raise ValueError(f"display index {display} out of range (have {len(disps)})")
    d = disps[display]
    return window_move(app_name, d["x"] + 40, d["y"] + 40, index=index)


def maximize(app_name: str, *, index: int = 0, display: int = 0) -> bool:
    """Resize to fill the active display (minus a small margin for the menu bar)."""
    disps = displays()
    d = disps[display]
    margin_top = 28 if d["y"] == 0 else 0  # rough menu bar inset
    return window_set_bounds(
        app_name, d["x"], d["y"] + margin_top, d["width"], d["height"] - margin_top, index=index,
    )


def tile_left(app_name: str, *, index: int = 0, display: int = 0) -> bool:
    disps = displays()
    d = disps[display]
    return window_set_bounds(app_name, d["x"], d["y"] + 28, d["width"] // 2, d["height"] - 28, index=index)


def tile_right(app_name: str, *, index: int = 0, display: int = 0) -> bool:
    disps = displays()
    d = disps[display]
    return window_set_bounds(
        app_name, d["x"] + d["width"] // 2, d["y"] + 28, d["width"] // 2, d["height"] - 28, index=index,
    )


def window_bounds(app_name: str, *, index: int = 0) -> Optional[dict]:
    """Get current (x, y, w, h) of an app window via AX (more accurate than CG)."""
    from .ax import position, size
    win = _nth_window(app_name, index)
    p = position(win)
    s = size(win)
    if p is None or s is None:
        return None
    return {"x": p[0], "y": p[1], "width": s[0], "height": s[1]}
