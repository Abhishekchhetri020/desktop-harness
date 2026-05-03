"""MCP server — exposes desktop-harness as Model Context Protocol tools.

Run with:  desktop-harness mcp                (stdio transport, MCP standard)

Add to Claude Code:
    claude mcp add desktop-harness -- desktop-harness mcp

Add to Hermes (~/.hermes/config.yaml):
    mcp_servers:
      desktop-harness:
        command: desktop-harness
        args: [mcp]

Add to Codex (~/.codex/config.toml):
    [mcp_servers.desktop-harness]
    command = "desktop-harness"
    args = ["mcp"]

Add to Gemini CLI (~/.gemini/settings.json):
    {"mcpServers": {"desktop-harness": {"command": "desktop-harness", "args": ["mcp"]}}}

Tools exposed (40+):
  apps:        list_apps, frontmost, open_app, activate_app, quit_app, app_info, is_running
  windows:     list_windows, window_focus, window_move, window_resize, window_minimize,
               window_close, window_to_display, maximize, tile_left, tile_right, window_bounds
  ax:          ax_find, ax_find_all, ax_click, ax_get_value, ax_set_value, ax_perform,
               ax_dump, ax_focused, ax_focus
  input:       click, double_click, right_click, type_text, key_press, scroll, drag, mouse_move
  screen:      screenshot, screenshot_window, screenshot_region, displays
  applescript: osascript, osascript_app, jxa
  ocr:         ocr_image, ocr_region, ocr_window, find_text_on_screen
  observers:   observe_app, list_observers, stop_observer, stop_all_observers, wait_for_event
  permissions: doctor, request_accessibility
  meta:        version

Hand-rolled JSON-RPC (no external mcp SDK) so it runs anywhere pyobjc does.
Spec: https://spec.modelcontextprotocol.io/specification/2025-06-18/
"""
from __future__ import annotations

import base64
import json
import logging
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

from . import __version__

# stderr-only logging — stdout is reserved for JSON-RPC.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
log = logging.getLogger("desktop_harness.mcp")


SUPPORTED_PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"]


# --- tool registry ---------------------------------------------------------


TOOLS: dict[str, dict] = {}


def tool(name: str, description: str, schema: dict | None = None):
    """Decorator: register a function as an MCP tool."""
    def deco(fn: Callable):
        TOOLS[name] = {
            "description": description.strip(),
            "input_schema": schema or {"type": "object", "properties": {}},
            "handler": fn,
        }
        return fn
    return deco


# --- helpers ---------------------------------------------------------------


def _ok(data: Any) -> dict:
    return {"ok": True, "result": data}


def _err(msg: str, *, hint: str = "") -> dict:
    out = {"ok": False, "error": msg}
    if hint:
        out["hint"] = hint
    return out


def _ax_pid_or_err(name: str):
    from .apps import pid_of
    p = pid_of(name)
    if p is None:
        return None, _err(f"app not running: {name!r}", hint="Call open_app first.")
    return p, None


def _save_image_to_temp(suffix: str = ".png") -> str:
    fd, p = tempfile.mkstemp(suffix=suffix, prefix="dh-mcp-")
    import os
    os.close(fd)
    return p


