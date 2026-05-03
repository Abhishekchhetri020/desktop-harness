"""pytest fixtures shared across test modules."""
import os
import platform
import time
import subprocess

import pytest


def pytest_collection_modifyitems(config, items):
    """Auto-skip 'live' tests on non-mac, on CI without permissions, or unless opted in."""
    if platform.system() != "Darwin":
        for item in items:
            item.add_marker(pytest.mark.skip(reason="macOS only"))
        return
    # 'live' tests open real apps. Opt in via RUN_LIVE_TESTS=1.
    run_live = os.environ.get("RUN_LIVE_TESTS") == "1"
    try:
        from desktop_harness.permissions import doctor_permissions
        perms = doctor_permissions()
        no_ax = not perms.get("accessibility")
    except Exception:
        no_ax = True
    for item in items:
        if "live" in item.keywords:
            if not run_live:
                item.add_marker(pytest.mark.skip(reason="set RUN_LIVE_TESTS=1 to run"))
            elif no_ax:
                item.add_marker(pytest.mark.skip(reason="Accessibility permission required"))


@pytest.fixture
def textedit():
    """Open TextEdit (universally present on macOS), yield, then close.

    Retries waiting for the app to be queryable via AX (TextEdit takes
    up to ~3s to fully spin up on cold boot)."""
    from desktop_harness import open_app, quit_app, is_running, app_ax, AXError
    if not is_running("TextEdit"):
        # Use `open -a` directly — more reliable than NSWorkspace.launchApplication_
        subprocess.run(["open", "-a", "TextEdit"], check=False)
    deadline = time.time() + 8.0
    while time.time() < deadline:
        if is_running("TextEdit"):
            try:
                app_ax("TextEdit")
                break
            except AXError:
                pass
        time.sleep(0.2)
    else:
        pytest.skip("TextEdit failed to launch within 8s")
    # Open a new doc so a window exists
    subprocess.run(["osascript", "-e", 'tell application "TextEdit" to make new document'], check=False)
    time.sleep(0.5)
    yield "TextEdit"
    try:
        quit_app("TextEdit", force=True)
    except Exception:
        pass
    time.sleep(0.3)
