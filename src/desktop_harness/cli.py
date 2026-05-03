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

    p_demo = sub.add_parser("demo", help="Live walkthrough — list apps, dump TextEdit AX, take a screenshot.")

    parser.add_argument("-c", "--code", help="Python expression / statements to evaluate.")
    parser.add_argument("-f", "--file", help="Run a Python file with all helpers in namespace.")
    parser.add_argument("--doctor", action="store_true", help="Diagnostics + permission status.")
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

    if args.doctor:
        _doctor()
        return 0

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
