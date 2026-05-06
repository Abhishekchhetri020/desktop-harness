"""Errors v0.5.0 — structured fields + as_dict."""
from __future__ import annotations

import pytest

from desktop_harness.errors import (
    DesktopHarnessError,
    ElementNotFound,
    ConfirmationRequired,
    StaleElementRef,
    AccessibilityNotGranted,
)


def test_base_error_keeps_message():
    e = DesktopHarnessError("oops")
    assert "oops" in str(e)


def test_extra_fields_default_to_none_or_empty():
    e = ElementNotFound("missing")
    assert e.app is None
    assert e.target is None
    assert e.tried == []
    assert e.hint is None


def test_as_dict_minimum_shape():
    e = ElementNotFound("missing")
    d = e.as_dict()
    assert d["ok"] is False
    assert d["type"] == "ElementNotFound"
    # remedy fallback used as hint when explicit hint is absent
    assert "ax_dump" in d["hint"]


def test_as_dict_carries_structured_context():
    e = ElementNotFound(
        "could not click",
        app="Notes",
        target="New Note",
        tried=["adapter", "ax_title_exact", "ax_title_contains", "ocr_screen"],
        hint="run accessibility_snapshot('Notes')",
    )
    d = e.as_dict()
    assert d["app"] == "Notes"
    assert d["target"] == "New Note"
    assert d["tried"] == ["adapter", "ax_title_exact", "ax_title_contains", "ocr_screen"]
    assert d["hint"] == "run accessibility_snapshot('Notes')"


def test_str_uses_hint_over_remedy_when_provided():
    e = ElementNotFound("not found", hint="try fuzzy match")
    assert "try fuzzy match" in str(e)


def test_str_uses_remedy_when_no_hint():
    e = ElementNotFound("not found")
    assert "ax_dump" in str(e)  # remedy text contains 'ax_dump'


def test_confirmation_required_carries_remedy():
    e = ConfirmationRequired("send_email is destructive")
    assert "confirm=True" in e.remedy
    d = e.as_dict()
    assert d["type"] == "ConfirmationRequired"


def test_stale_element_ref_carries_remedy():
    e = StaleElementRef("ref expired")
    assert "refresh_ref" in e.remedy or "re_find_element" in e.remedy


def test_accessibility_not_granted_remedy_present():
    e = AccessibilityNotGranted()
    d = e.as_dict()
    assert "Accessibility" in d["hint"] or "Accessibility" in str(e)


def test_extra_kwargs_dont_break_construction():
    # The classes accept arbitrary kwargs without app/target/tried/hint.
    e = ElementNotFound()
    assert e.tried == []