def _b64_image(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


# --- apps ------------------------------------------------------------------


@tool("list_apps", "List every running macOS app. Returns name, bundle_id, pid, active, hidden.")
def t_list_apps():
    from .apps import list_apps
    return _ok(list_apps())


@tool(
    "frontmost",
    "Return the app currently in front (the one whose menu bar is showing).",
)
def t_frontmost():
    from .apps import frontmost
    return _ok(frontmost())


@tool(
    "open_app",
    "Launch an app by name or full path, or activate it if already running. Waits ~1.5s.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def t_open_app(name: str):
    from .apps import open_app
    return _ok(open_app(name))


@tool(
    "activate_app",
    "Bring an already-running app to the front.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def t_activate_app(name: str):
    from .apps import activate
    return _ok({"activated": activate(name)})


@tool(
    "quit_app",
    "Quit an app gracefully (or pass force=true for SIGKILL).",
    {"type": "object", "properties": {"name": {"type": "string"}, "force": {"type": "boolean"}}, "required": ["name"]},
)
def t_quit_app(name: str, force: bool = False):
    from .apps import quit_app
    return _ok({"quit": quit_app(name, force=force)})


@tool(
    "app_info",
    "Detailed info about a running app: name, bundle_id, pid, path.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def t_app_info(name: str):
    from .apps import app_info
    info = app_info(name)
    if info is None:
        return _err(f"app not running: {name!r}")
    return _ok(info)


@tool(
    "is_running",
    "Check if an app is currently running.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
)
def t_is_running(name: str):
    from .apps import is_running
    return _ok({"running": is_running(name)})


# --- windows ---------------------------------------------------------------


@tool(
    "list_windows",
    "List on-screen windows. Optionally filter by app name.",
    {"type": "object", "properties": {"app": {"type": "string"}}},
)
def t_list_windows(app: str | None = None):
    from .windows import list_windows
    return _ok(list_windows(app))


@tool(
    "window_focus",
    "Bring window N of an app to the front and focus it.",
    {"type": "object", "properties": {"app": {"type": "string"}, "index": {"type": "integer"}}, "required": ["app"]},
)
def t_window_focus(app: str, index: int = 0):
    from .windows import window_focus
    return _ok({"focused": window_focus(app, index=index)})


@tool(
    "window_move",
    "Move window N of an app to (x, y) in screen coords.",
    {"type": "object", "properties": {
        "app": {"type": "string"}, "x": {"type": "number"}, "y": {"type": "number"},
        "index": {"type": "integer"},
    }, "required": ["app", "x", "y"]},
)
def t_window_move(app: str, x: float, y: float, index: int = 0):
    from .windows import window_move
    return _ok({"moved": window_move(app, x, y, index=index)})


@tool(
    "window_resize",
    "Resize window N of an app to (width, height).",
    {"type": "object", "properties": {
        "app": {"type": "string"}, "width": {"type": "number"}, "height": {"type": "number"},
        "index": {"type": "integer"},
    }, "required": ["app", "width", "height"]},
)
def t_window_resize(app: str, width: float, height: float, index: int = 0):
    from .windows import window_resize
    return _ok({"resized": window_resize(app, width, height, index=index)})


@tool(
    "window_minimize",
    "Minimize window N of an app (or restore via restore=true).",
    {"type": "object", "properties": {"app": {"type": "string"}, "index": {"type": "integer"}, "restore": {"type": "boolean"}}, "required": ["app"]},
)
def t_window_minimize(app: str, index: int = 0, restore: bool = False):
    from .windows import window_minimize
    return _ok({"ok": window_minimize(app, index=index, restore=restore)})


@tool(
    "window_close",
    "Close window N of an app (presses its close button, or cmd+W as fallback).",
    {"type": "object", "properties": {"app": {"type": "string"}, "index": {"type": "integer"}}, "required": ["app"]},
)
def t_window_close(app: str, index: int = 0):
    from .windows import window_close
    return _ok({"closed": window_close(app, index=index)})


@tool(
    "maximize",
    "Resize an app's window to fill the active display.",
    {"type": "object", "properties": {"app": {"type": "string"}, "index": {"type": "integer"}, "display": {"type": "integer"}}, "required": ["app"]},
)
def t_maximize(app: str, index: int = 0, display: int = 0):
    from .windows import maximize
    return _ok({"maximized": maximize(app, index=index, display=display)})


@tool(
    "tile_left",
    "Tile a window to the left half of a display.",
    {"type": "object", "properties": {"app": {"type": "string"}, "index": {"type": "integer"}, "display": {"type": "integer"}}, "required": ["app"]},
)
def t_tile_left(app: str, index: int = 0, display: int = 0):
    from .windows import tile_left
    return _ok({"tiled": tile_left(app, index=index, display=display)})


@tool(
    "tile_right",
    "Tile a window to the right half of a display.",
    {"type": "object", "properties": {"app": {"type": "string"}, "index": {"type": "integer"}, "display": {"type": "integer"}}, "required": ["app"]},
)
def t_tile_right(app: str, index: int = 0, display: int = 0):
    from .windows import tile_right
    return _ok({"tiled": tile_right(app, index=index, display=display)})


@tool(
    "window_bounds",
    "Current (x, y, width, height) of an app window via AX.",
    {"type": "object", "properties": {"app": {"type": "string"}, "index": {"type": "integer"}}, "required": ["app"]},
)
def t_window_bounds(app: str, index: int = 0):
    from .windows import window_bounds
    return _ok(window_bounds(app, index=index))


@tool(
    "window_to_display",
    "Move an app window to the origin of display N.",
    {"type": "object", "properties": {"app": {"type": "string"}, "display": {"type": "integer"}, "index": {"type": "integer"}}, "required": ["app"]},
)
def t_window_to_display(app: str, display: int = 0, index: int = 0):
    from .windows import window_to_display
    return _ok({"moved": window_to_display(app, display=display, index=index)})


# --- AX --------------------------------------------------------------------


_AX_REFS: dict[str, object] = {}
_AX_REF_CTR = 0
_AX_LOCK = threading.Lock()


def _ax_store(el) -> str:
    global _AX_REF_CTR
    with _AX_LOCK:
        _AX_REF_CTR += 1
        ref = f"ax_{_AX_REF_CTR}"
        _AX_REFS[ref] = el
        return ref


def _ax_get(ref: str):
    return _AX_REFS.get(ref)


def _ax_describe(el) -> dict:
    from .ax import get_attr
    return {
        "role": str(get_attr(el, "AXRole") or "") or None,
        "subrole": str(get_attr(el, "AXSubrole") or "") or None,
        "title": str(get_attr(el, "AXTitle") or "") or None,
        "value": (str(get_attr(el, "AXValue") or "")[:200] or None),
        "identifier": str(get_attr(el, "AXIdentifier") or "") or None,
        "enabled": bool(get_attr(el, "AXEnabled") or False),
    }


@tool(
    "ax_find",
    "Find ONE element in an app's AX tree by role/title/value/identifier filters. "
    "Returns a handle ref + descriptor. Use the ref in ax_click/ax_get_value/etc.",
    {"type": "object", "properties": {
        "app": {"type": "string"},
        "role": {"type": "string"},
        "title": {"type": "string"},
        "title_contains": {"type": "string"},
        "value": {"type": "string"},
        "value_contains": {"type": "string"},
        "identifier": {"type": "string"},
        "subrole": {"type": "string"},
        "max_depth": {"type": "integer"},
    }, "required": ["app"]},
)
def t_ax_find(app: str, **filters):
    from .ax import find
    el = find(app, **{k: v for k, v in filters.items() if v is not None})
    if el is None:
        return _err("not found", hint="Try ax_dump to see the live tree, or relax filters.")
    return _ok({"ref": _ax_store(el), **_ax_describe(el)})


@tool(
    "ax_find_all",
    "Find ALL elements matching filters (default limit 100).",
    {"type": "object", "properties": {
        "app": {"type": "string"},
        "role": {"type": "string"}, "title_contains": {"type": "string"},
        "limit": {"type": "integer"}, "max_depth": {"type": "integer"},
    }, "required": ["app"]},
)
def t_ax_find_all(app: str, limit: int = 100, **filters):
    from .ax import find_all
    els = find_all(app, limit=limit, **{k: v for k, v in filters.items() if v is not None})
    return _ok([{"ref": _ax_store(e), **_ax_describe(e)} for e in els])


@tool(
    "ax_click",
    "Press an AX element (no pixel coords). Pass the ref returned by ax_find.",
    {"type": "object", "properties": {"ref": {"type": "string"}}, "required": ["ref"]},
)
def t_ax_click(ref: str):
    from .ax import click_element
    el = _ax_get(ref)
    if el is None:
        return _err(f"unknown ref: {ref}")
    return _ok({"clicked": click_element(el)})


@tool(
    "ax_get_value",
    "Read the AXValue of an element (text content, slider value, etc).",
    {"type": "object", "properties": {"ref": {"type": "string"}}, "required": ["ref"]},
)
def t_ax_get_value(ref: str):
    from .ax import get_value
    el = _ax_get(ref)
    if el is None:
        return _err(f"unknown ref: {ref}")
    return _ok({"value": get_value(el)})


@tool(
    "ax_set_value",
    "Set the AXValue of an element (text fields, sliders).",
    {"type": "object", "properties": {"ref": {"type": "string"}, "value": {}}, "required": ["ref", "value"]},
)
def t_ax_set_value(ref: str, value):
    from .ax import set_value
    el = _ax_get(ref)
    if el is None:
        return _err(f"unknown ref: {ref}")
    return _ok({"set": set_value(el, value)})


@tool(
    "ax_perform",
    "Perform an arbitrary AX action (AXPress, AXShowMenu, AXIncrement, AXDecrement, AXConfirm, AXCancel).",
    {"type": "object", "properties": {"ref": {"type": "string"}, "action": {"type": "string"}}, "required": ["ref", "action"]},
)
def t_ax_perform(ref: str, action: str):
    from .ax import perform_action
    el = _ax_get(ref)
    if el is None:
        return _err(f"unknown ref: {ref}")
    return _ok({"performed": perform_action(el, action)})


@tool(
    "ax_dump",
    "Pretty-print an app's AX tree as text. Useful for discovering filters.",
    {"type": "object", "properties": {"app": {"type": "string"}, "max_depth": {"type": "integer"}}, "required": ["app"]},
)
def t_ax_dump(app: str, max_depth: int = 6):
    from .ax import ax_dump
    return _ok({"tree": ax_dump(app, max_depth=max_depth)})


@tool(
    "ax_focused",
    "Return the element currently focused, system-wide, with descriptor + ref.",
)
def t_ax_focused():
    from .ax import focused_element
    el = focused_element()
    if el is None:
        return _err("nothing focused")
    return _ok({"ref": _ax_store(el), **_ax_describe(el)})


@tool(
    "ax_focus",
    "Give keyboard focus to an AX element.",
    {"type": "object", "properties": {"ref": {"type": "string"}}, "required": ["ref"]},
)
def t_ax_focus(ref: str):
    from .ax import focus
    el = _ax_get(ref)
    if el is None:
        return _err(f"unknown ref: {ref}")
    return _ok({"focused": focus(el)})


# --- input -----------------------------------------------------------------


@tool(
    "click",
    "Click at screen coords (left button, single-click).",
    {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]},
)
def t_click(x: float, y: float):
    from .input import click_at
    click_at(x, y)
    return _ok({"clicked_at": [x, y]})


@tool(
    "double_click",
    "Double-click at screen coords.",
    {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]},
)
def t_double_click(x: float, y: float):
    from .input import double_click_at
    double_click_at(x, y)
    return _ok({"double_clicked_at": [x, y]})


@tool(
    "right_click",
    "Right-click at screen coords.",
    {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]},
)
def t_right_click(x: float, y: float):
    from .input import right_click_at
    right_click_at(x, y)
    return _ok({"right_clicked_at": [x, y]})


@tool(
    "type_text",
    "Type a string at the current keyboard focus (Unicode-clean — works for emoji/CJK).",
    {"type": "object", "properties": {"text": {"type": "string"}, "delay": {"type": "number"}}, "required": ["text"]},
)
def t_type_text(text: str, delay: float = 0.005):
    from .input import type_text
    type_text(text, delay=delay)
    return _ok({"typed": len(text)})


@tool(
    "key_press",
    "Press a key or chord, e.g. 'cmd+a', 'return', 'cmd+shift+t'.",
    {"type": "object", "properties": {"chord": {"type": "string"}, "count": {"type": "integer"}}, "required": ["chord"]},
)
def t_key_press(chord: str, count: int = 1):
    from .input import key
    key(chord, count=count)
    return _ok({"pressed": chord, "count": count})


@tool(
    "scroll",
    "Scroll by dy (vertical) and dx (horizontal). Positive dy = scroll down.",
    {"type": "object", "properties": {
        "dy": {"type": "integer"}, "dx": {"type": "integer"},
        "x": {"type": "number"}, "y": {"type": "number"},
    }},
)
def t_scroll(dy: int = 0, dx: int = 0, x: float | None = None, y: float | None = None):
    from .input import scroll
    scroll(dy=dy, dx=dx, x=x, y=y)
    return _ok({"scrolled": [dy, dx]})


@tool(
    "drag",
    "Press at (x1,y1), drag to (x2,y2), release.",
    {"type": "object", "properties": {
        "x1": {"type": "number"}, "y1": {"type": "number"},
        "x2": {"type": "number"}, "y2": {"type": "number"},
        "steps": {"type": "integer"},
    }, "required": ["x1", "y1", "x2", "y2"]},
)
def t_drag(x1: float, y1: float, x2: float, y2: float, steps: int = 20):
    from .input import drag
    drag(x1, y1, x2, y2, steps=steps)
    return _ok({"dragged_from": [x1, y1], "to": [x2, y2]})


@tool(
    "mouse_move",
    "Move the mouse cursor without clicking.",
    {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}}, "required": ["x", "y"]},
)
def t_mouse_move(x: float, y: float):
    from .input import mouse_move
    mouse_move(x, y)
    return _ok({"moved_to": [x, y]})


