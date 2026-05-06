"""Desktop Harness — drive any macOS app via Accessibility, AppleScript, CGEvent.

Public API is the union of these modules; the CLI exposes them as a flat namespace
so `desktop-harness -c 'click_element(find("Notes", role="AXButton", title="New Note"))'`
just works without imports.
"""
__version__ = "0.5.0"

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
from .vision import (
    app_class, is_electron, screenshot_with_grid, click_cell,
    smart_click as _vision_smart_click, vision_act,
    ELECTRON_APPS, APPLESCRIPT_APPS,
)
from .errors import (
    DesktopHarnessError, AccessibilityNotGranted, ScreenRecordingNotGranted,
    AutomationNotGranted, InputMonitoringNotGranted, AppNotRunning,
    WindowNotFound, ElementNotFound,
    ConfirmationRequired, StaleElementRef,
)

# v0.5.0 additions ---------------------------------------------------------
from .refs import (
    ElementRef, create_element_ref, resolve_ref, refresh_ref,
    re_find_element, is_stale, describe_element, element_bounds,
    list_refs,
    get_ref,
)
# smart_click v2 supersedes the v0.4 vision.smart_click (kept as
# `_vision_smart_click` for tests / backwards compat). New code should use
# the structured-result smart_click below.
from .smart import (
    smart_click, smart_type, smart_set_value, smart_menu, smart_open,
)
from .waiters import (
    wait_for_app, wait_for_frontmost, wait_for_window,
    wait_for_element, wait_until_value, wait_for_text,
    verify_window_open, verify_text_present, verify_clicked,
)
from .safety import (
    classify_action_risk, confirmed_action, recent_actions, clear_action_log,
    DESTRUCTIVE_KEYWORDS, DESTRUCTIVE_PRONE_APPS,
)
from . import adapters
from .adapters import (
    Adapter, register as register_adapter, get_adapter,
    list_adapters, adapter_actions, perform_adapter_action,
    FinderAdapter, NotesAdapter, MailAdapter,
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
    # vision tier (v0.4.0)
    "app_class", "is_electron", "screenshot_with_grid", "click_cell",
    "vision_act", "ELECTRON_APPS", "APPLESCRIPT_APPS",
    # errors
    "DesktopHarnessError", "AccessibilityNotGranted", "ScreenRecordingNotGranted",
    "AutomationNotGranted", "InputMonitoringNotGranted", "AppNotRunning",
    "WindowNotFound", "ElementNotFound",
    "ConfirmationRequired", "StaleElementRef",
    # v0.5.0: stable refs
    "ElementRef", "create_element_ref", "resolve_ref", "refresh_ref",
    "re_find_element", "is_stale", "describe_element", "element_bounds",
    "list_refs", "get_ref",
    # v0.5.0: smart actions (structured results)
    "smart_click", "smart_type", "smart_set_value", "smart_menu", "smart_open",
    # v0.5.0: waiters
    "wait_for_app", "wait_for_frontmost", "wait_for_window",
    "wait_for_element", "wait_until_value", "wait_for_text",
    "verify_window_open", "verify_text_present", "verify_clicked",
    # v0.5.0: safety
    "classify_action_risk", "confirmed_action", "recent_actions",
    "clear_action_log", "DESTRUCTIVE_KEYWORDS", "DESTRUCTIVE_PRONE_APPS",
    # v0.5.0: adapters
    "Adapter", "register_adapter", "get_adapter",
    "list_adapters", "adapter_actions", "perform_adapter_action",
    "FinderAdapter", "NotesAdapter", "MailAdapter",
    "adapters",
]
