"""Accessibility (AX) tree — the DOM equivalent for native macOS apps.

Every native app exposes an AXUIElement tree. We can:
  - Walk it (children, parent, descendants)
  - Find elements by role / title / value / placeholder / identifier
  - Read attributes (position, size, value, focused, enabled)
  - Press buttons, set text values, open menu items — without pixel coords

This is what makes desktop-harness more reliable than pixel-driving.
"""
from __future__ import annotations
from typing import Any, Optional

from ApplicationServices import (
    AXUIElementCreateApplication,
    AXUIElementCreateSystemWide,
    AXUIElementCopyAttributeValue,
    AXUIElementCopyAttributeNames,
    AXUIElementSetAttributeValue,
    AXUIElementPerformAction,
    AXUIElementCopyActionNames,
    AXIsProcessTrustedWithOptions,
    kAXErrorSuccess,
    kAXErrorAttributeUnsupported,
    kAXErrorNoValue,
    kAXTitleAttribute,
    kAXRoleAttribute,
    kAXSubroleAttribute,
    kAXValueAttribute,
    kAXChildrenAttribute,
    kAXParentAttribute,
    kAXFocusedAttribute,
    kAXFocusedUIElementAttribute,
    kAXPositionAttribute,
    kAXSizeAttribute,
    kAXEnabledAttribute,
    kAXDescriptionAttribute,
    kAXHelpAttribute,
    kAXIdentifierAttribute,
    kAXPlaceholderValueAttribute,
    kAXSelectedTextAttribute,
    kAXWindowsAttribute,
    kAXMainWindowAttribute,
    kAXFocusedWindowAttribute,
    kAXMenuBarAttribute,
    kAXPressAction,
    kAXShowMenuAction,
)
from .apps import pid_of


class AXError(Exception):
    pass


def app_ax(name_or_bundle: str):
    """AX root element of an app (must be running)."""
    pid = pid_of(name_or_bundle)
    if pid is None:
        raise AXError(f"app not running: {name_or_bundle!r}")
    return AXUIElementCreateApplication(pid)


def system_wide():
    """System-wide AX element. Used for focused_element() across apps."""
    return AXUIElementCreateSystemWide()


def get_attr(element, attr: str, default=None):
    """Read a single attribute. Returns default on missing."""
    try:
        err, val = AXUIElementCopyAttributeValue(element, attr, None)
    except Exception:
        return default
    if err == kAXErrorSuccess:
        return val
    return default


def set_value(element, value) -> bool:
    """Set kAXValueAttribute on an element (text fields, sliders)."""
    err = AXUIElementSetAttributeValue(element, kAXValueAttribute, value)
    return err == kAXErrorSuccess


def perform_action(element, action: str = "AXPress") -> bool:
    """Perform an action on an element (default = press/click).
    Common actions: AXPress, AXShowMenu, AXIncrement, AXDecrement, AXConfirm, AXCancel."""
    err = AXUIElementPerformAction(element, action)
    return err == kAXErrorSuccess


def click_element(element) -> bool:
    """Press an element via AX (no pixel coords needed)."""
    return perform_action(element, kAXPressAction)


def get_attrs(element) -> dict:
    """All readable attributes as a dict."""
    out = {}
    try:
        err, names = AXUIElementCopyAttributeNames(element, None)
    except Exception:
        return out
    if err != kAXErrorSuccess or names is None:
        return out
    for n in names:
        v = get_attr(element, n)
        if v is not None:
            out[str(n)] = v
    return out


def role(element) -> str | None:
    r = get_attr(element, kAXRoleAttribute)
    return str(r) if r else None


def title(element) -> str | None:
    t = get_attr(element, kAXTitleAttribute)
    return str(t) if t else None


def get_value(element):
    return get_attr(element, kAXValueAttribute)


def position(element) -> tuple[float, float] | None:
    """Element's screen position (x, y) in points."""
    from AppKit import NSValue
    p = get_attr(element, kAXPositionAttribute)
    if p is None:
        return None
    try:
        # AXValue holds a CGPoint; cast via objc
        import objc
        from CoreFoundation import CFGetTypeID
        from ApplicationServices import AXValueGetValue, kAXValueCGPointType
        ok, point = AXValueGetValue(p, kAXValueCGPointType, None)
        if ok:
            return (float(point.x), float(point.y))
    except Exception:
        return None
    return None


def size(element) -> tuple[float, float] | None:
    s = get_attr(element, kAXSizeAttribute)
    if s is None:
        return None
    try:
        from ApplicationServices import AXValueGetValue, kAXValueCGSizeType
        ok, sz = AXValueGetValue(s, kAXValueCGSizeType, None)
        if ok:
            return (float(sz.width), float(sz.height))
    except Exception:
        return None
    return None


def parent(element):
    return get_attr(element, kAXParentAttribute)


def children(element) -> list:
    c = get_attr(element, kAXChildrenAttribute)
    return list(c) if c else []


def descendants(element, *, max_depth: int = 30):
    """Yield (element, depth) for every descendant."""
    stack = [(element, 0)]
    while stack:
        el, d = stack.pop()
        yield el, d
        if d >= max_depth:
            continue
        for c in reversed(children(el)):
            stack.append((c, d + 1))