# --- screen / OCR ----------------------------------------------------------


@tool(
    "screenshot",
    "Capture the full screen. Returns saved PNG path (and base64 if include_image=true).",
    {"type": "object", "properties": {"path": {"type": "string"}, "include_image": {"type": "boolean"}}},
)
def t_screenshot(path: str | None = None, include_image: bool = False):
    from .screen import screenshot
    p = screenshot(path)
    out = {"path": p}
    if include_image:
        out["image_b64"] = _b64_image(p)
    return _ok(out)


@tool(
    "screenshot_window",
    "Capture window N of an app.",
    {"type": "object", "properties": {"app": {"type": "string"}, "index": {"type": "integer"}, "path": {"type": "string"}}, "required": ["app"]},
)
def t_screenshot_window(app: str, index: int = 0, path: str | None = None):
    from .screen import screenshot_window
    return _ok({"path": screenshot_window(app, index=index, path=path)})


@tool(
    "screenshot_region",
    "Capture a rectangular region of the screen.",
    {"type": "object", "properties": {
        "x": {"type": "integer"}, "y": {"type": "integer"},
        "w": {"type": "integer"}, "h": {"type": "integer"},
        "path": {"type": "string"},
    }, "required": ["x", "y", "w", "h"]},
)
def t_screenshot_region(x: int, y: int, w: int, h: int, path: str | None = None):
    from .screen import screenshot_region
    return _ok({"path": screenshot_region(x, y, w, h, path)})


