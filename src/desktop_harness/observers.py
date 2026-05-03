"""Live AX notifications — react to UI changes instead of polling.

Subscribe to AXNotification events on an element. Common notifications:
  AXFocusedUIElementChanged   focus moves to a different element
  AXFocusedWindowChanged      app's focused window changed
  AXMainWindowChanged         app's main window changed
  AXWindowCreated             new window appeared
  AXWindowMoved               window moved
  AXWindowResized             window resized
  AXValueChanged              a text field / slider value changed
  AXTitleChanged              an element's title changed
  AXSelectedTextChanged       selection changed in a text view

Usage:

    from desktop_harness import observers as O

    def on_value(element, info):
        print("changed:", get_value(element))

    handle = O.observe("Notes", "AXValueChanged", on_value, scope="focused")
    # ... later
    O.unobserve(handle)

    # Or use a context manager:
    with O.observing("Notes", "AXFocusedUIElementChanged", on_focus):
        ...

The observer runs on a background CFRunLoop thread; your callback fires on
that thread, so keep it short (no blocking I/O, no Tkinter, no NSApp work).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterator, Optional

from ApplicationServices import (
    AXObserverCreate,
    AXObserverAddNotification,
    AXObserverRemoveNotification,
    AXObserverGetRunLoopSource,
    kAXErrorSuccess,
)
from CoreFoundation import (
    CFRunLoopAddSource,
    CFRunLoopRun,
    CFRunLoopStop,
    CFRunLoopGetCurrent,
    kCFRunLoopDefaultMode,
)

from .ax import app_ax, focused_element, get_attr, AXError
from .apps import pid_of


Callback = Callable[[object, dict], None]


@dataclass
class ObserverHandle:
    """Opaque handle returned by observe(). Pass to unobserve()."""
    pid: int
    notification: str
    element_role: str
    _observer: object
    _element: object
    _thread: threading.Thread
    _runloop: object
    _stop: threading.Event


_HANDLES: dict[int, ObserverHandle] = {}
_NEXT_ID = 0
_LOCK = threading.Lock()


def _next_id() -> int:
    global _NEXT_ID
    with _LOCK:
        _NEXT_ID += 1
        return _NEXT_ID


def observe(
    app_name: str,
    notification: str,
    callback: Callback,
    *,
    scope: str = "app",
    user_info: Optional[dict] = None,
    timeout: float = 5.0,
) -> int:
    """Subscribe to AX notifications.

    Args:
        app_name: target app
        notification: e.g. "AXFocusedUIElementChanged", "AXValueChanged"
        callback: fn(element, info_dict) — called from the observer thread
        scope: "app" → on the app root element. "focused" → on whatever element
               is focused right now. "main_window" → on the main window.
        user_info: extra dict passed back to callback in info["user_info"]
        timeout: how long to wait for the observer thread to spin up

    Returns:
        an integer handle id. Pass to unobserve() to stop receiving.
    """
    pid = pid_of(app_name)
    if pid is None:
        raise AXError(f"app not running: {app_name!r}")

    if scope == "app":
        element = app_ax(app_name)
        role = "AXApplication"
    elif scope == "focused":
        element = focused_element()
        if element is None:
            raise AXError("no focused element to observe")
        role = str(get_attr(element, "AXRole") or "")
    elif scope == "main_window":
        from .windows import main_window
        element = main_window(app_name)
        role = "AXWindow"
    else:
        raise ValueError(f"unknown scope: {scope!r}")

    err, observer = AXObserverCreate(pid, _trampoline, None)
    if err != kAXErrorSuccess or observer is None:
        raise AXError(f"AXObserverCreate failed for pid {pid} (err={err})")

    info_box: dict = {"callback": callback, "user_info": user_info or {}}
    err = AXObserverAddNotification(observer, element, notification, info_box)
    if err != kAXErrorSuccess:
        raise AXError(
            f"AXObserverAddNotification failed for {notification!r} "
            f"on {role!r} (err={err}). The app may not emit this notification, "
            f"or you may need Accessibility permission."
        )

    stop = threading.Event()
    runloop_box: dict = {}
    started = threading.Event()

    def _run():
        try:
            rl = CFRunLoopGetCurrent()
            runloop_box["rl"] = rl
            src = AXObserverGetRunLoopSource(observer)
            CFRunLoopAddSource(rl, src, kCFRunLoopDefaultMode)
            started.set()
            while not stop.is_set():
                CFRunLoopRun()
        except Exception as e:  # noqa: BLE001
            info_box["error"] = repr(e)
            started.set()

    th = threading.Thread(target=_run, name=f"dh-observer-{notification}", daemon=True)
    th.start()
    if not started.wait(timeout=timeout):
        raise AXError("observer thread failed to start (timeout)")

    handle = ObserverHandle(
        pid=pid, notification=notification, element_role=role,
        _observer=observer, _element=element,
        _thread=th, _runloop=runloop_box.get("rl"), _stop=stop,
    )
    handle_id = _next_id()
    _HANDLES[handle_id] = handle
    return handle_id


def unobserve(handle_id: int) -> bool:
    """Stop a previously-registered observer."""
    h = _HANDLES.pop(handle_id, None)
    if h is None:
        return False
    try:
        AXObserverRemoveNotification(h._observer, h._element, h.notification)
    except Exception:
        pass
    h._stop.set()
    if h._runloop is not None:
        try:
            CFRunLoopStop(h._runloop)
        except Exception:
            pass
    h._thread.join(timeout=2.0)
    return True


def list_observers() -> list[dict]:
    """All currently-active observer handles."""
    return [
        {"id": k, "pid": v.pid, "notification": v.notification, "scope_role": v.element_role}
        for k, v in _HANDLES.items()
    ]


def stop_all() -> int:
    """Unsubscribe every observer registered in this process."""
    n = 0
    for hid in list(_HANDLES):
        if unobserve(hid):
            n += 1
    return n


class observing:
    """Context manager.  with observing("X", "AXValueChanged", cb): ..."""

    def __init__(self, app_name: str, notification: str, callback: Callback, **kwargs):
        self.app_name = app_name
        self.notification = notification
        self.callback = callback
        self.kwargs = kwargs
        self._id: Optional[int] = None

    def __enter__(self):
        self._id = observe(self.app_name, self.notification, self.callback, **self.kwargs)
        return self._id

    def __exit__(self, *exc):
        if self._id is not None:
            unobserve(self._id)


# --- C trampoline -----------------------------------------------------------

def _trampoline(observer, element, notification, refcon):
    """Bridges from the C AX callback to the Python callable.

    pyobjc's AXObserverCreate signature takes a callback that receives
    (observer, element, notification, refcon). refcon is the dict we
    passed to AddNotification — contains the user callback.
    """
    try:
        cb = refcon.get("callback") if isinstance(refcon, dict) else None
        if cb is None:
            return
        info = {
            "notification": str(notification) if notification else None,
            "user_info": refcon.get("user_info") if isinstance(refcon, dict) else None,
        }
        cb(element, info)
    except Exception as e:  # noqa: BLE001
        # Never propagate exceptions back into Cocoa — would crash the run loop.
        try:
            import sys
            print(f"[observers] callback error: {e!r}", file=sys.stderr)
        except Exception:
            pass


# --- helpers ---------------------------------------------------------------


def wait_for(
    app_name: str,
    notification: str,
    *,
    scope: str = "app",
    timeout: float = 10.0,
    predicate: Optional[Callable[[object, dict], bool]] = None,
) -> Optional[object]:
    """Block until a notification fires (optionally matching predicate).

    Returns the element that triggered it, or None on timeout. Useful for
    waiting on a window to open, a value to change, etc.
    """
    got: dict = {}
    done = threading.Event()

    def _cb(el, info):
        if predicate is None or predicate(el, info):
            got["el"] = el
            done.set()

    hid = observe(app_name, notification, _cb, scope=scope)
    try:
        done.wait(timeout=timeout)
        return got.get("el")
    finally:
        unobserve(hid)
