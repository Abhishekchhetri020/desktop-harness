"""App adapter registry.

An adapter is a small object that knows how to drive ONE app reliably,
hiding the AX/AppleScript/keyboard tier choice from callers. v0.5.0
ships three adapters: Finder, Notes, Mail.

Adapter contract:
  - .name           : canonical app name
  - .bundle_ids     : tuple of bundle ids it claims (used for matching)
  - .app_class      : "applescript" | "native_ax" | "electron" | "custom"
  - .actions()      : list[str] of all action names
  - .safe_actions   : tuple[str, ...] of read-only / reversible actions
  - .dangerous_actions : tuple[str, ...] of destructive actions
  - .can_click(label) -> bool
  - .click(label) -> dict
  - .perform(action, **kwargs) -> dict      (dispatch table)

Result dicts always carry: {ok, action, ...details}. Errors carry
{ok: False, error, hint}.
"""
from __future__ import annotations

from typing import Optional

from .base import Adapter
from .finder import FinderAdapter
from .notes import NotesAdapter
from .mail import MailAdapter


_REGISTRY: dict[str, Adapter] = {}


def register(adapter: Adapter) -> None:
    _REGISTRY[adapter.name] = adapter
    for bid in adapter.bundle_ids:
        _REGISTRY[bid] = adapter


def get_adapter(app: Optional[str]) -> Optional[Adapter]:
    if not app:
        return None
    if app in _REGISTRY:
        return _REGISTRY[app]
    # Case-insensitive name match
    low = app.lower()
    for k, v in _REGISTRY.items():
        if k.lower() == low:
            return v
    return None


def list_adapters() -> list[dict]:
    """Compact list of registered adapters (deduplicated by name)."""
    seen = set()
    out = []
    for v in _REGISTRY.values():
        if v.name in seen:
            continue
        seen.add(v.name)
        out.append({
            "name": v.name,
            "bundle_ids": list(v.bundle_ids),
            "app_class": v.app_class,
            "actions": list(v.actions()),
            "safe_actions": list(v.safe_actions),
            "dangerous_actions": list(v.dangerous_actions),
        })
    return out


def adapter_actions(app: str) -> dict:
    """Compact description of the actions an adapter exposes."""
    a = get_adapter(app)
    if a is None:
        return {
            "ok": False,
            "error": f"no adapter registered for app {app!r}",
            "hint": "Use the generic smart_click / smart_type / smart_menu instead, "
                    "or register an adapter via desktop_harness.adapters.register()."
        }
    return {
        "ok": True,
        "name": a.name,
        "app_class": a.app_class,
        "actions": list(a.actions()),
        "safe_actions": list(a.safe_actions),
        "dangerous_actions": list(a.dangerous_actions),
    }


def perform_adapter_action(app: str, action: str, **kwargs) -> dict:
    """Dispatch into the adapter's `perform()`."""
    a = get_adapter(app)
    if a is None:
        return {"ok": False, "error": f"no adapter for {app!r}",
                "hint": "Use the generic smart_* primitives or register an adapter."}
    return a.perform(action, **kwargs)


# Register built-ins
for _adapter in (FinderAdapter(), NotesAdapter(), MailAdapter()):
    register(_adapter)


__all__ = [
    "Adapter", "register", "get_adapter", "list_adapters",
    "adapter_actions", "perform_adapter_action",
    "FinderAdapter", "NotesAdapter", "MailAdapter",
]
