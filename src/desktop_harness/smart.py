"""Smart action engine — tiered, structured-result wrappers around clicking,
typing, setting values, and walking menus.

Tier order (each smart_* picks the relevant subset):
  1. ADAPTER       — app adapter native method, if registered
  2. AX_EXACT      — AX find by exact title/value
  3. AX_FUZZY      — AX find by title_contains / description / placeholder
  4. APPLESCRIPT   — `tell` for known scriptable apps (limited for click)
  5. KEYBOARD      — known shortcut / command palette
  6. OCR           — OCR full screen / app window, click pixel center
  7. VISION        — return a vision_act payload for the agent to handoff
  8. FAIL          — structured error with `tried` + hint

Every smart_* returns:
  {
    "ok": bool,
    "tier": <name of tier that won>,
    "tried": [<tiers attempted>],
    "target": <input>,
    "app": <input app>,
    "ref": <ElementRef.id, when AX won>,
    "screenshot_path": <only if vision/OCR was used>,
    "hint": <only on failure>,
    "error": <only on failure>,
  }

Native AX success path NEVER takes a screenshot.
"""
from __future__ import annotations

from typing import Any, Optional

from .ax import find, click_element, set_value, get_attr
from .apps import frontmost as _frontmost
from .vision import app_class as _app_class, ELECTRON_APPS  # noqa: F401
from .refs import create_element_ref


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _begin(target, app):
    return {
        "target": target if not isinstance(target, dict) else target.get("ref"),
        "app": app,
        "tried": [],
        "ok": False,
    }


def _win(out: dict, tier: str, **extra) -> dict:
    out["tier"] = tier
    out["ok"] = True
    out.update(extra)
    return out


def _fail(out: dict, error: str, hint: str) -> dict:
    out["tier"] = "fail"
    out["error"] = error
    out["hint"] = hint
    return out


def _resolve_target(target_or_ref, app: Optional[str]):
    """Accept either a string label, an ElementRef id like 'r-abcd1234', or an
    AXUIElement. Returns (element_or_none, label_or_none)."""
    from .refs import resolve_ref
    if isinstance(target_or_ref, str):
        if target_or_ref.startswith("r-"):
            el = resolve_ref(target_or_ref)
            return el, None
        return None, target_or_ref
    # Assume it's already an AXUIElement
    return target_or_ref, None


# ---------------------------------------------------------------------------
# smart_click
# ---------------------------------------------------------------------------

def smart_click(
    target,
    *,
    app: Optional[str] = None,
    case_insensitive: bool = True,
    use_vision_fallback: bool = True,
) -> dict:
    """Click the best match for `target`. Returns structured result.

    `target` can be:
      - a label string ("New Note")
      - an ElementRef id ("r-abc12345")
      - a raw AXUIElement (for advanced users)

    Skips AX tiers entirely for known Electron apps (saves ~2s per call).
    """
    out = _begin(target, app)
    el, label = _resolve_target(target, app)

    # Adapter tier
    if app and label:
        from . import adapters
        out["tried"].append("adapter")
        adapter = adapters.get_adapter(app)
        if adapter is not None and adapter.can_click(label):
            r = adapter.click(label)
            if r.get("ok"):
                return _win(out, "adapter", **{k: v for k, v in r.items() if k != "ok"})

    cls = _app_class(app) if app else "unknown"
    out["app_class"] = cls
    is_electron = cls == "electron"

    # Direct ref / element click
    if el is not None:
        out["tried"].append("ref_direct")
        if click_element(el):
            ref = create_element_ref(el, app=app)
            return _win(out, "ref_direct", ref=ref.id, role=ref.role, title=ref.title)

    # AX tiers (skip for Electron)
    if app and label and not is_electron:
        # Tier: AX_EXACT
        out["tried"].append("ax_title_exact")
        try:
            el = find(app, title=label)
        except Exception:
            el = None
        if el is not None and click_element(el):
            ref = create_element_ref(el, app=app)
            return _win(out, "ax_title_exact", ref=ref.id, role=ref.role, title=ref.title)

        # Tier: AX_FUZZY
        out["tried"].append("ax_title_contains")
        try:
            el = find(app, title_contains=label)
        except Exception:
            el = None
        if el is not None and click_element(el):
            ref = create_element_ref(el, app=app)
            return _win(out, "ax_title_contains", ref=ref.id, role=ref.role, title=ref.title)

        # Tier: AX_DESCRIBE
        out["tried"].append("ax_describe_match")
        for filt in ({"description": label}, {"placeholder": label}, {"identifier": label}):
            try:
                el = find(app, **filt)
            except Exception:
                el = None
            if el is not None and click_element(el):
                ref = create_element_ref(el, app=app)
                return _win(out, "ax_describe_match", ref=ref.id, role=ref.role, title=ref.title)

    if not label:
        return _fail(out, "Cannot click without a target label or live ref",
                     "Pass a string label or an existing ref id.")

    # Tier: OCR
    out["tried"].append("ocr_screen")
    try:
        from .ocr import find_text_on_screen
        from .input import click_at
        pt = find_text_on_screen(label, case_insensitive=case_insensitive)
        if pt is not None:
            click_at(pt[0], pt[1])
            return _win(out, "ocr_screen", coords=list(pt))
    except Exception as e:
        out["ocr_error"] = str(e)

    # Tier: VISION handoff
    if use_vision_fallback:
        out["tried"].append("vision_handoff")
        try:
            from .vision import vision_act
            v = vision_act(f"click '{label}'", app=app)
            out["vision"] = {
                "screenshot_path": v.get("screenshot", {}).get("path"),
                "recommendations": v.get("recommendations", []),
            }
            out["screenshot_path"] = v.get("screenshot", {}).get("path")
        except Exception as e:
            out["vision_error"] = str(e)

    return _fail(
        out,
        f"Could not click {label!r} in {app!r}",
        "Inspect accessibility_snapshot(app) for the available controls, "
        "or use the screenshot in `vision.screenshot_path` to choose visually.",
    )


