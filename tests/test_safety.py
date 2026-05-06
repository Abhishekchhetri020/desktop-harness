"""Safety layer — risk classification + confirmed_action gating."""
from __future__ import annotations

import pytest

from desktop_harness.safety import (
    classify_action_risk,
    confirmed_action,
    recent_actions,
    clear_action_log,
    DESTRUCTIVE_KEYWORDS,
    DESTRUCTIVE_PRONE_APPS,
)
from desktop_harness.errors import ConfirmationRequired


# --- classify_action_risk ---

def test_safe_default():
    assert classify_action_risk("click") == "safe"
    assert classify_action_risk("snapshot") == "safe"
    assert classify_action_risk("read_selected_email") == "safe"


def test_destructive_keywords_catch_explicit_verbs():
    for kw in ("send", "delete", "submit", "pay", "remove", "publish", "post", "wipe"):
        assert classify_action_risk(kw) == "destructive", kw


def test_destructive_keyword_in_target_text_classifies_destructive():
    assert classify_action_risk("click", target="Send Email") == "destructive"
    assert classify_action_risk("click", target="Delete forever") == "destructive"
    assert classify_action_risk("click", target="Pay $100") == "destructive"


def test_caution_for_set_and_save_actions():
    assert classify_action_risk("set_value") == "caution"
    assert classify_action_risk("smart_set_value") == "caution"
    assert classify_action_risk("type_text") == "caution"
    assert classify_action_risk("save") == "caution"


def test_send_prone_app_flag():
    # Plain click in Mail without destructive keyword in target -> caution
    assert classify_action_risk("click", target="Subject", app="Mail") == "caution"
    assert classify_action_risk("click", target="To", app="Slack") == "caution"


def test_send_prone_app_doesnt_override_destructive():
    # Even in a non-prone app, "delete" is still destructive
    assert classify_action_risk("click", target="Delete", app="Finder") == "destructive"


def test_filesystem_mutations_destructive():
    assert classify_action_risk("move_to_trash") == "destructive"
    assert classify_action_risk("delete_file") == "destructive"
    assert classify_action_risk("empty_trash") == "destructive"


# --- confirmed_action ---

def test_safe_action_runs_without_confirm():
    clear_action_log()
    out = confirmed_action("click", lambda: 42, target="OK", app="Notes")
    assert out["ok"] is True
    assert out["risk"] == "safe"
    assert out["executed"] is True
    assert out["result"] == 42


def test_destructive_without_confirm_raises():
    clear_action_log()
    with pytest.raises(ConfirmationRequired):
        confirmed_action("send_email", lambda: "sent",
                          target="Hello", app="Mail")


def test_destructive_with_confirm_runs():
    out = confirmed_action("send_email", lambda: "sent",
                           confirm=True, target="Hello", app="Mail")
    assert out["ok"] is True
    assert out["risk"] == "destructive"
    assert out["result"] == "sent"


def test_dry_run_short_circuits():
    out = confirmed_action("send_email", lambda: "should_not_run",
                           dry_run=True, target="Hello", app="Mail")
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["executed"] is False
    assert "preview" in out


def test_failure_inside_callable_returns_error_dict_not_raise():
    def boom(): raise RuntimeError("kaboom")
    out = confirmed_action("click", boom, target="OK", app="Notes")
    assert out["ok"] is False
    assert "kaboom" in out["error"]


def test_action_log_records_recent():
    clear_action_log()
    confirmed_action("click", lambda: 1, target="OK", app="Notes")
    confirmed_action("type_text", lambda: 2, target="hi", app="Notes")
    log = recent_actions()
    assert len(log) >= 2
    assert log[-1]["action"] == "type_text"


def test_clear_action_log_returns_count():
    clear_action_log()
    confirmed_action("click", lambda: 1, target="x", app="Notes")
    confirmed_action("click", lambda: 2, target="y", app="Notes")
    n = clear_action_log()
    assert n == 2
    assert recent_actions() == []
