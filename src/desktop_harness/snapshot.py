"""Accessibility snapshot — one-shot JSON of every interactive element in an app.

The macOS-MCP / Playwright-MCP "headline" feature: a compact, structured view
of the UI that's tiny enough to fit in an LLM context window AND rich enough
that the agent can pick the right element by ref without screenshots.

Each element gets a stable reference (`ax_<id>`) that you can pass to the
existing `ax_click` / `ax_get_value` / `ax_set_value` MCP tools.
"""
from __future__ import annotations

import threading
from typing import Optional

from .ax import (
    app_ax,
    children,
    get_attr,
    AXError,
)


# Roles considered "interactive" — clickable / typable / settable
INTERACTIVE_ROLES = frozenset({
    "AXButton",
    "AXMenuButton",
    "AXMenuItem",
    "AXMenuBarItem",
    "AXMenuBarExtra",
    "AXTextField",
    "AXTextArea",
    "AXSearchField",
    "AXSecureTextField",
    "AXComboBox",
    "AXPopUpButton",
    "AXCheckBox",
    "AXRadioButton",
    "AXSlider",
    "AXSwitch",
    "AXTabGroup",
    "AXTab",
    "AXLink",
    "AXCell",
    "AXRow",
    "AXOutline",
    "AXList",
    "AXGroup",  # often holds important content
    "AXIncrementor",
    "AXDecrementor",
    "AXColorWell",
    "AXImage",  # only if it has a title/help
    "AXStaticText",  # only if non-empty
})


# Container roles we walk through but don't include
CONTAINER_ROLES = frozenset({
    "AXApplication",
    "AXWindow",
    "AXScrollArea",
    "AXSplitGroup",
    "AXLayoutArea",
    "AXSheet",
    "AXDrawer",
    "AXToolbar",
    "AXMenuBar",
    "AXMenu",
})


_REGISTRY: dict[str, object] = {}
_LOCK = threading.Lock()
_NEXT = 0


def _register(el) -> str:
    global _NEXT
    with _LOCK:
        _NEXT += 1
        ref = f"ax_{_NEXT}"
        _REGISTRY[ref] = el
        return ref


def lookup_ref(ref: str):
    """Resolve a ref to its AX element. Returns None if unknown."""
    return _REGISTRY.get(ref)


def clear_refs() -> int:
    """Drop all registered refs. Returns the count freed."""
    with _LOCK:
        n = len(_REGISTRY)
        _REGISTRY.clear()
        return n


def _short(v, limit: int = 80) -> Optional[str]:
    if v is None:
        return None
    s = str(v)
    if not s:
        return None
    if len(s) > limit:
        return s[:limit] + "…"
    return s


def _describe(el, ref: str) -> dict:
    """Compact description of one element. Optimized for LLM tokens."""
    out: dict = {"ref": ref}
    role = get_attr(el, "AXRole")
    if role:
        out["role"] = str(role)
    sub = get_attr(el, "AXSubrole")
    if sub:
        out["subrole"] = str(sub)
    title = _short(get_attr(el, "AXTitle"))
    if title:
        out["title"] = title
    value = _short(get_attr(el, "AXValue"))
    if value:
        out["value"] = value
    placeholder = _short(get_attr(el, "AXPlaceholderValue"))
    if placeholder:
        out["placeholder"] = placeholder
    desc = _short(get_attr(el, "AXDescription"))
    if desc:
        out["description"] = desc
    help_ = _short(get_attr(el, "AXHelp"))
    if help_:
        out["help"] = help_
    ident = get_attr(el, "AXIdentifier")
    if ident:
        out["id"] = str(ident)
    enabled = get_attr(el, "AXEnabled")
    if enabled is False:
        out["disabled"] = True
    return out


def accessibility_snapshot(
    app_name: str,
    *,
    max_depth: int = 30,
    max_elements: int = 500,
    interactive_only: bool = True,
    include_static_text: bool = True,
) -> dict:
    """Walk the AX tree of an app and return a compact JSON snapshot.

    Each interactive element gets a stable ref like "ax_42" that you can pass
    to ax_click / ax_get_value / ax_set_value via the MCP server.

    Output shape:
        {
          "app": "Notes",
          "summary": {"interactive": 42, "windows": 1, "menus": 8},
          "tree": [
            {"ref": "ax_1", "role": "AXWindow", "title": "Untitled",
             "children": [
                {"ref": "ax_2", "role": "AXButton", "title": "New Note"},
                ...
             ]},
            ...
          ]
        }
    """
    root = app_ax(app_name)

    counters = {"interactive": 0, "windows": 0, "menus": 0, "static_text": 0, "total": 0}

    def walk(el, depth: int) -> Optional[dict]:
        if counters["total"] >= max_elements:
            return None
        counters["total"] += 1

        role = str(get_attr(el, "AXRole") or "")
        is_window = role == "AXWindow"
        is_menu_item = role in ("AXMenuItem", "AXMenuBarItem")
        is_static = role == "AXStaticText"

        if is_window:
            counters["windows"] += 1
        if is_menu_item:
            counters["menus"] += 1

        # Decide whether to include this node in output.
        include_self = (
            (role in INTERACTIVE_ROLES)
            or (role in CONTAINER_ROLES and role in ("AXWindow", "AXSheet", "AXDrawer", "AXToolbar"))
        )
        if interactive_only and not include_self:
            include_self = False
        if is_static and not include_static_text:
            include_self = False
        if is_static and include_static_text:
            v = get_attr(el, "AXValue")
            if not v or not str(v).strip():
                include_self = False

        # Walk kids
        kids: list[dict] = []
        if depth < max_depth:
            for c in children(el):
                node = walk(c, depth + 1)
                if node:
                    kids.append(node)

        if not include_self and not kids:
            return None
        if not include_self and kids and len(kids) == 1:
            # Collapse pure container with a single child
            return kids[0]

        node: dict = _describe(el, _register(el)) if include_self else {"role": role}
        if include_self and role in INTERACTIVE_ROLES:
            counters["interactive"] += 1
        if is_static:
            counters["static_text"] += 1
        if kids:
            node["children"] = kids
        return node

    root_kids = []
    for c in children(root):
        n = walk(c, 0)
        if n:
            root_kids.append(n)

    return {
        "app": app_name,
        "summary": {
            "interactive": counters["interactive"],
            "windows": counters["windows"],
            "menus": counters["menus"],
            "static_text": counters["static_text"],
            "total_walked": counters["total"],
            "truncated_at_max_elements": counters["total"] >= max_elements,
        },
        "tree": root_kids,
    }