# ---------------------------------------------------------------------------
# smart_type — focus a control then type text
# ---------------------------------------------------------------------------

def smart_type(
    target,
    text: str,
    *,
    app: Optional[str] = None,
    clear_first: bool = False,
) -> dict:
    """Focus a text control and type into it.

    Tier order:
      1. AX find + AXFocused=True + type via CGEvent
      2. Click the control via smart_click then type
    """
    from .ax import focus
    from .input import type_text, key
    from .refs import resolve_ref

    out = _begin(target, app)
    el, label = _resolve_target(target, app)

    # If a ref/element was given, focus it then type
    if el is not None:
        out["tried"].append("ax_focus")
        try:
            focused = focus(el)
        except Exception:
            focused = False
        if focused:
            if clear_first:
                key("cmd+a"); key("delete")
            type_text(text)
            ref = create_element_ref(el, app=app)
            return _win(out, "ax_focus", ref=ref.id, typed=text[:60])

    # If we have a label + app, find by AX then focus + type
    if app and label:
        out["tried"].append("ax_find_focus")
        try:
            el = find(app, title=label) or find(app, placeholder=label) or find(app, title_contains=label)
        except Exception:
            el = None
        if el is not None:
            try:
                focused = focus(el)
            except Exception:
                focused = False
            if focused:
                if clear_first:
                    key("cmd+a"); key("delete")
                type_text(text)
                ref = create_element_ref(el, app=app)
                return _win(out, "ax_find_focus", ref=ref.id, typed=text[:60])

        # Fallback: smart_click to focus, then type
        out["tried"].append("smart_click_then_type")
        click_res = smart_click(label, app=app)
        if click_res.get("ok"):
            if clear_first:
                key("cmd+a"); key("delete")
            type_text(text)
            return _win(out, "smart_click_then_type", clicked_via=click_res.get("tier"),
                        typed=text[:60])

    # Last resort — type into whatever's focused
    out["tried"].append("blind_type")
    type_text(text)
    return _win(out, "blind_type", typed=text[:60],
                note="No target focused — text went to the system-focused control.")


# ---------------------------------------------------------------------------
# smart_set_value — directly set AXValue (works for text fields, sliders, …)
# ---------------------------------------------------------------------------

def smart_set_value(target, value, *, app: Optional[str] = None) -> dict:
    """Set a control's AXValue directly. Faster than typing; works for any
    settable element (text fields, sliders, switches, popups in some apps)."""
    out = _begin(target, app)
    el, label = _resolve_target(target, app)

    if el is None and app and label:
        out["tried"].append("ax_find_for_set")
        try:
            el = find(app, title=label) or find(app, placeholder=label) or find(app, title_contains=label)
        except Exception:
            el = None

    if el is None:
        return _fail(out, "no element to set value on",
                     "Pass an ElementRef id or supply (app, label).")

    out["tried"].append("ax_set_value")
    if set_value(el, value):
        ref = create_element_ref(el, app=app)
        new_v = get_attr(el, "AXValue")
        return _win(out, "ax_set_value", ref=ref.id, value=str(new_v) if new_v is not None else None)

    # AX setValue refused — fall back to focus + type
    out["tried"].append("smart_type_fallback")
    return smart_type(el, str(value), app=app, clear_first=True)


# ---------------------------------------------------------------------------
# smart_menu — walk an app's menu bar, e.g. "File > New Folder"
# ---------------------------------------------------------------------------

