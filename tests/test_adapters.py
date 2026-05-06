"""App adapter registry + Finder/Notes/Mail."""
from __future__ import annotations

import pytest

from desktop_harness import adapters
from desktop_harness.adapters import (
    Adapter,
    list_adapters,
    get_adapter,
    adapter_actions,
    perform_adapter_action,
    FinderAdapter,
    NotesAdapter,
    MailAdapter,
)
from desktop_harness.errors import ConfirmationRequired


def test_three_built_in_adapters_registered():
    names = {a["name"] for a in list_adapters()}
    assert {"Finder", "Notes", "Mail"} <= names


def test_get_adapter_by_name():
    a = get_adapter("Notes")
    assert isinstance(a, NotesAdapter)


def test_get_adapter_by_bundle_id():
    a = get_adapter("com.apple.finder")
    assert isinstance(a, FinderAdapter)


def test_get_adapter_case_insensitive():
    a = get_adapter("notes")
    assert isinstance(a, NotesAdapter)


def test_get_adapter_returns_none_for_unknown():
    assert get_adapter("ThisAppDoesNotExist") is None
    assert get_adapter(None) is None


def test_adapter_actions_for_known_app():
    out = adapter_actions("Mail")
    assert out["ok"] is True
    assert "send_email" in out["dangerous_actions"]
    assert "draft_email" in out["safe_actions"]
    assert out["app_class"] == "applescript"


def test_adapter_actions_for_unknown_app_has_hint():
    out = adapter_actions("Nonexistent")
    assert out["ok"] is False
    assert "hint" in out


def test_finder_safe_vs_dangerous_split():
    a = FinderAdapter()
    assert "open_folder" in a.safe_actions
    assert "create_folder" in a.dangerous_actions
    assert "move_to_trash" in a.dangerous_actions
    assert set(a.safe_actions).isdisjoint(a.dangerous_actions)


def test_notes_safe_vs_dangerous_split():
    a = NotesAdapter()
    assert "list_folders" in a.safe_actions
    assert "delete_note" in a.dangerous_actions
    assert set(a.safe_actions).isdisjoint(a.dangerous_actions)


def test_mail_send_email_in_dangerous_only():
    a = MailAdapter()
    assert "send_email" in a.dangerous_actions
    assert "send_email" not in a.safe_actions
    assert "draft_email" in a.safe_actions


def test_perform_unknown_action_returns_error():
    out = perform_adapter_action("Notes", "no_such_action")
    assert out["ok"] is False
    assert "unknown action" in out["error"].lower()
    assert "available actions" in out["hint"].lower() or "actions" in out["hint"].lower()


def test_perform_destructive_without_confirm_blocks():
    """Mail.send_email without confirm/dry_run must raise ConfirmationRequired."""
    with pytest.raises(ConfirmationRequired):
        perform_adapter_action("Mail", "send_email",
                                to="x@example.com",
                                subject="Test",
                                body="Body")


def test_perform_destructive_with_dry_run_returns_preview():
    out = perform_adapter_action("Mail", "send_email",
                                  to="x@example.com",
                                  subject="Test",
                                  body="Body",
                                  dry_run=True)
    assert out["ok"] is True
    assert out["dry_run"] is True
    assert out["executed"] is False
    assert "preview" in out


def test_perform_unknown_app_has_hint():
    out = perform_adapter_action("NoSuch", "do_something")
    assert out["ok"] is False
    assert "hint" in out


def test_register_custom_adapter():
    class _DummyAdapter(Adapter):
        name = "DummyApp"
        bundle_ids = ("com.example.dummy",)
        app_class = "native_ax"
        safe_actions = ("ping",)
        def do_ping(self):
            return {"ok": True, "pong": True}

    d = _DummyAdapter()
    adapters.register(d)
    try:
        assert get_adapter("DummyApp") is d
        out = perform_adapter_action("DummyApp", "ping")
        assert out["ok"] is True
        assert out["pong"] is True
    finally:
        # Don't pollute the registry for other tests
        adapters._REGISTRY.pop("DummyApp", None)
        adapters._REGISTRY.pop("com.example.dummy", None)