def focused_element():
    """The element currently focused, system-wide."""
    return get_attr(system_wide(), kAXFocusedUIElementAttribute)


def focus(element) -> bool:
    """Give an element keyboard focus."""
    err = AXUIElementSetAttributeValue(element, kAXFocusedAttribute, True)
    return err == kAXErrorSuccess


def _matches(el, *, role=None, subrole=None, title=None, value=None,
             identifier=None, placeholder=None, description=None,
             title_contains=None, value_contains=None) -> bool:
    if role is not None:
        r = get_attr(el, kAXRoleAttribute)
        if r is None or str(r) != role:
            return False
    if subrole is not None:
        s = get_attr(el, kAXSubroleAttribute)
        if s is None or str(s) != subrole:
            return False
    if title is not None:
        t = get_attr(el, kAXTitleAttribute)
        if t is None or str(t) != title:
            return False
    if title_contains is not None:
        t = get_attr(el, kAXTitleAttribute)
        if t is None or title_contains.lower() not in str(t).lower():
            return False
    if value is not None:
        v = get_attr(el, kAXValueAttribute)
        if v is None or str(v) != value:
            return False
    if value_contains is not None:
        v = get_attr(el, kAXValueAttribute)
        if v is None or value_contains.lower() not in str(v).lower():
            return False
    if identifier is not None:
        i = get_attr(el, kAXIdentifierAttribute)
        if i is None or str(i) != identifier:
            return False
    if placeholder is not None:
        p = get_attr(el, kAXPlaceholderValueAttribute)
        if p is None or str(p) != placeholder:
            return False
    if description is not None:
        d = get_attr(el, kAXDescriptionAttribute)
        if d is None or str(d) != description:
            return False
    return True


def find(app_or_element, *, role=None, subrole=None, title=None, value=None,
         identifier=None, placeholder=None, description=None,
         title_contains=None, value_contains=None,
         max_depth: int = 25):
    """Find the FIRST element matching all given filters. BFS by default
    (so the topmost match wins). app_or_element can be an app name string
    OR an AXUIElement to search under."""
    root = app_ax(app_or_element) if isinstance(app_or_element, str) else app_or_element
    queue = [(root, 0)]
    seen = 0
    while queue:
        el, d = queue.pop(0)
        seen += 1
        if _matches(el, role=role, subrole=subrole, title=title, value=value,
                    identifier=identifier, placeholder=placeholder,
                    description=description, title_contains=title_contains,
                    value_contains=value_contains):
            return el
        if d < max_depth:
            for c in children(el):
                queue.append((c, d + 1))
    return None


def find_all(app_or_element, *, role=None, subrole=None, title=None, value=None,
             identifier=None, placeholder=None, description=None,
             title_contains=None, value_contains=None,
             max_depth: int = 25, limit: int = 100):
    """Find ALL elements matching filters."""
    root = app_ax(app_or_element) if isinstance(app_or_element, str) else app_or_element
    out = []
    queue = [(root, 0)]
    while queue and len(out) < limit:
        el, d = queue.pop(0)
        if _matches(el, role=role, subrole=subrole, title=title, value=value,
                    identifier=identifier, placeholder=placeholder,
                    description=description, title_contains=title_contains,
                    value_contains=value_contains):
            out.append(el)
        if d < max_depth:
            for c in children(el):
                queue.append((c, d + 1))
    return out


def ax_tree(app_or_element, *, max_depth: int = 8, max_per_level: int = 50) -> dict:
    """Snapshot the AX tree as nested dicts. Trimmed for readability."""
    root = app_ax(app_or_element) if isinstance(app_or_element, str) else app_or_element

    def _node(el, d):
        n = {
            "role": str(get_attr(el, kAXRoleAttribute) or ""),
            "title": str(get_attr(el, kAXTitleAttribute) or "") or None,
            "value": _short(get_attr(el, kAXValueAttribute)),
            "identifier": str(get_attr(el, kAXIdentifierAttribute) or "") or None,
        }
        if d < max_depth:
            kids = children(el)[:max_per_level]
            if kids:
                n["children"] = [_node(c, d + 1) for c in kids]
        return {k: v for k, v in n.items() if v not in (None, "", [])}

    return _node(root, 0)


def _short(v) -> str | None:
    if v is None:
        return None
    s = str(v)
    if len(s) > 80:
        return s[:80] + "…"
    return s or None


def ax_dump(app_or_element, *, max_depth: int = 6, indent: int = 0) -> str:
    """Pretty-print the AX tree as text."""
    root = app_ax(app_or_element) if isinstance(app_or_element, str) else app_or_element
    lines = []

    def walk(el, d):
        r = get_attr(el, kAXRoleAttribute) or ""
        t = get_attr(el, kAXTitleAttribute)
        v = _short(get_attr(el, kAXValueAttribute))
        idn = get_attr(el, kAXIdentifierAttribute)
        bits = [str(r)]
        if t:
            bits.append(f'title={t!r}')
        if v:
            bits.append(f'value={v!r}')
        if idn:
            bits.append(f'id={idn!r}')
        lines.append("  " * d + " ".join(bits))
        if d < max_depth:
            for c in children(el):
                walk(c, d + 1)

    walk(root, indent)
    return "\n".join(lines)
