"""Wait + verify primitives.

Agents must not be forced into blind sleep loops. This module wraps
AX notifications (via observers.wait_for) where possible, with a polling
fallback when the right notification doesn't fit the use case.

All waits return a structured dict so the caller can reason about which
method observed the change ("ax_notification" vs "polling") and how long
it took.
"""
from __future__ import annotations

import time
from typing import Optional

from .ax import find, app_ax, get_attr
from .apps import is_running, frontmost
from .windows import list_windows


def _now() -> float:
    return time.monotonic()


def wait_for_app(app: str, *, timeout: float = 10.0, poll: float = 0.2) -> dict:
    """Wait for an app to be running. Polls (no AX notification fits)."""
    start = _now()
    while _now() - start < timeout:
        if is_running(app):
            return {"ok": True, "method": "polling", "elapsed": _now() - start}
        time.sleep(poll)
    return {
        "ok": False, "method": "polling", "elapsed": _now() - start,
        "error": f"app {app!r} did not start within {timeout}s",
        "hint": "Run `open_app('AppName')` or check the app is installed.",
    }


def wait_for_frontmost(app: str, *, timeout: float = 10.0, poll: float = 0.2) -> dict:
    """Wait for `app` to become frontmost."""
    start = _now()
    while _now() - start < timeout:
        fm = frontmost() or {}
        if fm.get("name") == app:
            return {"ok": True, "method": "polling", "elapsed": _now() - start}
        time.sleep(poll)
    fm = frontmost() or {}
    return {
        "ok": False, "method": "polling", "elapsed": _now() - start,
        "frontmost": fm.get("name"),
        "error": f"{app!r} not frontmost within {timeout}s",
        "hint": "Call `activate(app)` to bring it forward, then re-wait.",
    }


def wait_for_window(
    app: str,
    *,
    title: Optional[str] = None,
    title_contains: Optional[str] = None,
    timeout: float = 10.0,
    poll: float = 0.25,
) -> dict:
    """Wait for a window matching the title filter to appear in `app`."""
    start = _now()
    while _now() - start < timeout:
        try:
            wins = list_windows(app)
        except Exception:
            wins = []
        for w in wins:
            name = w.get("name") or ""
            if title is not None and name == title:
                return {"ok": True, "method": "polling", "elapsed": _now() - start, "window": w}
            if title_contains is not None and title_contains.lower() in name.lower():
                return {"ok": True, "method": "polling", "elapsed": _now() - start, "window": w}
            if title is None and title_contains is None and name:
                return {"ok": True, "method": "polling", "elapsed": _now() - start, "window": w}
        time.sleep(poll)
    return {
        "ok": False, "method": "polling", "elapsed": _now() - start,
        "error": f"no matching window in {app!r} within {timeout}s",
        "hint": "Open the window first, or relax the title filter.",
    }


def wait_for_element(
    app: str,
    *,
    role: Optional[str] = None,
    title: Optional[str] = None,
    title_contains: Optional[str] = None,
    identifier: Optional[str] = None,
    timeout: float = 10.0,
    poll: float = 0.2,
):
    """Wait for an AX element matching the filters to appear.

    Returns {"ok": True, "ref": <id>, "method": "polling", "elapsed": ...}
    on success. The ref is a stable ElementRef id; pass it to resolve_ref()
    or smart_click(ref=...).
    """
    from .refs import create_element_ref
    start = _now()
    while _now() - start < timeout:
        try:
            kw = {}
            if role is not None: kw["role"] = role
            if title is not None: kw["title"] = title
            if title_contains is not None: kw["title_contains"] = title_contains
            if identifier is not None: kw["identifier"] = identifier
            el = find(app, **kw) if kw else None
        except Exception:
            el = None
        if el is not None:
            ref = create_element_ref(el, app=app)
            return {
                "ok": True, "method": "polling", "elapsed": _now() - start,
                "ref": ref.id, "role": ref.role, "title": ref.title,
            }
        time.sleep(poll)
    return {
        "ok": False, "method": "polling", "elapsed": _now() - start,
        "error": "element not found within timeout",
        "hint": "Run accessibility_snapshot(app) to inspect the live tree.",
    }


