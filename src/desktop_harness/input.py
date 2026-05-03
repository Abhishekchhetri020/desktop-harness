"""Low-level input via CGEvent. Mouse + keyboard at the OS level."""
from __future__ import annotations
import time
from typing import Optional, Tuple

from Quartz import (
    CGEventCreateMouseEvent,
    CGEventCreateKeyboardEvent,
    CGEventCreateScrollWheelEvent,
    CGEventPost,
    CGEventSetFlags,
    CGEventKeyboardSetUnicodeString,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGEventRightMouseDown,
    kCGEventRightMouseUp,
    kCGEventMouseMoved,
    kCGEventLeftMouseDragged,
    kCGHIDEventTap,
    kCGMouseButtonLeft,
    kCGMouseButtonRight,
    kCGScrollEventUnitPixel,
    kCGScrollEventUnitLine,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskShift,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskControl,
    CGEventSetIntegerValueField,
    kCGMouseEventClickState,
)

# US ANSI keycodes (kVK_*)
KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7,
    "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16,
    "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "=": 24,
    "9": 25, "7": 26, "-": 27, "8": 28, "0": 29, "]": 30, "o": 31, "u": 32,
    "[": 33, "i": 34, "p": 35, "l": 37, "j": 38, "'": 39, "k": 40, ";": 41,
    "\\": 42, ",": 43, "/": 44, "n": 45, "m": 46, ".": 47,
    "return": 36, "enter": 36,
    "tab": 48, "space": 49, "delete": 51, "backspace": 51, "escape": 53, "esc": 53,
    "command": 55, "cmd": 55,
    "shift": 56, "capslock": 57, "option": 58, "alt": 58, "control": 59, "ctrl": 59,
    "right_shift": 60, "right_option": 61, "right_control": 62, "fn": 63,
    "f17": 64, "volumeup": 72, "volumedown": 73, "mute": 74,
    "f18": 79, "f19": 80, "f20": 90,
    "f5": 96, "f6": 97, "f7": 98, "f3": 99, "f8": 100, "f9": 101,
    "f11": 103, "f13": 105, "f16": 106, "f14": 107, "f10": 109, "f12": 111,
    "f15": 113, "help": 114, "home": 115, "pageup": 116, "forward_delete": 117,
    "f4": 118, "end": 119, "f2": 120, "pagedown": 121, "f1": 122,
    "left": 123, "right": 124, "down": 125, "up": 126,
}

_MODIFIERS = {
    "cmd": kCGEventFlagMaskCommand, "command": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift,
    "alt": kCGEventFlagMaskAlternate, "option": kCGEventFlagMaskAlternate, "opt": kCGEventFlagMaskAlternate,
    "ctrl": kCGEventFlagMaskControl, "control": kCGEventFlagMaskControl,
}


def _post(event):
    CGEventPost(kCGHIDEventTap, event)


def mouse_move(x: float, y: float) -> None:
    ev = CGEventCreateMouseEvent(None, kCGEventMouseMoved, (x, y), kCGMouseButtonLeft)
    _post(ev)


def click_at(x: float, y: float, *, button: str = "left", count: int = 1, delay: float = 0.05) -> None:
    """Click at (x, y) in screen coords. Single, double, or triple-click via count."""
    btn = kCGMouseButtonLeft if button == "left" else kCGMouseButtonRight
    down_t = kCGEventLeftMouseDown if button == "left" else kCGEventRightMouseDown
    up_t = kCGEventLeftMouseUp if button == "left" else kCGEventRightMouseUp
    mouse_move(x, y)
    time.sleep(delay)
    for i in range(count):
        down = CGEventCreateMouseEvent(None, down_t, (x, y), btn)
        CGEventSetIntegerValueField(down, kCGMouseEventClickState, i + 1)
        _post(down)
        up = CGEventCreateMouseEvent(None, up_t, (x, y), btn)
        CGEventSetIntegerValueField(up, kCGMouseEventClickState, i + 1)
        _post(up)
        if count > 1:
            time.sleep(0.04)


