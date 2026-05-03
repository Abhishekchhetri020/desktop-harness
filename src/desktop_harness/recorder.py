"""User-action recorder — capture clicks/keys, emit a replayable Python script.

Uses CGEventTap to listen to system input. Outputs:
  - JSON event list (--out events.json)
  - or a runnable Python script using desktop_harness primitives (--out replay.py)

Caveats:
  - Requires both Accessibility AND Input Monitoring permissions for the
    recording process (Terminal, iTerm, Claude Code, …).
  - We capture mouse position + key events. We do NOT capture clipboard
    contents or Touch ID. Modifier-only events are tracked.
  - Generated scripts use absolute pixel coords by default. For more robust
    replay, edit them to use AX find()/click_element() instead.

Example:

    from desktop_harness import recorder
    rec = recorder.Recorder()
    rec.start()
    # ... user interacts ...
    rec.stop()
    rec.to_python("/tmp/replay.py")

CLI:
    desktop-harness record --out /tmp/replay.py --duration 30
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from CoreFoundation import (
    CFRunLoopAddSource,
    CFRunLoopRun,
    CFRunLoopStop,
    CFRunLoopGetCurrent,
    CFMachPortCreateRunLoopSource,
    kCFRunLoopDefaultMode,
    kCFAllocatorDefault,
)
from Quartz import (
    CGEventTapCreate,
    CGEventTapEnable,
    CGEventGetLocation,
    CGEventGetIntegerValueField,
    CGEventGetFlags,
    CGEventGetType,
    kCGSessionEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionListenOnly,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGEventRightMouseDown,
    kCGEventRightMouseUp,
    kCGEventOtherMouseDown,
    kCGEventOtherMouseUp,
    kCGEventKeyDown,
    kCGEventKeyUp,
    kCGEventFlagsChanged,
    kCGEventScrollWheel,
    kCGKeyboardEventKeycode,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskShift,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskControl,
    kCGScrollWheelEventDeltaAxis1,
    kCGScrollWheelEventDeltaAxis2,
    kCGMouseEventClickState,
)

from .input import KEYCODES


_INVERSE_KEYCODES = {v: k for k, v in KEYCODES.items()}


_EVENT_NAMES = {
    kCGEventLeftMouseDown: "left_down",
    kCGEventLeftMouseUp: "left_up",
    kCGEventRightMouseDown: "right_down",
    kCGEventRightMouseUp: "right_up",
    kCGEventOtherMouseDown: "other_down",
    kCGEventOtherMouseUp: "other_up",
    kCGEventKeyDown: "key_down",
    kCGEventKeyUp: "key_up",
    kCGEventFlagsChanged: "flags",
    kCGEventScrollWheel: "scroll",
}


@dataclass
class Event:
    t: float            # seconds since Recorder.start()
    type: str           # left_down, key_down, scroll, ...
    x: Optional[float] = None
    y: Optional[float] = None
    key: Optional[str] = None
    keycode: Optional[int] = None
    modifiers: list[str] = field(default_factory=list)
    click_count: Optional[int] = None
    scroll_dy: Optional[int] = None
    scroll_dx: Optional[int] = None


def _flags_to_modifiers(flags: int) -> list[str]:
    out = []
    if flags & kCGEventFlagMaskCommand:  out.append("cmd")
    if flags & kCGEventFlagMaskShift:    out.append("shift")
    if flags & kCGEventFlagMaskAlternate: out.append("option")
    if flags & kCGEventFlagMaskControl:  out.append("ctrl")
    return out


class Recorder:
    """Record system input events. Start, stop, dump."""

    def __init__(self):
        self._events: list[Event] = []
        self._t0: Optional[float] = None
        self._tap = None
        self._runloop = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self, *, timeout: float = 5.0) -> None:
        """Begin recording. Returns once the tap is live (or raises)."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._t0 = time.monotonic()
        self._stop.clear()
        ready = threading.Event()
        err: dict = {}

        def _run():
            try:
                mask = (
                    (1 << kCGEventLeftMouseDown) | (1 << kCGEventLeftMouseUp)
                    | (1 << kCGEventRightMouseDown) | (1 << kCGEventRightMouseUp)
                    | (1 << kCGEventOtherMouseDown) | (1 << kCGEventOtherMouseUp)
                    | (1 << kCGEventKeyDown) | (1 << kCGEventKeyUp)
                    | (1 << kCGEventFlagsChanged) | (1 << kCGEventScrollWheel)
                )
                tap = CGEventTapCreate(
                    kCGSessionEventTap,
                    kCGHeadInsertEventTap,
                    kCGEventTapOptionListenOnly,
                    mask,
                    self._tap_callback,
                    None,
                )
                if tap is None:
                    err["msg"] = (
                        "CGEventTapCreate returned None. The recording process "
                        "needs both Accessibility AND Input Monitoring "
                        "permissions in System Settings → Privacy & Security."
                    )
                    ready.set()
                    return
                self._tap = tap
                src = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
                CFRunLoopAddSource(CFRunLoopGetCurrent(), src, kCFRunLoopDefaultMode)
                CGEventTapEnable(tap, True)
                self._runloop = CFRunLoopGetCurrent()
                ready.set()
                while not self._stop.is_set():
                    CFRunLoopRun()
            except Exception as e:  # noqa: BLE001
                err["msg"] = repr(e)
                ready.set()

        self._thread = threading.Thread(target=_run, name="dh-recorder", daemon=True)
        self._thread.start()
        if not ready.wait(timeout=timeout):
            raise RuntimeError("recorder thread failed to start (timeout)")
        if "msg" in err:
            raise RuntimeError(err["msg"])

    def stop(self) -> list[Event]:
        """Stop recording. Returns the captured events."""
        if self._tap is not None:
            try:
                CGEventTapEnable(self._tap, False)
            except Exception:
                pass
        self._stop.set()
        if self._runloop is not None:
            try:
                CFRunLoopStop(self._runloop)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        return self.events()

    def events(self) -> list[Event]:
        with self._lock:
            return list(self._events)

    def to_json(self, path: str) -> str:
        Path(path).write_text(json.dumps([asdict(e) for e in self.events()], indent=2))
        return path

    def to_python(self, path: str, *, base_delay: float = 0.05) -> str:
        """Generate a runnable Python script that replays the recording."""
        lines = [
            "#!/usr/bin/env python3",
            '"""Auto-generated by desktop_harness.recorder. Edit freely.',
            "",
            "Replay tip: pixel-coord clicks are fragile. For reliable replay,",
            "rewrite a click_at(x,y) call as:",
            '    click_element(find("AppName", role="AXButton", title="Save"))',
            '"""',
            "import time",
            "from desktop_harness import click_at, double_click_at, right_click_at",
            "from desktop_harness import key, type_text, scroll, mouse_move",
            "",
        ]
        prev_t = 0.0
        keys_down: dict[int, list[str]] = {}
        for e in self.events():
            dt = max(0.0, e.t - prev_t)
            if dt > base_delay:
                lines.append(f"time.sleep({dt:.3f})")
            prev_t = e.t
            if e.type in ("left_down", "right_down", "other_down"):
                # capture down — wait for matching up to coalesce as click
                keys_down[id(e)] = [e.type, e.x, e.y, e.click_count or 1]
                continue
            if e.type in ("left_up", "right_up", "other_up"):
                # naive: emit click on up
                btn = "left" if "left" in e.type else ("right" if "right" in e.type else "left")
                count = e.click_count or 1
                if btn == "left" and count == 2:
                    lines.append(f"double_click_at({e.x:.1f}, {e.y:.1f})")
                elif btn == "right":
                    lines.append(f"right_click_at({e.x:.1f}, {e.y:.1f})")
                else:
                    lines.append(f"click_at({e.x:.1f}, {e.y:.1f})  # count={count}")
                continue
            if e.type == "key_down":
                if e.key:
                    chord = "+".join(e.modifiers + [e.key]) if e.modifiers else e.key
                    lines.append(f"key({chord!r})")
                else:
                    lines.append(f"key('keycode_{e.keycode}')  # unknown key")
                continue
            if e.type == "scroll":
                lines.append(f"scroll(dy={e.scroll_dy or 0}, dx={e.scroll_dx or 0})")
                continue
            # key_up, flags — ignore (combos handled by key())
        lines.append("")
        Path(path).write_text("\n".join(lines))
        return path

    # --- internal ------------------------------------------------------------

    def _tap_callback(self, proxy, event_type, event, refcon):
        try:
            t = time.monotonic() - (self._t0 or time.monotonic())
            name = _EVENT_NAMES.get(event_type, f"type_{event_type}")
            ev = Event(t=t, type=name)
            if event_type in (
                kCGEventLeftMouseDown, kCGEventLeftMouseUp,
                kCGEventRightMouseDown, kCGEventRightMouseUp,
                kCGEventOtherMouseDown, kCGEventOtherMouseUp,
                kCGEventScrollWheel,
            ):
                pt = CGEventGetLocation(event)
                ev.x = float(pt.x)
                ev.y = float(pt.y)
            if event_type in (kCGEventLeftMouseUp, kCGEventLeftMouseDown):
                ev.click_count = int(CGEventGetIntegerValueField(event, kCGMouseEventClickState))
            if event_type in (kCGEventKeyDown, kCGEventKeyUp, kCGEventFlagsChanged):
                kc = int(CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode))
                ev.keycode = kc
                ev.key = _INVERSE_KEYCODES.get(kc)
                ev.modifiers = _flags_to_modifiers(CGEventGetFlags(event))
            if event_type == kCGEventScrollWheel:
                ev.scroll_dy = int(CGEventGetIntegerValueField(event, kCGScrollWheelEventDeltaAxis1))
                ev.scroll_dx = int(CGEventGetIntegerValueField(event, kCGScrollWheelEventDeltaAxis2))
            with self._lock:
                self._events.append(ev)
        except Exception:
            pass
        return event
