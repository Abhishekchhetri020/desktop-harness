"""Wait/verify primitives — uses monkeypatch to keep tests fast."""
from __future__ import annotations

import time

import pytest

from desktop_harness import waiters


def test_wait_for_app_succeeds_when_running(monkeypatch):
    monkeypatch.setattr(waiters, "is_running", lambda name: True)
    out = waiters.wait_for_app("Notes", timeout=0.5)
    assert out["ok"] is True
    assert out["method"] == "polling"
    assert out["elapsed"] < 0.5


def test_wait_for_app_times_out_with_hint(monkeypatch):
    monkeypatch.setattr(waiters, "is_running", lambda name: False)
    t0 = time.monotonic()
    out = waiters.wait_for_app("NeverApp", timeout=0.3, poll=0.05)
    assert out["ok"] is False
    assert "did not start" in out["error"]
    assert "hint" in out
    assert time.monotonic() - t0 >= 0.3


def test_wait_for_frontmost_succeeds(monkeypatch):
    monkeypatch.setattr(waiters, "frontmost", lambda: {"name": "Notes"})
    out = waiters.wait_for_frontmost("Notes", timeout=0.5)
    assert out["ok"] is True


def test_wait_for_frontmost_reports_actual_frontmost_on_timeout(monkeypatch):
    monkeypatch.setattr(waiters, "frontmost", lambda: {"name": "Mail"})
    out = waiters.wait_for_frontmost("Notes", timeout=0.2, poll=0.05)
    assert out["ok"] is False
    assert out["frontmost"] == "Mail"


def test_wait_for_window_succeeds_on_match(monkeypatch):
    monkeypatch.setattr(waiters, "list_windows",
                        lambda app: [{"name": "Untitled — Notes", "id": 1}])
    out = waiters.wait_for_window("Notes", title_contains="Untitled", timeout=0.5)
    assert out["ok"] is True
    assert out["window"]["name"] == "Untitled — Notes"


def test_wait_for_window_times_out(monkeypatch):
    monkeypatch.setattr(waiters, "list_windows", lambda app: [])
    out = waiters.wait_for_window("Notes", title_contains="Nope", timeout=0.2, poll=0.05)
    assert out["ok"] is False
    assert "no matching window" in out["error"]


def test_verify_window_open_no_match_returns_window_list(monkeypatch):
    monkeypatch.setattr(waiters, "list_windows",
                        lambda app: [{"name": "Win1"}, {"name": "Win2"}])
    out = waiters.verify_window_open("Notes", title_contains="Nope")
    assert out["ok"] is False
    assert out["windows"] == ["Win1", "Win2"]


def test_verify_window_open_match(monkeypatch):
    monkeypatch.setattr(waiters, "list_windows",
                        lambda app: [{"name": "Notes — A"}])
    out = waiters.verify_window_open("Notes", title_contains="Notes")
    assert out["ok"] is True
    assert out["window"]["name"] == "Notes — A"
