"""Typed exceptions + remediation messages.

Every error tells the user EXACTLY what to do next. No generic stack traces.
"""
from __future__ import annotations


class DesktopHarnessError(Exception):
    """Base class. .remedy() returns a one-line plain-language fix."""
    remedy: str = ""

    def __str__(self) -> str:
        m = super().__str__()
        return f"{m}\n  → {self.remedy}" if self.remedy else m


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
