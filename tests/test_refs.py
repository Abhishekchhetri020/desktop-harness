"""ElementRef — fingerprinting + (de)serialisation.

Live-AX path is exercised in test_ax.py; here we test the fingerprint logic
with a minimal fake AX surface so the suite stays fast and deterministic.
"""
from __future__ import annotations

import pytest

from desktop_harness.refs import (
    ElementRef,
    _stable_fingerprint,
    _short_id,
    clear_refs,
    list_refs,
)


def test_short_id_is_8hex_prefixed():
    sid = _short_id("abcdef0123456789")
    assert sid == "r-abcdef01"


def test_fingerprint_stable_for_identical_inputs():
    fp1 = _stable_fingerprint("Notes", "com.apple.Notes", "AXButton",
                              "New Note", None, [("AXWindow", 0), ("AXButton", 3)])
    fp2 = _stable_fingerprint("Notes", "com.apple.Notes", "AXButton",
                              "New Note", None, [("AXWindow", 0), ("AXButton", 3)])
    assert fp1 == fp2


def test_fingerprint_changes_when_path_changes():
    fp1 = _stable_fingerprint("Notes", "com.apple.Notes", "AXButton",
                              "New Note", None, [("AXWindow", 0), ("AXButton", 3)])
    fp2 = _stable_fingerprint("Notes", "com.apple.Notes", "AXButton",
                              "New Note", None, [("AXWindow", 0), ("AXButton", 4)])
    assert fp1 != fp2


def test_fingerprint_changes_when_title_changes():
    fp1 = _stable_fingerprint("Notes", "com.apple.Notes", "AXButton",
                              "New Note", None, [])
    fp2 = _stable_fingerprint("Notes", "com.apple.Notes", "AXButton",
                              "Save", None, [])
    assert fp1 != fp2


def test_fingerprint_ignores_value_snippet_and_frame():
    # ElementRef carries value_snippet + frame, but stable fingerprint
    # excludes them (volatile bits).
    fp1 = _stable_fingerprint("Notes", "com.apple.Notes", "AXButton",
                              "New Note", "id-1", [("AXWindow", 0)])
    fp2 = _stable_fingerprint("Notes", "com.apple.Notes", "AXButton",
                              "New Note", "id-1", [("AXWindow", 0)])
    assert fp1 == fp2


def test_element_ref_round_trip_dict():
    r = ElementRef(
        id="r-abcd1234",
        app="Notes",
        bundle_id="com.apple.Notes",
        pid=1234,
        role="AXButton",
        title="New Note",
        path=[("AXWindow", 0), ("AXButton", 3)],
        frame=(100.0, 200.0, 50.0, 30.0),
        fingerprint="abcd1234" * 5,
    )
    d = r.to_dict()
    assert d["app"] == "Notes"
    assert d["path"] == [["AXWindow", 0], ["AXButton", 3]]
    assert d["frame"] == [100.0, 200.0, 50.0, 30.0]
    r2 = ElementRef.from_dict(d)
    assert r2.app == r.app
    assert r2.path == r.path
    assert r2.frame == r.frame


def test_clear_refs_returns_count():
    clear_refs()
    # Nothing in registry → 0
    assert clear_refs() == 0


def test_list_refs_returns_compact_list():
    clear_refs()
    out = list_refs()
    assert out == []
