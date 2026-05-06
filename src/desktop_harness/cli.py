"""CLI entry point — `desktop-harness -c "expr"` evaluates Python with all builtins
pre-imported, just like browser-harness."""
from __future__ import annotations
import argparse
import json
import sys
import time
import traceback

from . import __version__


def _build_namespace() -> dict:
    """Flat namespace containing every public helper. Used by `-c` mode.
    Pulls from the package's __all__ so we don't get bitten by submodule/function
    name collisions (e.g. the `ocr` module vs the `ocr` function)."""
    import desktop_harness as _pkg
    ns: dict = {}
    for k in _pkg.__all__:
        ns[k] = getattr(_pkg, k)

    # Convenience: pre-import common stdlib
    import json as _json, time as _time, os as _os, re as _re
    ns.update({"json": _json, "time": _time, "os": _os, "re": _re})

    # Workspace helpers — load anything in agent_helpers.py if it exists
    try:
        from pathlib import Path
        ws_root = Path(__file__).resolve().parents[2] / "agent-workspace"
        helpers = ws_root / "agent_helpers.py"
        if helpers.exists():
            ns["__agent_helpers_path__"] = str(helpers)
            code = helpers.read_text()
            exec(compile(code, str(helpers), "exec"), ns)
    except Exception as e:  # don't fail the CLI if the workspace is broken
        ns["__agent_helpers_error__"] = repr(e)
    return ns


def _doctor():
    from .permissions import doctor_permissions
    from .apps import list_apps
    print(f"desktop-harness {__version__}")
    print()
    print("Python:", sys.version.split()[0])
    try:
        import objc, AppKit, Quartz, ApplicationServices, Vision  # noqa
        print("pyobjc:", "OK")
    except Exception as e:
        print("pyobjc:", "FAIL —", e)

    perms = doctor_permissions()
    for k, v in perms.items():
        flag = "✓" if v else "✗"
        print(f"  {flag} {k}: {v}")
    if not perms["accessibility"]:
        print()
        print("[!] Accessibility is required for AX clicks/finds and CGEvent input.")
        print("    Open: System Settings → Privacy & Security → Accessibility,")
        print("    then enable the parent process (Terminal, iTerm, Claude Code, …).")
    if not perms["screen_recording"]:
        print()
        print("[!] Screen Recording is required for screenshots and OCR.")
        print("    Open: System Settings → Privacy & Security → Screen Recording.")
    apps = list_apps()
    print()
    print(f"Running apps: {len(apps)} (sample 5):")
    for a in apps[:5]:
        print(f"  {a['name']:30s}  pid={a['pid']:6d}  bundle={a['bundle_id']}")


def _setup() -> int:
    """Interactive permissions wizard. Walks the four System Settings panes
    that desktop-harness needs and waits for each to flip on."""
    from .permissions import (
        check_accessibility, check_screen_recording,
        check_automation, doctor_permissions,
    )
    print(f"desktop-harness setup — v{__version__}")
    print()
    perms = doctor_permissions()

    panes = [
        ("Accessibility",
         "System Settings → Privacy & Security → Accessibility",
         "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
         "accessibility",
         check_accessibility),
        ("Screen Recording",
         "System Settings → Privacy & Security → Screen Recording",
         "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
         "screen_recording",
         check_screen_recording),
        ("Automation",
         "System Settings → Privacy & Security → Automation",
         "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation",
         None,
         None),
        ("Input Monitoring",
         "System Settings → Privacy & Security → Input Monitoring "
         "(only needed for the action recorder)",
         "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
         None,
         None),
    ]

    import subprocess
    for name, where, url, key, checker in panes:
        granted = perms.get(key) if key else None
        flag = "✓" if granted else ("?" if granted is None else "✗")
        print(f"[{flag}] {name}")
        print(f"     {where}")
        if granted is False:
            print(f"     Opening pane…")
            try:
                subprocess.run(["open", url], check=False, timeout=5)
            except Exception:
                pass
            print("     Toggle this app on, then press Enter to re-check.")
            try:
                input()
            except EOFError:
                pass
            if checker is not None and not checker():
                print(f"     Still not granted. You can re-run `desktop-harness --setup`.")
        print()

    print("Re-running diagnostics:")
    _doctor()
    return 0