@tool(
    "displays",
    "Enumerate all attached displays.",
)
def t_displays():
    from .screen import displays
    return _ok(displays())


@tool(
    "ocr_image",
    "OCR a PNG/JPEG file using the macOS Vision framework. Returns text blocks with bbox + confidence.",
    {"type": "object", "properties": {"path": {"type": "string"}, "fast": {"type": "boolean"}}, "required": ["path"]},
)
def t_ocr_image(path: str, fast: bool = False):
    from .ocr import ocr
    return _ok(ocr(path, fast=fast))


@tool(
    "ocr_region",
    "Screenshot a region then OCR it.",
    {"type": "object", "properties": {
        "x": {"type": "integer"}, "y": {"type": "integer"},
        "w": {"type": "integer"}, "h": {"type": "integer"},
        "fast": {"type": "boolean"},
    }, "required": ["x", "y", "w", "h"]},
)
def t_ocr_region(x: int, y: int, w: int, h: int, fast: bool = False):
    from .ocr import ocr_region
    return _ok(ocr_region(x, y, w, h, fast=fast))


@tool(
    "ocr_window",
    "OCR a specific app window.",
    {"type": "object", "properties": {"app": {"type": "string"}, "index": {"type": "integer"}, "fast": {"type": "boolean"}}, "required": ["app"]},
)
def t_ocr_window(app: str, index: int = 0, fast: bool = False):
    from .ocr import ocr_window
    return _ok(ocr_window(app, index=index, fast=fast))