def double_click_at(x: float, y: float) -> None:
    click_at(x, y, count=2)


def right_click_at(x: float, y: float) -> None:
    click_at(x, y, button="right")


def drag(x1: float, y1: float, x2: float, y2: float, *, steps: int = 20, hold: float = 0.05) -> None:
    """Press at (x1,y1), drag to (x2,y2), release."""
    mouse_move(x1, y1)
    time.sleep(hold)
    down = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, (x1, y1), kCGMouseButtonLeft)
    _post(down)
    for i in range(1, steps + 1):
        t = i / steps
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        ev = CGEventCreateMouseEvent(None, kCGEventLeftMouseDragged, (x, y), kCGMouseButtonLeft)
        _post(ev)
        time.sleep(0.005)
    up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, (x2, y2), kCGMouseButtonLeft)
    _post(up)


def type_text(text: str, *, delay: float = 0.005) -> None:
    """Type a string by pushing each character via CGEventKeyboardSetUnicodeString.
    Fast and Unicode-clean — works for emoji, CJK, etc. Bypasses keyboard layouts."""
    for ch in text:
        ev_down = CGEventCreateKeyboardEvent(None, 0, True)
        CGEventKeyboardSetUnicodeString(ev_down, len(ch.encode("utf-16-le")) // 2, ch)
        _post(ev_down)
        ev_up = CGEventCreateKeyboardEvent(None, 0, False)
        CGEventKeyboardSetUnicodeString(ev_up, len(ch.encode("utf-16-le")) // 2, ch)
        _post(ev_up)
        if delay:
            time.sleep(delay)


def _parse_combo(combo: str) -> tuple[int, int]:
    parts = [p.strip().lower() for p in combo.split("+")]
    flags = 0
    main = parts[-1]
    for mod in parts[:-1]:
        if mod in _MODIFIERS:
            flags |= _MODIFIERS[mod]
        else:
            raise ValueError(f"Unknown modifier: {mod}")
    if main not in KEYCODES:
        raise ValueError(f"Unknown key: {main}")
    return KEYCODES[main], flags


def key(combo: str, *, count: int = 1, delay: float = 0.04) -> None:
    """Press a key or combo, e.g. 'cmd+a', 'return', 'cmd+shift+t'."""
    keycode, flags = _parse_combo(combo)
    for _ in range(count):
        down = CGEventCreateKeyboardEvent(None, keycode, True)
        if flags:
            CGEventSetFlags(down, flags)
        _post(down)
        up = CGEventCreateKeyboardEvent(None, keycode, False)
        if flags:
            CGEventSetFlags(up, flags)
        _post(up)
        if delay:
            time.sleep(delay)


def hold_key(combo: str, duration: float) -> None:
    """Press and hold for duration seconds, then release."""
    keycode, flags = _parse_combo(combo)
    down = CGEventCreateKeyboardEvent(None, keycode, True)
    if flags:
        CGEventSetFlags(down, flags)
    _post(down)
    time.sleep(duration)
    up = CGEventCreateKeyboardEvent(None, keycode, False)
    if flags:
        CGEventSetFlags(up, flags)
    _post(up)


def scroll(dy: int = 0, dx: int = 0, *, x: float | None = None, y: float | None = None,
           unit: str = "pixel") -> None:
    """Scroll by dy (vertical) and dx (horizontal). Positive dy = down, positive dx = right.
    Optionally move cursor to (x, y) first."""
    if x is not None and y is not None:
        mouse_move(x, y)
        time.sleep(0.02)
    u = kCGScrollEventUnitPixel if unit == "pixel" else kCGScrollEventUnitLine
    ev = CGEventCreateScrollWheelEvent(None, u, 2, -dy, dx)
    _post(ev)
