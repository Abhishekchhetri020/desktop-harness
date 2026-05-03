"""TCC permission checks and helpful error guidance."""
from __future__ import annotations
import subprocess

from ApplicationServices import (
    AXIsProcessTrustedWithOptions,
    AXIsProcessTrusted,
)


def check_accessibility(*, prompt: bool = False) -> bool:
    """Is this process trusted for the AX API?"""
    if prompt:
        opts = {"AXTrustedCheckOptionPrompt": True}
        return bool(AXIsProcessTrustedWithOptions(opts))
    return bool(AXIsProcessTrusted())


def request_accessibility() -> bool:
    """Trigger the macOS dialog that asks for Accessibility access."""
    opts = {"AXTrustedCheckOptionPrompt": True}
    return bool(AXIsProcessTrustedWithOptions(opts))


def check_screen_recording() -> bool:
    """Probe Screen Recording by attempting a 1×1 capture."""
    try:
        from Quartz import (
            CGWindowListCreateImage, CGRectMake, kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID, kCGWindowImageDefault,
        )
        img = CGWindowListCreateImage(
            CGRectMake(0, 0, 1, 1),
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
            kCGWindowImageDefault,
        )
        return img is not None
    except Exception:
        return False


def check_automation(target_app: str = "System Events") -> bool:
    """Try a no-op AppleScript against target_app to see if Automation is granted."""
    try:
        r = subprocess.run(
            ["osascript", "-e", f'tell application "{target_app}" to get name'],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def doctor_permissions() -> dict:
    """One-shot status of every permission desktop-harness might need."""
    return {
        "accessibility": check_accessibility(prompt=False),
        "screen_recording": check_screen_recording(),
        "automation_system_events": check_automation("System Events"),
    }