def click_text(needle: str, *, app: Optional[str] = None, case_insensitive: bool = True) -> bool:
    """Hybrid AX→OCR text-to-action.

    Strategy:
      1. If app is given, search its AX tree for an element whose title/value
         contains `needle` and click it via AX (no pixel coords).
      2. Otherwise, OCR the screen and click the pixel center of the matched text.
    """
    if app is not None:
        from .ax import find, click_element
        for filt_kwargs in (
            {"title_contains": needle},
            {"value_contains": needle},
        ):
            el = find(app, **filt_kwargs)
            if el is not None:
                return click_element(el)
    # OCR fallback
    from .ocr import find_text_on_screen
    from .input import click_at
    pt = find_text_on_screen(needle, case_insensitive=case_insensitive)
    if pt is None:
        return False
    click_at(pt[0], pt[1])
    return True


def scrape_app(app_name: str, *, max_depth: int = 30, max_chars: int = 50000) -> str:
    """Extract all visible text from an app as a Markdown-ish string.

    Walks the AX tree. Headings come from window/group titles, paragraphs from
    AXStaticText, list items from AXMenuItem.
    """
    root = app_ax(app_name)
    out: list[str] = [f"# {app_name}\n"]
    chars = len(out[0])

    def visit(el, depth: int):
        nonlocal chars
        if chars >= max_chars:
            return
        role = str(get_attr(el, "AXRole") or "")
        title = get_attr(el, "AXTitle")
        value = get_attr(el, "AXValue")

        if role == "AXWindow" and title:
            line = f"\n## {title}\n"
            out.append(line); chars += len(line)
        elif role in ("AXGroup", "AXSplitGroup", "AXTabGroup") and title:
            line = f"\n### {title}\n"
            out.append(line); chars += len(line)
        elif role == "AXStaticText" and value:
            line = str(value).strip()
            if line:
                out.append(line + "\n"); chars += len(line) + 1
        elif role in ("AXTextField", "AXTextArea") and value:
            v = str(value).strip()
            if v:
                line = f"\n```\n{v[:5000]}\n```\n"
                out.append(line); chars += len(line)
        elif role in ("AXMenuItem", "AXMenuBarItem") and title:
            line = f"- {title}\n"
            out.append(line); chars += len(line)

        if depth < max_depth:
            for c in children(el):
                visit(c, depth + 1)

    for c in children(root):
        visit(c, 0)

    text = "".join(out)
    if chars >= max_chars:
        text += f"\n\n_(truncated at {max_chars} chars)_"
    return text


def batch_actions(actions: list[dict]) -> list[dict]:
    """Run a list of actions in sequence. Each action: {"action": "name", **kwargs}.

    Stops on first failure unless action has "continue_on_error": true.
    Returns per-action result dicts.

    Supported actions: click, double_click, right_click, type_text, key_press,
    scroll, mouse_move, ax_click, ax_set_value, sleep, screenshot.
    """
    import time
    from .input import click_at, double_click_at, right_click_at, type_text, key, scroll, mouse_move
    from .ax import click_element, set_value
    from .screen import screenshot

    results = []
    for i, a in enumerate(actions):
        name = a.get("action")
        try:
            if name == "click":
                click_at(a["x"], a["y"]); r = {"ok": True}
            elif name == "double_click":
                double_click_at(a["x"], a["y"]); r = {"ok": True}
            elif name == "right_click":
                right_click_at(a["x"], a["y"]); r = {"ok": True}
            elif name == "type_text":
                type_text(a["text"], delay=a.get("delay", 0.005)); r = {"ok": True}
            elif name == "key_press":
                key(a["chord"], count=a.get("count", 1)); r = {"ok": True}
            elif name == "scroll":
                scroll(dy=a.get("dy", 0), dx=a.get("dx", 0), x=a.get("x"), y=a.get("y")); r = {"ok": True}
            elif name == "mouse_move":
                mouse_move(a["x"], a["y"]); r = {"ok": True}
            elif name == "ax_click":
                el = lookup_ref(a["ref"])
                if el is None:
                    raise AXError(f"unknown ref: {a['ref']}")
                r = {"ok": click_element(el)}
            elif name == "ax_set_value":
                el = lookup_ref(a["ref"])
                if el is None:
                    raise AXError(f"unknown ref: {a['ref']}")
                r = {"ok": set_value(el, a["value"])}
            elif name == "sleep":
                time.sleep(a.get("seconds", 0.5)); r = {"ok": True}
            elif name == "screenshot":
                r = {"ok": True, "path": screenshot(a.get("path"))}
            else:
                r = {"ok": False, "error": f"unknown action: {name}"}
        except Exception as e:  # noqa: BLE001
            r = {"ok": False, "error": str(e)}
        r["action"] = name
        r["index"] = i
        results.append(r)
        if not r.get("ok") and not a.get("continue_on_error"):
            break
    return results
