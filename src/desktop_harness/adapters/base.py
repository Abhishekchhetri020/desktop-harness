"""Adapter base class + helpers."""
from __future__ import annotations

from typing import Any


class Adapter:
    """Subclass and override. See FinderAdapter / NotesAdapter / MailAdapter."""
    name: str = ""
    bundle_ids: tuple[str, ...] = ()
    app_class: str = "native_ax"
    safe_actions: tuple[str, ...] = ()
    dangerous_actions: tuple[str, ...] = ()

    def actions(self) -> list[str]:
        return list(self.safe_actions) + list(self.dangerous_actions)

    def can_click(self, label: str) -> bool:
        """Override if the adapter has a fast-path for specific labels."""
        return False

    def click(self, label: str) -> dict:
        return {"ok": False, "error": "no fast click path for this adapter"}

    def perform(self, action: str, **kwargs) -> dict:
        # Default: dispatch to a method named like the action.
        method = getattr(self, f"do_{action}", None)
        if method is None:
            return {
                "ok": False,
                "error": f"unknown action {action!r} for {self.name}",
                "hint": f"Available actions: {', '.join(self.actions())}",
            }
        # Structured errors (DesktopHarnessError + subclasses, including
        # ConfirmationRequired) MUST propagate so callers can react to the
        # error TYPE, not just an opaque dict. Generic exceptions become
        # agent-friendly dicts.
        from ..errors import DesktopHarnessError
        try:
            return method(**kwargs)
        except DesktopHarnessError:
            raise
        except TypeError as e:
            return {
                "ok": False,
                "error": f"bad args for {action!r}: {e}",
                "hint": "Check argument names and required kwargs.",
            }
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e), "action": action}