@tool(
    "find_text_on_screen",
    "OCR the full screen and find a string. Returns (x, y) center pixel coords for clicking.",
    {"type": "object", "properties": {"needle": {"type": "string"}, "case_insensitive": {"type": "boolean"}}, "required": ["needle"]},
)
def t_find_text_on_screen(needle: str, case_insensitive: bool = True):
    from .ocr import find_text_on_screen
    pt = find_text_on_screen(needle, case_insensitive=case_insensitive)
    if pt is None:
        return _err(f"text not found on screen: {needle!r}")
    return _ok({"x": pt[0], "y": pt[1]})


# --- AppleScript -----------------------------------------------------------


@tool(
    "osascript",
    "Run an AppleScript and return stdout.",
    {"type": "object", "properties": {"script": {"type": "string"}, "language": {"type": "string"}, "timeout": {"type": "number"}}, "required": ["script"]},
)
def t_osascript(script: str, language: str | None = None, timeout: float = 30.0):
    from .applescript import osascript
    return _ok({"stdout": osascript(script, language=language, timeout=timeout)})


@tool(
    "osascript_app",
    "Wrap script body in `tell application \"X\" ... end tell` and run.",
    {"type": "object", "properties": {"app": {"type": "string"}, "body": {"type": "string"}, "timeout": {"type": "number"}}, "required": ["app", "body"]},
)
def t_osascript_app(app: str, body: str, timeout: float = 30.0):
    from .applescript import osascript_app
    return _ok({"stdout": osascript_app(app, body, timeout=timeout)})


