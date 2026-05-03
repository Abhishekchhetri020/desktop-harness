"""Screenshots via CoreGraphics. Full screen, window, region. PNG output."""
from __future__ import annotations
import os
import tempfile
from typing import Optional

from Quartz import (
    CGWindowListCreateImage,
    CGWindowListCopyWindowInfo,
    CGRectMake,
    CGRectInfinite,
    CGMainDisplayID,
    CGDisplayBounds,
    CGGetActiveDisplayList,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowListOptionIncludingWindow,
    kCGWindowListExcludeDesktopElements,
    kCGNullWindowID,
    kCGWindowImageDefault,
    kCGWindowImageBoundsIgnoreFraming,
    kCGWindowName,
    kCGWindowOwnerName,
    kCGWindowNumber,
    kCGWindowBounds,
)
from Quartz.CoreGraphics import CGImageGetWidth, CGImageGetHeight
from AppKit import NSBitmapImageRep, NSPNGFileType


def displays() -> list[dict]:
    """All attached displays."""
    err, ids, count = CGGetActiveDisplayList(16, None, None)
    out = []
    for did in ids[:count]:
        b = CGDisplayBounds(did)
        out.append({
            "id": int(did),
            "x": int(b.origin.x), "y": int(b.origin.y),
            "width": int(b.size.width), "height": int(b.size.height),
            "main": bool(did == CGMainDisplayID()),
        })
    return out


def main_display_size() -> tuple[int, int]:
    b = CGDisplayBounds(CGMainDisplayID())
    return int(b.size.width), int(b.size.height)


def save_image(cg_image, path: str) -> str:
    """Save a CGImage to PNG."""
    bitmap = NSBitmapImageRep.alloc().initWithCGImage_(cg_image)
    data = bitmap.representationUsingType_properties_(NSPNGFileType, None)
    data.writeToFile_atomically_(path, True)
    return path


def screenshot(path: str | None = None) -> str:
    """Capture the entire screen. Returns saved PNG path."""
    image = CGWindowListCreateImage(
        CGRectInfinite,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowImageDefault,
    )
    if image is None:
        raise RuntimeError("screenshot failed — Screen Recording permission?")
    if path is None:
        fd, path = tempfile.mkstemp(suffix=".png", prefix="dh-screen-")
        os.close(fd)
    return save_image(image, path)


def screenshot_region(x: int, y: int, w: int, h: int, path: str | None = None) -> str:
    rect = CGRectMake(x, y, w, h)
    image = CGWindowListCreateImage(
        rect, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, kCGWindowImageDefault,
    )
    if image is None:
        raise RuntimeError("screenshot_region failed — Screen Recording permission?")
    if path is None:
        fd, path = tempfile.mkstemp(suffix=".png", prefix="dh-region-")
        os.close(fd)
    return save_image(image, path)


def _windows_of(app_name: str) -> list[dict]:
    info = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
        kCGNullWindowID,
    )
    out = []
    for w in info:
        owner = str(w.get(kCGWindowOwnerName, "") or "")
        if owner.lower() == app_name.lower():
            b = w.get(kCGWindowBounds, {})
            out.append({
                "id": int(w.get(kCGWindowNumber, 0)),
                "owner": owner,
                "name": str(w.get(kCGWindowName, "") or ""),
                "x": int(b.get("X", 0)), "y": int(b.get("Y", 0)),
                "width": int(b.get("Width", 0)), "height": int(b.get("Height", 0)),
            })
    return out


def screenshot_window(app_name: str, *, index: int = 0, path: str | None = None) -> str:
    """Screenshot a specific window of an app (by index in window list)."""
    wins = _windows_of(app_name)
    if not wins:
        raise RuntimeError(f"no windows for app {app_name!r}")
    win = wins[index]
    image = CGWindowListCreateImage(
        CGRectMake(win["x"], win["y"], win["width"], win["height"]),
        kCGWindowListOptionIncludingWindow,
        win["id"],
        kCGWindowImageBoundsIgnoreFraming,
    )
    if image is None:
        raise RuntimeError("screenshot_window failed — Screen Recording permission?")
    if path is None:
        fd, path = tempfile.mkstemp(suffix=".png", prefix=f"dh-{app_name}-")
        os.close(fd)
    return save_image(image, path)
