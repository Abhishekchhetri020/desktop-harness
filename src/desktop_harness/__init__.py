"""Desktop Harness — drive any macOS app via Accessibility, AppleScript, CGEvent.

Public API is the union of these modules; the CLI exposes them as a flat namespace
so `desktop-harness -c 'click_element(find("Notes", role="AXButton", title="New Note"))'`
just works without imports.
"""
__version__ = "0.3.0"

from .apps import (
    list_apps, frontmost, open_app, activate, quit_app, is_running,
    pid_of, app_info,
)
from .input import (
    click_at, double_click_at, right_click_at, mouse_move, drag,
    type_text, key, hold_key, scroll, KEYCODES,
)
from .screen import (
    screenshot, screenshot_window, screenshot_region, displays,
    main_display_size, save_image,
)
from .ax import (
    app_ax, ax_tree, ax_dump, find, find_all, click_element,
    get_value, set_value, get_attr, get_attrs, perform_action,
    role, title, position, size, focused_element, focus,
    parent, children, descendants, AXError,
)
from .applescript import (
    osascript, osascript_app, jxa, tell, type_via_se, key_via_se,
)
from .ocr import (
    ocr, ocr_region, ocr_window, find_text_on_screen,
)
from .permissions import (
    check_accessibility, check_screen_recording, check_automation,
    request_accessibility, doctor_permissions,
)
from .windows import (
    list_windows, windows_of, main_window, focused_window,
    window_move, window_resize, window_set_bounds, window_minimize,
    window_close, window_focus, window_to_display, maximize,
    tile_left, tile_right, window_bounds,
)
from .observers import (
    observe, unobserve, list_observers, stop_all, observing, wait_for,
)
from .recorder import Recorder
from .snapshot import (
    accessibility_snapshot, click_text, scrape_app, batch_actions,
    lookup_ref, clear_refs, INTERACTIVE_ROLES,
)
from .errors import (
    DesktopHarnessError, AccessibilityNotGranted, ScreenRecordingNotGranted,
    AutomationNotGranted, InputMonitoringNotGranted, AppNotRunning,
    WindowNotFound, ElementNotFound,
)

__all__ = [
    # apps
    "list_apps", "frontmost", "open_app", "activate", "quit_app",
    "is_running", "pid_of", "app_info",
    # input
    "click_at", "double_click_at", "right_click_at", "mouse_move", "drag",
    "type_text", "key", "hold_key", "scroll", "KEYCODES",
    # screen
    "screenshot", "screenshot_window", "screenshot_region", "displays",
    "main_display_size", "save_image",
    # ax
    "app_ax", "ax_tree", "ax_dump", "find", "find_all", "click_element",
    "get_value", "set_value", "get_attr", "get_attrs", "perform_action",
    "role", "title", "position", "size", "focused_element", "focus",
    "parent", "children", "descendants", "AXError",
    # applescript
    "osascript", "osascript_app", "jxa", "tell", "type_via_se", "key_via_se",
    # ocr
    "ocr", "ocr_region", "ocr_window", "find_text_on_screen",
    # permissions
    "check_accessibility", "check_screen_recording", "check_automation",
    "request_accessibility", "doctor_permissions",
    # windows
    "list_windows", "windows_of", "main_window", "focused_window",
    "window_move", "window_resize", "window_set_bounds", "window_minimize",
    "window_close", "window_focus", "window_to_display", "maximize",
    "tile_left", "tile_right", "window_bounds",
    # observers
    "observe", "unobserve", "list_observers", "stop_all", "observing", "wait_for",
    # recorder
    "Recorder",
    # snapshot (v0.3.0)
    "accessibility_snapshot", "click_text", "scrape_app", "batch_actions",
    "lookup_ref", "clear_refs", "INTERACTIVE_ROLES",
    # errors
    "DesktopHarnessError", "AccessibilityNotGranted", "ScreenRecordingNotGranted",
    "AutomationNotGranted", "InputMonitoringNotGranted", "AppNotRunning",
    "WindowNotFound", "ElementNotFound",
]