@tool(
    "jxa",
    "Run JavaScript for Automation (JXA). Same surface as AppleScript, JS syntax.",
    {"type": "object", "properties": {"script": {"type": "string"}, "timeout": {"type": "number"}}, "required": ["script"]},
)
def t_jxa(script: str, timeout: float = 30.0):
    from .applescript import jxa
    return _ok({"stdout": jxa(script, timeout=timeout)})


# --- observers -------------------------------------------------------------


_OBSERVER_EVENTS: dict[int, list[dict]] = {}
_OBSERVER_LOCK = threading.Lock()


@tool(
    "observe_app",
    "Subscribe to an AX notification on an app. Events are buffered; poll with get_observer_events.",
    {"type": "object", "properties": {
        "app": {"type": "string"},
        "notification": {"type": "string"},
        "scope": {"type": "string", "enum": ["app", "focused", "main_window"]},
    }, "required": ["app", "notification"]},
)
def t_observe_app(app: str, notification: str, scope: str = "app"):
    from . import observers as O

    buffer: list[dict] = []
    handle_id_box: dict = {}

    def cb(el, info):
        buffer.append({"t": time.time(), "info": info, "element": _ax_describe(el)})

    hid = O.observe(app, notification, cb, scope=scope)
    handle_id_box["id"] = hid
    with _OBSERVER_LOCK:
        _OBSERVER_EVENTS[hid] = buffer
    return _ok({"observer_id": hid, "buffer_kept_in_memory": True})


@tool(
    "get_observer_events",
    "Pull buffered events for an observer (and optionally drain).",
    {"type": "object", "properties": {"observer_id": {"type": "integer"}, "drain": {"type": "boolean"}}, "required": ["observer_id"]},
)
def t_get_observer_events(observer_id: int, drain: bool = True):
    with _OBSERVER_LOCK:
        evs = _OBSERVER_EVENTS.get(observer_id, [])
        if drain:
            _OBSERVER_EVENTS[observer_id] = []
            return _ok({"events": evs})
        return _ok({"events": list(evs)})


@tool(
    "list_observers",
    "Active observer subscriptions.",
)
def t_list_observers():
    from . import observers as O
    return _ok(O.list_observers())