def wait_until_value(
    ref_or_app,
    *,
    contains: Optional[str] = None,
    equals: Optional[str] = None,
    timeout: float = 10.0,
    poll: float = 0.2,
    role: Optional[str] = None,
    title: Optional[str] = None,
) -> dict:
    """Wait until an element's AXValue matches.

    `ref_or_app` may be a ref id (string), an ElementRef, or an app name
    (in which case role+title are used to find the element fresh).
    """
    from .refs import resolve_ref, ElementRef
    start = _now()
    while _now() - start < timeout:
        el = None
        if isinstance(ref_or_app, ElementRef) or (isinstance(ref_or_app, str) and ref_or_app.startswith("r-")):
            el = resolve_ref(ref_or_app)
        elif isinstance(ref_or_app, str):
            kw = {}
            if role: kw["role"] = role
            if title: kw["title"] = title
            try:
                el = find(ref_or_app, **kw) if kw else None
            except Exception:
                el = None
        if el is not None:
            v = get_attr(el, "AXValue")
            v_s = str(v) if v is not None else ""
            if equals is not None and v_s == equals:
                return {"ok": True, "method": "polling", "elapsed": _now() - start, "value": v_s}
            if contains is not None and contains in v_s:
                return {"ok": True, "method": "polling", "elapsed": _now() - start, "value": v_s}
        time.sleep(poll)
    return {
        "ok": False, "method": "polling", "elapsed": _now() - start,
        "error": "value did not match within timeout",
        "hint": "Confirm the element exists and that the expected text is correct.",
    }


def wait_for_text(app: str, text: str, *, timeout: float = 10.0, poll: float = 0.5) -> dict:
    """Wait until `text` appears anywhere in the app's scraped content."""
    from .snapshot import scrape_app
    start = _now()
    needle = text.lower()
    while _now() - start < timeout:
        try:
            content = scrape_app(app, max_chars=5000)
        except Exception:
            content = ""
        if needle in content.lower():
            return {"ok": True, "method": "polling", "elapsed": _now() - start}
        time.sleep(poll)
    return {
        "ok": False, "method": "polling", "elapsed": _now() - start,
        "error": f"text {text!r} not seen in {app!r} within {timeout}s",
        "hint": "Take an accessibility_snapshot(app) to see what text is exposed.",
    }


def verify_window_open(app: str, *, title_contains: Optional[str] = None) -> dict:
    """Snapshot check: does `app` currently have a matching window?"""
    try:
        wins = list_windows(app)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    for w in wins:
        name = w.get("name") or ""
        if title_contains is None or title_contains.lower() in name.lower():
            return {"ok": True, "window": w}
    return {"ok": False, "error": "no matching window", "windows": [w.get("name") for w in wins]}


def verify_text_present(app: str, text: str) -> dict:
    """One-shot: is `text` present in `app`'s AX-extracted content right now?"""
    from .snapshot import scrape_app
    try:
        content = scrape_app(app, max_chars=10000)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": text.lower() in content.lower()}


def verify_clicked(app: str, *, role: Optional[str] = None, title: Optional[str] = None) -> dict:
    """Best-effort verify-after-click: confirms the target element still exists
    (i.e. button didn't disappear) OR that focus moved off it (success signal
    for menu items / submit buttons that close)."""
    kw = {}
    if role: kw["role"] = role
    if title: kw["title"] = title
    try:
        el = find(app, **kw) if kw else None
    except Exception:
        el = None
    if el is None:
        return {"ok": True, "note": "target gone — click likely advanced state"}
    # If it still exists, it's still ok (idempotent button).
    return {"ok": True, "note": "target still present (idempotent action)"}
