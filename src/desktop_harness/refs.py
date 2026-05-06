"""Stable element references.

Why this module exists:
  v0.4 refs (`ax_42`) were just integer counters into a process-local dict.
  When the AXUIElement handle went stale (window closed, view recycled),
  the ref became dead and the agent had to take a fresh snapshot.

  v0.5 refs are STRUCTURED FINGERPRINTS. They include enough metadata
  (app + bundle + role + title + path-from-root + index + frame) that we
  can re-resolve the element from scratch by walking the live AX tree
  when the cached handle is stale. Playwright's locator pattern, applied
  to macOS.

Key types:
  - ElementRef       : dataclass holding the fingerprint + cached handle
  - create_element_ref(el, app=None) -> ElementRef
  - resolve_ref(ref) -> AXUIElement | None        (cached then re-find)
  - refresh_ref(ref) -> ElementRef                (returns a new ref)
  - re_find_element(ref) -> AXUIElement | None   (always re-walks tree)
  - is_stale(ref) -> bool

Refs are hashable, JSON-serialisable (via .to_dict / from_dict), and have
short string IDs (`r-<8hex>`) for use in MCP responses + logs.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from .ax import (
    app_ax,
    children,
    get_attr,
    role as _role,
    title as _title,
    position,
    size,
)
from .apps import app_info, frontmost


# ---------------------------------------------------------------------------
# ElementRef dataclass
# ---------------------------------------------------------------------------

@dataclass
class ElementRef:
    """Structured fingerprint of an AX element.

    `path` is the chain of (role, index_among_siblings_with_same_role)
    pairs from app root to this element. Enables deterministic re-find.
    """
    id: str                                    # short hex id (r-<8hex>)
    app: str                                   # app name as the user calls it
    bundle_id: Optional[str] = None
    pid: Optional[int] = None
    role: Optional[str] = None
    subrole: Optional[str] = None
    title: Optional[str] = None
    value_snippet: Optional[str] = None
    identifier: Optional[str] = None           # AXIdentifier (most stable)
    placeholder: Optional[str] = None
    description: Optional[str] = None
    help: Optional[str] = None
    path: list[tuple[str, int]] = field(default_factory=list)   # [("AXWindow", 0), ("AXButton", 3)]
    frame: Optional[tuple[float, float, float, float]] = None    # (x, y, w, h)
    ts: float = field(default_factory=time.time)
    fingerprint: str = ""                      # sha1 of stable bits

    def to_dict(self) -> dict:
        d = asdict(self)
        # Tuples become lists in JSON; preserve as lists for symmetry
        d["path"] = [list(p) for p in self.path]
        if self.frame is not None:
            d["frame"] = list(self.frame)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ElementRef":
        kw = dict(d)
        kw["path"] = [tuple(p) for p in kw.get("path", [])]
        if kw.get("frame") is not None:
            kw["frame"] = tuple(kw["frame"])
        return cls(**kw)


# ---------------------------------------------------------------------------
# Process-local registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, tuple[ElementRef, object]] = {}
_LOCK = threading.RLock()


def _short_id(fingerprint: str) -> str:
    return f"r-{fingerprint[:8]}"


def _stable_fingerprint(app: str, bundle_id: Optional[str], role_: Optional[str],
                        title_: Optional[str], identifier: Optional[str],
                        path: list[tuple[str, int]]) -> str:
    """SHA1 over the bits least likely to change frame-to-frame.
    Excludes value, frame, ts."""
    blob = json.dumps(
        [app, bundle_id or "", role_ or "", title_ or "",
         identifier or "", [list(p) for p in path]],
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def _index_among_siblings(parent_el, child_el, role_: str) -> int:
    """Position of child_el among siblings with the same role.
    Returns 0 if not found (best-effort)."""
    try:
        sibs = children(parent_el)
    except Exception:
        return 0
    same_role = []
    for s in sibs:
        try:
            r = get_attr(s, "AXRole")
            if str(r) == role_:
                same_role.append(s)
        except Exception:
            continue
    for i, s in enumerate(same_role):
        if s is child_el:
            return i
    return 0


def _build_path(el, root) -> list[tuple[str, int]]:
    """Walk parent chain from el up to root, capturing (role, sibling-index)."""
    path: list[tuple[str, int]] = []
    cur = el
    safety = 64
    while cur is not None and cur is not root and safety > 0:
        safety -= 1
        try:
            parent_el = get_attr(cur, "AXParent")
        except Exception:
            parent_el = None
        if parent_el is None:
            break
        cur_role = str(get_attr(cur, "AXRole") or "")
        idx = _index_among_siblings(parent_el, cur, cur_role)
        path.append((cur_role, idx))
        cur = parent_el
    path.reverse()
    return path


def _frame(el) -> Optional[tuple[float, float, float, float]]:
    p = position(el)
    s = size(el)
    if p is None or s is None:
        return None
    return (p[0], p[1], s[0], s[1])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_element_ref(element, app: Optional[str] = None) -> ElementRef:
    """Build a stable fingerprint for an AX element + cache its handle."""
    if app is None:
        # Try to recover app name via the AX root attribute chain
        cur = element
        for _ in range(64):
            try:
                role_ = get_attr(cur, "AXRole")
            except Exception:
                role_ = None
            if str(role_) == "AXApplication":
                app = str(get_attr(cur, "AXTitle") or "") or None
                break
            try:
                cur = get_attr(cur, "AXParent")
            except Exception:
                cur = None
            if cur is None:
                break
    if app is None:
        fm = frontmost() or {}
        app = fm.get("name")

    info = app_info(app) if app else None
    bundle_id = info.get("bundle_id") if info else None
    pid = info.get("pid") if info else None

    role_ = _role(element)
    subrole = get_attr(element, "AXSubrole")
    title_ = _title(element)
    val = get_attr(element, "AXValue")
    val_snip = (str(val)[:80] + "…") if val and len(str(val)) > 80 else (str(val) if val else None)
    identifier = get_attr(element, "AXIdentifier")
    placeholder = get_attr(element, "AXPlaceholderValue")
    description = get_attr(element, "AXDescription")
    help_ = get_attr(element, "AXHelp")

    root = app_ax(app) if app else None
    path = _build_path(element, root) if root is not None else []
    fp = _stable_fingerprint(app or "", bundle_id, role_, title_,
                             str(identifier) if identifier else None, path)

    ref = ElementRef(
        id=_short_id(fp),
        app=app or "",
        bundle_id=bundle_id,
        pid=pid,
        role=role_,
        subrole=str(subrole) if subrole else None,
        title=title_,
        value_snippet=val_snip,
        identifier=str(identifier) if identifier else None,
        placeholder=str(placeholder) if placeholder else None,
        description=str(description) if description else None,
        help=str(help_) if help_ else None,
        path=path,
        frame=_frame(element),
        fingerprint=fp,
    )

    with _LOCK:
        _REGISTRY[ref.id] = (ref, element)
    return ref


def get_ref(ref_id: str) -> Optional[ElementRef]:
    """Look up an ElementRef by its short id."""
    with _LOCK:
        entry = _REGISTRY.get(ref_id)
    return entry[0] if entry else None


def resolve_ref(ref_or_id, *, allow_refind: bool = True):
    """Resolve a ref (object or id) to a live AXUIElement, re-finding if stale.

    Returns the element on success, None if the element cannot be found.
    """
    ref = ref_or_id if isinstance(ref_or_id, ElementRef) else get_ref(ref_or_id)
    if ref is None:
        return None
    with _LOCK:
        entry = _REGISTRY.get(ref.id)
    cached = entry[1] if entry else None
    if cached is not None and not _is_stale_handle(cached, ref):
        return cached
    if not allow_refind:
        return None
    fresh = re_find_element(ref)
    if fresh is not None:
        with _LOCK:
            _REGISTRY[ref.id] = (ref, fresh)
    return fresh


def is_stale(ref_or_id) -> bool:
    """True if the cached handle no longer matches the fingerprint."""
    ref = ref_or_id if isinstance(ref_or_id, ElementRef) else get_ref(ref_or_id)
    if ref is None:
        return True
    with _LOCK:
        entry = _REGISTRY.get(ref.id)
    if entry is None:
        return True
    return _is_stale_handle(entry[1], ref)


def _is_stale_handle(el, ref: ElementRef) -> bool:
    """Cheap probe: read role+title from the cached handle and compare to the ref."""
    try:
        r = get_attr(el, "AXRole")
        if r is None:
            return True
        if ref.role is not None and str(r) != ref.role:
            return True
        if ref.title is not None:
            t = get_attr(el, "AXTitle")
            if t is None or str(t) != ref.title:
                return True
        return False
    except Exception:
        return True


def re_find_element(ref_or_id):
    """Re-walk the app's AX tree to find an element matching the ref.

    Strategy (best-effort, in order):
      1. Path replay: walk from app root using ref.path indices.
      2. AXIdentifier + role match: most stable single attribute when present.
      3. Role + title exact.
      4. Role + title_contains.
    """
    ref = ref_or_id if isinstance(ref_or_id, ElementRef) else get_ref(ref_or_id)
    if ref is None or not ref.app:
        return None
    try:
        root = app_ax(ref.app)
    except Exception:
        return None

    # 1. Path replay
    if ref.path:
        cur = root
        for r_role, idx in ref.path:
            try:
                same_role = [c for c in children(cur)
                             if str(get_attr(c, "AXRole") or "") == r_role]
            except Exception:
                same_role = []
            if not same_role or idx >= len(same_role):
                cur = None
                break
            cur = same_role[idx]
        if cur is not None:
            # Sanity: title or identifier matches if we have one
            if ref.title:
                t = get_attr(cur, "AXTitle")
                if t is not None and str(t) == ref.title:
                    return cur
            elif ref.identifier:
                i = get_attr(cur, "AXIdentifier")
                if i is not None and str(i) == ref.identifier:
                    return cur
            else:
                return cur

    # 2. By identifier
    if ref.identifier:
        from .ax import find
        try:
            el = find(ref.app, identifier=ref.identifier, role=ref.role)
            if el is not None:
                return el
        except Exception:
            pass

    # 3. By role + title exact
    if ref.role and ref.title:
        from .ax import find
        try:
            el = find(ref.app, role=ref.role, title=ref.title)
            if el is not None:
                return el
        except Exception:
            pass

    # 4. By role + title_contains
    if ref.role and ref.title:
        from .ax import find
        try:
            el = find(ref.app, role=ref.role, title_contains=ref.title[:32])
            if el is not None:
                return el
        except Exception:
            pass

    return None


def refresh_ref(ref_or_id) -> Optional[ElementRef]:
    """Re-find the element AND issue a freshly-built ref for it.

    Returns the new ref (with same .id as original if fingerprint unchanged,
    or a different id if the element's stable bits drifted), or None if the
    element can no longer be found.
    """
    ref = ref_or_id if isinstance(ref_or_id, ElementRef) else get_ref(ref_or_id)
    if ref is None:
        return None
    el = re_find_element(ref)
    if el is None:
        return None
    return create_element_ref(el, app=ref.app)


def describe_element(element, app: Optional[str] = None) -> dict:
    """Compact dict description of an element. Used in snapshots + tests."""
    ref = create_element_ref(element, app)
    return {
        "ref": ref.id,
        "role": ref.role,
        "subrole": ref.subrole,
        "title": ref.title,
        "value": ref.value_snippet,
        "id": ref.identifier,
        "placeholder": ref.placeholder,
        "description": ref.description,
    }


def element_bounds(element):
    """(x, y, w, h) of an AX element, or None."""
    return _frame(element)


def clear_refs() -> int:
    """Drop all registered refs. Returns count freed."""
    with _LOCK:
        n = len(_REGISTRY)
        _REGISTRY.clear()
    return n


def list_refs() -> list[dict]:
    """List every active ref (compact form). Diagnostics use only."""
    with _LOCK:
        return [r.to_dict() for r, _ in _REGISTRY.values()]