def smart_menu(app: str, menu_path: str) -> dict:
    """Click through an app menu by path. `menu_path` uses '>' as separator,
    e.g. 'File > New Folder' or 'Edit > Find > Find Next'.

    Tier order:
      1. AX walk — find AXMenuBarItem by title, expand, find AXMenuItem,
         press. Most reliable for native apps.
      2. AppleScript — `tell` the app's menu via System Events for sandboxed
         menu commands.
    """
    from .apps import activate
    out = {"app": app, "menu_path": menu_path, "tried": [], "ok": False}

    parts = [p.strip() for p in menu_path.split(">") if p.strip()]
    if not parts:
        return _fail(out, "empty menu_path", "Use 'File > New Folder' format.")

    # Bring app forward — required for menu interaction
    try:
        activate(app)
    except Exception:
        pass

    # Tier 1: AX walk
    out["tried"].append("ax_menu_walk")
    try:
        from .ax import app_ax, children, get_attr as _ga
        root = app_ax(app)
        menu_bar = _ga(root, "AXMenuBar")
        if menu_bar is not None:
            current = menu_bar
            walked = []
            for i, name in enumerate(parts):
                next_el = None
                # Look at children, then their kids (menus), match by title
                for c in children(current):
                    t = _ga(c, "AXTitle")
                    if t is not None and str(t) == name:
                        next_el = c
                        break
                if next_el is None:
                    # Expand any menu containers and search again
                    for c in children(current):
                        for sub in children(c):
                            t = _ga(sub, "AXTitle")
                            if t is not None and str(t) == name:
                                next_el = sub
                                break
                        if next_el is not None:
                            break
                if next_el is None:
                    out["error"] = f"menu item not found: {name!r} (after {walked})"
                    out["hint"] = (
                        f"Use ax_dump({app!r}) to inspect the menu hierarchy. "
                        "Names are case-sensitive and may use special characters (… vs ...)."
                    )
                    return out
                walked.append(name)
                # If not the last, descend; else press
                if i < len(parts) - 1:
                    # Need to expand this submenu — perform AXShowMenu if available
                    try:
                        from .ax import perform_action
                        perform_action(next_el, "AXShowMenu")
                    except Exception:
                        pass
                    current = next_el
                else:
                    if click_element(next_el):
                        return _win(out, "ax_menu_walk", walked=walked)
                    out["error"] = f"could not press final menu item {name!r}"
                    return out
    except Exception as e:
        out["ax_error"] = str(e)

    # Tier 2: AppleScript
    out["tried"].append("applescript_menu")
    try:
        from .applescript import osascript
        # System Events click of nested menus is fiddly; supports up to 3 levels.
        if len(parts) == 2:
            top, item = parts
            script = (
                f'tell application "System Events" to tell process "{app}" '
                f'to click menu item "{item}" of menu "{top}" of menu bar 1'
            )
            osascript(script)
            return _win(out, "applescript_menu", walked=parts)
        if len(parts) == 3:
            top, mid, item = parts
            script = (
                f'tell application "System Events" to tell process "{app}" '
                f'to click menu item "{item}" of menu 1 of menu item "{mid}" of menu "{top}" of menu bar 1'
            )
            osascript(script)
            return _win(out, "applescript_menu", walked=parts)
    except Exception as e:
        out["applescript_error"] = str(e)

    return _fail(out, "menu walk failed",
                 f"Try `ax_dump({app!r})` to inspect the menu, or use osascript directly.")


# ---------------------------------------------------------------------------
# smart_open — launch an app or open a path
# ---------------------------------------------------------------------------

def smart_open(app_or_path: str, *, wait: float = 5.0) -> dict:
    """Launch an app by name OR open a file/folder path. Waits for the app
    to become running."""
    from .apps import open_app, is_running
    from .waiters import wait_for_app

    out: dict = {"target": app_or_path, "tried": []}
    is_path = "/" in app_or_path or app_or_path.startswith("~")

    if is_path:
        out["tried"].append("open_path")
        import subprocess, os
        path = os.path.expanduser(app_or_path)
        try:
            subprocess.run(["open", path], check=True, timeout=10)
            return _win(out, "open_path", path=path)
        except Exception as e:
            return _fail(out, f"open failed: {e}", "Verify the path exists and is readable.")

    out["tried"].append("open_app")
    try:
        open_app(app_or_path)
    except Exception as e:
        return _fail(out, f"open_app failed: {e}",
                     "Verify the app is installed; try `mdfind 'kMDItemKind == \"Application\"'`.")

    # Wait for it to come up
    if wait > 0:
        out["tried"].append("wait_for_app")
        w = wait_for_app(app_or_path, timeout=wait)
        if not w.get("ok"):
            return _fail(out, w.get("error", "did not start"), w.get("hint", ""))
        return _win(out, "open_app", elapsed=w.get("elapsed"))

    return _win(out, "open_app", waited=False) if is_running(app_or_path) else _fail(
        out, "did not become running", "Increase wait or check installation."
    )
