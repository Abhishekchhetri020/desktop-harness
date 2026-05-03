"""errors.py — exception classes carry remediation."""
from desktop_harness.errors import (
    DesktopHarnessError, AccessibilityNotGranted, ScreenRecordingNotGranted,
    AutomationNotGranted, AppNotRunning, ElementNotFound,
)


def test_subclasses_have_remedy():
    for cls in (
        AccessibilityNotGranted, ScreenRecordingNotGranted,
        AutomationNotGranted, AppNotRunning, ElementNotFound,
    ):
        assert cls.remedy
        assert isinstance(cls.remedy, str)


def test_str_includes_remedy():
    e = AccessibilityNotGranted("AX denied")
    s = str(e)
    assert "AX denied" in s
    assert "System Settings" in s