@tool(
    "stop_observer",
    "Unsubscribe an observer by id.",
    {"type": "object", "properties": {"observer_id": {"type": "integer"}}, "required": ["observer_id"]},
)
def t_stop_observer(observer_id: int):
    from . import observers as O
    ok = O.unobserve(observer_id)
    with _OBSERVER_LOCK:
        _OBSERVER_EVENTS.pop(observer_id, None)
    return _ok({"stopped": ok})


@tool(
    "stop_all_observers",
    "Unsubscribe every observer registered in this MCP server.",
)
def t_stop_all_observers():
    from . import observers as O
    n = O.stop_all()
    with _OBSERVER_LOCK:
        _OBSERVER_EVENTS.clear()
    return _ok({"stopped_count": n})


@tool(
    "wait_for_event",
    "Block until an AX notification fires on an app (or timeout). Returns the triggering element ref.",
    {"type": "object", "properties": {
        "app": {"type": "string"},
        "notification": {"type": "string"},
        "scope": {"type": "string"},
        "timeout": {"type": "number"},
    }, "required": ["app", "notification"]},
)
def t_wait_for_event(app: str, notification: str, scope: str = "app", timeout: float = 10.0):
    from . import observers as O
    el = O.wait_for(app, notification, scope=scope, timeout=timeout)
    if el is None:
        return _err("timed out waiting for event")
    return _ok({"ref": _ax_store(el), **_ax_describe(el)})


# --- permissions -----------------------------------------------------------


@tool(
    "doctor",
    "Diagnostics: pyobjc imports OK + every TCC permission status. Use first when something fails.",
)
def t_doctor():
    from .permissions import doctor_permissions
    perms = doctor_permissions()
    out = {
        "version": __version__,
        "permissions": perms,
        "notes": [],
    }
    if not perms["accessibility"]:
        out["notes"].append("Accessibility OFF — AX find/click and CGEvent input will fail.")
    if not perms["screen_recording"]:
        out["notes"].append("Screen Recording OFF — screenshots and OCR will fail.")
    return _ok(out)


@tool(
    "request_accessibility",
    "Trigger the macOS dialog asking for Accessibility permission.",
)
def t_request_accessibility():
    from .permissions import request_accessibility
    return _ok({"granted": request_accessibility()})


@tool(
    "version",
    "Server version + tool count.",
)
def t_version():
    return _ok({"version": __version__, "tool_count": len(TOOLS)})


# --- JSON-RPC dispatcher ---------------------------------------------------


def _handle_request(req: dict) -> dict | None:
    method = req.get("method") or ""
    rid = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        client_v = params.get("protocolVersion", SUPPORTED_PROTOCOL_VERSIONS[0])
        negotiated = client_v if client_v in SUPPORTED_PROTOCOL_VERSIONS else SUPPORTED_PROTOCOL_VERSIONS[0]
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "desktop-harness", "version": __version__},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method.startswith("notifications/"):
        return None
    if method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {"tools": [
                {"name": n, "description": t["description"], "inputSchema": t["input_schema"]}
                for n, t in TOOLS.items()
            ]},
        }
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        spec = TOOLS.get(name)
        if spec is None:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Unknown tool: {name}"}}
        try:
            result = spec["handler"](**args)
        except TypeError as e:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": f"Bad arguments for {name}: {e}"}}
        except Exception as e:  # noqa: BLE001
            log.exception("tool %s failed", name)
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32000, "message": str(e)}}
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]},
        }
    if rid is None:
        return None
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def main() -> int:
    log.info("desktop-harness %s MCP server starting (%d tools)", __version__, len(TOOLS))
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                # graceful EOF (peer closed) — keep running until stdin re-attaches
                # would here, but per MCP contract clients keep stdin open. Exit cleanly.
                log.info("stdin EOF — exiting")
                break
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                log.warning("bad JSON: %s", e)
                continue
            resp = _handle_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except KeyboardInterrupt:
            break
        except Exception as e:  # noqa: BLE001
            log.exception("server error: %s", e)
    # cleanup observers
    try:
        from . import observers as O
        O.stop_all()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