def _record(out_path: str, duration: float) -> int:
    from .recorder import Recorder
    print(f"Recording for {duration:.1f}s — interact with anything…", file=sys.stderr)
    rec = Recorder()
    try:
        rec.start()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    time.sleep(duration)
    rec.stop()
    if out_path.endswith(".json"):
        rec.to_json(out_path)
    else:
        rec.to_python(out_path)
    print(f"Wrote {len(rec.events())} events to {out_path}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# v0.5.0 subcommands
# ---------------------------------------------------------------------------

def _print_json(o):
    try:
        print(json.dumps(o, indent=2, default=str))
    except Exception:
        print(repr(o))


def _cmd_snapshot(app: str, max_elements: int, interactive_only: bool) -> int:
    from .snapshot import accessibility_snapshot
    snap = accessibility_snapshot(app, max_elements=max_elements,
                                  interactive_only=interactive_only)
    _print_json(snap)
    return 0


def _cmd_click(app: str | None, target: str) -> int:
    from .smart import smart_click
    _print_json(smart_click(target, app=app))
    return 0


def _cmd_type(app: str | None, target: str, text: str, clear: bool) -> int:
    from .smart import smart_type
    _print_json(smart_type(target, text, app=app, clear_first=clear))
    return 0


def _cmd_menu(app: str, menu_path: str) -> int:
    from .smart import smart_menu
    _print_json(smart_menu(app, menu_path))
    return 0


def _cmd_wait(app: str, role: str | None, title: str | None,
              title_contains: str | None, timeout: float) -> int:
    from .waiters import wait_for_element
    _print_json(wait_for_element(app, role=role, title=title,
                                  title_contains=title_contains, timeout=timeout))
    return 0


def _cmd_adapter(app: str | None, action: str | None, args_json: str | None) -> int:
    from .adapters import list_adapters, adapter_actions, perform_adapter_action
    if app is None:
        _print_json(list_adapters())
        return 0
    if action is None:
        _print_json(adapter_actions(app))
        return 0
    args = json.loads(args_json) if args_json else {}
    _print_json(perform_adapter_action(app, action, **args))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="desktop-harness",
        description="Drive any macOS app via AX, AppleScript, CGEvent, OCR.",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("mcp", help="Run as an MCP server over stdio (for AI agents).")

    p_record = sub.add_parser("record", help="Record user actions to a replayable script.")
    p_record.add_argument("--out", required=True, help="Output path (.py or .json).")
    p_record.add_argument("--duration", type=float, default=15.0, help="Recording duration in seconds.")

    sub.add_parser("demo", help="Live walkthrough — list apps, dump TextEdit AX, take a screenshot.")

    # v0.5.0 subcommands
    p_snap = sub.add_parser("snapshot", help="Compact AX snapshot of an app (JSON).")
    p_snap.add_argument("app")
    p_snap.add_argument("--max-elements", type=int, default=500)
    p_snap.add_argument("--all", action="store_true",
                        help="Include non-interactive elements too.")

    p_click = sub.add_parser("click", help="Smart click a label or ref in an app.")
    p_click.add_argument("app", nargs="?")
    p_click.add_argument("target")

    p_type = sub.add_parser("type", help="Smart-focus a control and type text.")
    p_type.add_argument("app", nargs="?")
    p_type.add_argument("target")
    p_type.add_argument("text")
    p_type.add_argument("--clear", action="store_true",
                        help="Clear existing value before typing (cmd+a, delete).")

    p_menu = sub.add_parser("menu", help="Click an app menu by path: 'File > New Folder'.")
    p_menu.add_argument("app")
    p_menu.add_argument("menu_path")

    p_wait = sub.add_parser("wait", help="Wait for an AX element to appear.")
    p_wait.add_argument("app")
    p_wait.add_argument("--role")
    p_wait.add_argument("--title")
    p_wait.add_argument("--title-contains")
    p_wait.add_argument("--timeout", type=float, default=10.0)

    p_adapter = sub.add_parser("adapter",
                               help="List adapters, list adapter actions, or run an adapter action.")
    p_adapter.add_argument("app", nargs="?", help="App name. Omit to list all adapters.")
    p_adapter.add_argument("action", nargs="?",
                           help="Action name. Omit to list available actions.")
    p_adapter.add_argument("--args", help="JSON dict of kwargs for the action.")

    parser.add_argument("-c", "--code", help="Python expression / statements to evaluate.")
    parser.add_argument("-f", "--file", help="Run a Python file with all helpers in namespace.")
    parser.add_argument("--doctor", action="store_true", help="Diagnostics + permission status.")
    parser.add_argument("--setup", action="store_true",
                        help="Interactive permissions wizard.")
    parser.add_argument("--list-apps", action="store_true", help="List running apps as JSON.")
    parser.add_argument("--frontmost", action="store_true", help="Print the frontmost app.")
    parser.add_argument("--ax", metavar="APP", help="Dump AX tree of an app.")
    parser.add_argument("--ax-depth", type=int, default=6, help="Max depth for --ax.")
    parser.add_argument("--screenshot", metavar="PATH", help="Save full-screen PNG to PATH.")
    parser.add_argument("--list-windows", metavar="APP", help="List windows of APP (or all if 'all').")
    parser.add_argument("--version", action="version", version=f"desktop-harness {__version__}")
    args = parser.parse_args(argv)

    if args.cmd == "mcp":
        from .mcp_server import main as mcp_main
        return mcp_main()

    if args.cmd == "record":
        return _record(args.out, args.duration)

    if args.cmd == "demo":
        return _demo()

    if args.cmd == "snapshot":
        return _cmd_snapshot(args.app, args.max_elements, not args.all)

    if args.cmd == "click":
        return _cmd_click(args.app, args.target)

    if args.cmd == "type":
        return _cmd_type(args.app, args.target, args.text, args.clear)

    if args.cmd == "menu":
        return _cmd_menu(args.app, args.menu_path)

    if args.cmd == "wait":
        return _cmd_wait(args.app, args.role, args.title, args.title_contains, args.timeout)

    if args.cmd == "adapter":
        return _cmd_adapter(args.app, args.action, args.args)

    if args.doctor:
        _doctor()
        return 0

    if args.setup:
        return _setup()

    if args.list_apps:
        from .apps import list_apps
        print(json.dumps(list_apps(), indent=2))
        return 0

    if args.frontmost:
        from .apps import frontmost
        print(json.dumps(frontmost(), indent=2))
        return 0

    if args.ax:
        from .ax import ax_dump
        print(ax_dump(args.ax, max_depth=args.ax_depth))
        return 0

    if args.screenshot:
        from .screen import screenshot
        print(screenshot(args.screenshot))
        return 0

    if args.list_windows:
        from .windows import list_windows
        app = None if args.list_windows == "all" else args.list_windows
        print(json.dumps(list_windows(app), indent=2))
        return 0

    if args.code:
        ns = _build_namespace()
        try:
            try:
                result = eval(args.code, ns)
                if result is not None:
                    if isinstance(result, (dict, list)):
                        try:
                            print(json.dumps(result, indent=2, default=str))
                        except Exception:
                            print(repr(result))
                    else:
                        print(result)
            except SyntaxError:
                exec(args.code, ns)
        except SystemExit:
            raise
        except Exception:
            traceback.print_exc()
            return 1
        return 0

    if args.file:
        ns = _build_namespace()
        with open(args.file) as f:
            code = f.read()
        exec(compile(code, args.file, "exec"), ns)
        return 0

    parser.print_help()
    return 0


def _demo() -> int:
    """Live demo proving the harness works end-to-end on a fresh system."""
    from .apps import list_apps, frontmost, open_app
    from .ax import ax_dump
    from .screen import screenshot
    from .permissions import doctor_permissions

    print("=== desktop-harness demo ===")
    perms = doctor_permissions()
    for k, v in perms.items():
        print(f"  {('✓' if v else '✗')} {k}")
    if not perms["accessibility"]:
        print("\nGrant Accessibility first; demo skipping AX steps.\n")
    print()

    print(f"Frontmost: {frontmost()}")
    print(f"Running apps: {len(list_apps())}")
    print()
    print("Opening TextEdit…")
    open_app("TextEdit")
    time.sleep(1.0)
    if perms["accessibility"]:
        print("AX tree of TextEdit (depth 3):")
        try:
            print(ax_dump("TextEdit", max_depth=3))
        except Exception as e:
            print(f"  (skipped: {e})")
    print()
    if perms["screen_recording"]:
        path = screenshot()
        print(f"Screenshot saved: {path}")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
