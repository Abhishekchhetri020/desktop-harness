"""Risk classification + confirmation gating.

Goal: prevent agents from accidentally pressing Send / Delete / Submit.

Three risk levels:
  * safe        — read-only or reversible (snapshot, click on a non-destructive
                  control, type into a draft, focus a window, …). No friction.
  * caution     — potentially overwriting work but reversible by the user
                  (close window, save-as, set value on a field). Logged but
                  not blocked.
  * destructive — permanent or hard-to-undo (send / submit / pay / delete /
                  remove / publish / post / quit-without-save). Requires
                  confirm=True or dry_run=True or it raises.

Use `confirmed_action(name, fn, *, confirm=False, dry_run=False, **ctx)` to
wrap a callable. Read-only callers don't need to interact with this module.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Callable, Optional

from .errors import ConfirmationRequired


# Words in the target text or action name that indicate a destructive op.
DESTRUCTIVE_KEYWORDS = frozenset({
    "send", "submit", "pay", "purchase", "buy", "checkout", "confirm",
    "delete", "remove", "trash", "erase", "discard", "drop",
    "publish", "post", "tweet",
    "reset", "format", "wipe", "clear all", "factory",
    "log out", "sign out", "quit",
    "overwrite", "replace",
})

# Apps where common actions are inherently destructive when they touch send
# pathways. Used as a multiplier when other heuristics are ambiguous.
DESTRUCTIVE_PRONE_APPS = frozenset({
    "Mail", "Messages", "Slack", "Discord", "Telegram",
    "Outlook", "Teams", "WhatsApp",
})


_LOG_LOCK = threading.Lock()
_ACTION_LOG: deque = deque(maxlen=200)


def classify_action_risk(
    action: str,
    target: Optional[str] = None,
    app: Optional[str] = None,
) -> str:
    """Return 'safe' | 'caution' | 'destructive'.

    Heuristic, not a security boundary. Anything claiming to send / delete /
    submit / pay is destructive. Set-value on text fields is caution. All
    other clicks / reads are safe by default.
    """
    a = (action or "").lower().strip()
    t = (target or "").lower().strip()
    blob = f"{a} {t}"

    # Explicit destructive verbs — most agent harm comes through these.
    for kw in DESTRUCTIVE_KEYWORDS:
        if kw in blob:
            return "destructive"

    # Send-prone app + click on something with text is caution at minimum.
    if app and app in DESTRUCTIVE_PRONE_APPS and a in (
        "click", "smart_click", "press"
    ):
        # Click on a button labelled obviously destructive elsewhere caught above.
        # A plain click in Mail composer (e.g. in body) is fine — caution stays.
        return "caution"

    # Setting values, closing windows, saving — caution
    if a in (
        "set_value", "smart_set_value", "type_text", "smart_type",
        "save", "save_as", "close_window", "window_close",
    ):
        return "caution"

    # File-system mutations through Finder adapter wrappers
    if a in (
        "move_to_trash", "delete_file", "empty_trash",
    ):
        return "destructive"

    return "safe"


def _record(entry: dict) -> None:
    entry["ts"] = time.time()
    with _LOG_LOCK:
        _ACTION_LOG.append(entry)


def recent_actions(n: int = 20) -> list[dict]:
    """Return the last `n` action records, newest last."""
    with _LOG_LOCK:
        return list(_ACTION_LOG)[-n:]


def clear_action_log() -> int:
    with _LOG_LOCK:
        n = len(_ACTION_LOG)
        _ACTION_LOG.clear()
    return n


def confirmed_action(
    name: str,
    fn: Callable[..., Any],
    *args,
    confirm: bool = False,
    dry_run: bool = False,
    target: Optional[str] = None,
    app: Optional[str] = None,
    **kwargs,
) -> dict:
    """Run `fn(*args, **kwargs)` with risk gating + logging.

    Returns a dict:
      {
        "ok": bool,
        "action": name,
        "risk": "safe" | "caution" | "destructive",
        "executed": bool,        # False when dry_run or blocked
        "dry_run": bool,
        "result": <fn return>?,  # absent when dry_run / blocked
        "error": "..."?,
      }

    Raises `ConfirmationRequired` if `risk == 'destructive'` and neither
    `confirm` nor `dry_run` is set.
    """
    risk = classify_action_risk(name, target=target, app=app)

    record = {
        "action": name,
        "app": app,
        "target": target,
        "risk": risk,
        "dry_run": dry_run,
        "confirm": confirm,
    }

    if risk == "destructive" and not (confirm or dry_run):
        record["executed"] = False
        record["error"] = "ConfirmationRequired"
        _record(record)
        raise ConfirmationRequired(
            f"{name!r} is destructive (risk={risk}, target={target!r}, app={app!r})",
            app=app, target=target, hint=(
                "Re-call with confirm=True to execute, or dry_run=True to preview."
            ),
        )

    if dry_run:
        record["executed"] = False
        record["preview"] = {"action": name, "args": list(args), "kwargs": kwargs}
        _record(record)
        return {
            "ok": True,
            "action": name,
            "risk": risk,
            "executed": False,
            "dry_run": True,
            "preview": record["preview"],
        }

    try:
        result = fn(*args, **kwargs)
        record["executed"] = True
        record["ok"] = True
        _record(record)
        return {
            "ok": True,
            "action": name,
            "risk": risk,
            "executed": True,
            "dry_run": False,
            "result": result,
        }
    except Exception as e:  # noqa: BLE001
        record["executed"] = False
        record["error"] = str(e)
        _record(record)
        return {
            "ok": False,
            "action": name,
            "risk": risk,
            "executed": False,
            "dry_run": False,
            "error": str(e),
        }
