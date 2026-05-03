"""App lifecycle: list, frontmost, launch, activate, quit, query."""
from __future__ import annotations
import subprocess
import time
from typing import Optional

from AppKit import (
    NSWorkspace,
    NSRunningApplication,
    NSWorkspaceLaunchDefault,
    NSApplicationActivateIgnoringOtherApps,
)


def list_apps() -> list[dict]:
    """Every running app: name, bundle id, pid, active, hidden."""
    out = []
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        out.append({
            "name": str(a.localizedName() or ""),
            "bundle_id": str(a.bundleIdentifier() or ""),
            "pid": int(a.processIdentifier()),
            "active": bool(a.isActive()),
            "hidden": bool(a.isHidden()),
        })
    return out


def frontmost() -> dict | None:
    """The app currently in front."""
    a = NSWorkspace.sharedWorkspace().frontmostApplication()
    if a is None:
        return None
    return {
        "name": str(a.localizedName() or ""),
        "bundle_id": str(a.bundleIdentifier() or ""),
        "pid": int(a.processIdentifier()),
    }


def is_running(name_or_bundle: str) -> bool:
    n = name_or_bundle.lower()
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if (str(a.localizedName() or "").lower() == n
                or str(a.bundleIdentifier() or "").lower() == n):
            return True
    return False


def pid_of(name_or_bundle: str) -> int | None:
    n = name_or_bundle.lower()
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if (str(a.localizedName() or "").lower() == n
                or str(a.bundleIdentifier() or "").lower() == n):
            return int(a.processIdentifier())
    return None


def app_info(name_or_bundle: str) -> dict | None:
    n = name_or_bundle.lower()
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if (str(a.localizedName() or "").lower() == n
                or str(a.bundleIdentifier() or "").lower() == n):
            url = a.bundleURL()
            return {
                "name": str(a.localizedName() or ""),
                "bundle_id": str(a.bundleIdentifier() or ""),
                "pid": int(a.processIdentifier()),
                "active": bool(a.isActive()),
                "hidden": bool(a.isHidden()),
                "path": str(url.path()) if url else None,
            }
    return None


def open_app(name_or_path: str, *, wait: float = 1.5) -> dict | None:
    """Launch an app (or activate if already running). Returns app_info after wait."""
    ws = NSWorkspace.sharedWorkspace()
    if name_or_path.startswith("/"):
        ok = ws.launchApplication_(name_or_path)
    else:
        ok = ws.launchApplication_(name_or_path)
    if not ok:
        # Try via `open -a` as fallback
        subprocess.run(["open", "-a", name_or_path], check=False)
    time.sleep(wait)
    return app_info(name_or_path.split("/")[-1].replace(".app", ""))


def activate(name_or_bundle: str) -> bool:
    """Bring an app to the front."""
    pid = pid_of(name_or_bundle)
    if pid is None:
        return False
    a = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    if a is None:
        return False
    return bool(a.activateWithOptions_(NSApplicationActivateIgnoringOtherApps))


def quit_app(name_or_bundle: str, *, force: bool = False) -> bool:
    """Quit an app gracefully (or force-terminate)."""
    pid = pid_of(name_or_bundle)
    if pid is None:
        return False
    a = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    if a is None:
        return False
    return bool(a.forceTerminate() if force else a.terminate())
