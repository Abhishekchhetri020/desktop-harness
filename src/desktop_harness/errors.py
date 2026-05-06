"""Typed exceptions + remediation messages.

Every error tells the user EXACTLY what to do next. No generic stack traces.

v0.5.0: each exception now carries optional `app`, `target`, `tried` (list of
attempted tiers) and `hint`. Use `.as_dict()` to serialise for MCP responses.
"""
from __future__ import annotations

from typing import Optional


class DesktopHarnessError(Exception):
    """Base class. .remedy returns a one-line plain-language fix.

    Optional structured context for agent-friendly errors:
      - app:    target app name
      - target: what the caller was trying to find / act on
      - tried:  ordered list of tiers attempted before failure
      - hint:   one-line next-step suggestion (overrides .remedy in MCP output)
    """
    remedy: str = ""

    def __init__(
        self,
        message: str = "",
        *,
        app: Optional[str] = None,
        target: Optional[str] = None,
        tried: Optional[list[str]] = None,
        hint: Optional[str] = None,
    ):
        super().__init__(message)
        self.app = app
        self.target = target
        self.tried = list(tried) if tried else []
        self.hint = hint

    def __str__(self) -> str:
        m = super().__str__()
        suffix = self.hint or self.remedy
        return f"{m}\n  → {suffix}" if suffix else m

    def as_dict(self) -> dict:
        """Compact JSON-friendly form for MCP / CLI output."""
        out: dict = {
            "ok": False,
            "error": super().__str__() or self.__class__.__name__,
            "type": self.__class__.__name__,
        }
        if self.app:
            out["app"] = self.app
        if self.target:
            out["target"] = self.target
        if self.tried:
            out["tried"] = list(self.tried)
        out["hint"] = self.hint or self.remedy or "see desktop-harness --doctor"
        return out


class AccessibilityNotGranted(DesktopHarnessError):
    remedy = (
        "Open System Settings → Privacy & Security → Accessibility, "
        "then enable the parent process (Terminal / iTerm / Claude Code / …). "
        "You may need to restart that app for the change to take effect."
    )


class ScreenRecordingNotGranted(DesktopHarnessError):
    remedy = (
        "Open System Settings → Privacy & Security → Screen Recording, "
        "enable the parent process, then restart it."
    )


class AutomationNotGranted(DesktopHarnessError):
    remedy = (
        "Open System Settings → Privacy & Security → Automation, "
        "expand the parent process and enable the target app. "
        "If the target isn't listed, run a tell command first to trigger the prompt."
    )


class InputMonitoringNotGranted(DesktopHarnessError):
    remedy = (
        "Open System Settings → Privacy & Security → Input Monitoring, "
        "enable the parent process, then restart it. "
        "Required for the action recorder."
    )


class AppNotRunning(DesktopHarnessError):
    remedy = "Launch the app first via open_app('AppName') or open -a AppName."


class WindowNotFound(DesktopHarnessError):
    remedy = "Use list_windows('AppName') to enumerate available windows."


class ElementNotFound(DesktopHarnessError):
    remedy = (
        "Try ax_dump('AppName') to see the live tree, or relax your filters "
        "(e.g. use title_contains= instead of exact title=). "
        "Some apps populate the tree lazily — focus the window first."
    )


class ConfirmationRequired(DesktopHarnessError):
    """Raised when a destructive action is invoked without confirm=True."""
    remedy = (
        "This action is destructive. Re-call with confirm=True to execute, "
        "or with dry_run=True to preview without side effects."
    )


class StaleElementRef(DesktopHarnessError):
    """Raised when a stable element ref can no longer be resolved."""
    remedy = (
        "The UI changed since the ref was created. Call refresh_ref(ref) "
        "or re_find_element(ref), or take a fresh accessibility_snapshot()."
    )
