"""smart_* engine — structured-result tests using monkeypatched AX layer."""
from __future__ import annotations

import pytest

from desktop_harness import smart


# --- smart_click result shape --------------------------------------------

def test_smart_click_returns_structured_dict_on_failure(monkeypatch):
    """When app is unknown / not running, AX find raises; OCR/vision also miss
    → result has tried[] and hint."""
    # Force AX find to raise so we walk the full tier list without side effects.
    monkeypatch.setattr(smart, "find", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no app")))
    monkeypatch.setattr(smart, "click_element", lambda el: False)

    # OCR returns None (no match)
    import sys
    monkeypatch.setattr(sys.modules["desktop_harness.ocr"],
                        "find_text_on_screen", lambda needle, **kw: None)

    # Vision_act would be slow + need permissions → stub it
    import sys as _sys
    monkeypatch.setattr(_sys.modules["desktop_harness.vision"], "vision_act",
                        lambda task, app=None, grid=12: {
                            "screenshot": {"path": "/tmp/fake.png"},
                            "recommendations": ["fake"],
                        })

    # adapters.get_adapter for an unknown app -> None
    out = smart.smart_click("New Note", app="UnknownApp")
    assert out["ok"] is False
    assert "tried" in out and len(out["tried"]) > 0
    assert "hint" in out
    # OCR was tried before vision handoff
    assert "ocr_screen" in out["tried"]


def test_smart_click_skips_ax_for_electron_apps(monkeypatch):
    """For Electron apps, AX tiers are skipped to save ~2s/call."""
    seen = []
    def fake_find(*a, **kw):
        seen.append(("find", a, kw))
        return None
    monkeypatch.setattr(smart, "find", fake_find)
    # OCR / vision still get called
    import sys
    monkeypatch.setattr(sys.modules["desktop_harness.ocr"],
                        "find_text_on_screen", lambda needle, **kw: None)
    import sys as _sys
    monkeypatch.setattr(_sys.modules["desktop_harness.vision"], "vision_act",
                        lambda task, app=None, grid=12: {
                            "screenshot": {"path": "/tmp/fake.png"},
                            "recommendations": [],
                        })

    # Pretend Slack is in ELECTRON_APPS by patching app_class
    monkeypatch.setattr(smart, "_app_class", lambda app: "electron")

    out = smart.smart_click("Send", app="Slack", use_vision_fallback=False)
    # No find() calls happened — AX tiers were skipped
    assert seen == []
    assert out["app_class"] == "electron"
    # Tier list omitted ax_title_exact / ax_title_contains
    assert "ax_title_exact" not in out["tried"]
    assert "ax_title_contains" not in out["tried"]


def test_smart_click_ax_exact_wins_first(monkeypatch):
    """AX find returns a fake element, click_element succeeds → tier=ax_title_exact."""
    fake_el = object()

    def fake_find(app, **kw):
        if kw.get("title") == "New Note":
            return fake_el
        return None

    monkeypatch.setattr(smart, "find", fake_find)
    monkeypatch.setattr(smart, "click_element", lambda el: el is fake_el)
    monkeypatch.setattr(smart, "_app_class", lambda app: "native_ax")

    # Stub create_element_ref so we don't need a live AX tree
    from desktop_harness.refs import ElementRef
    monkeypatch.setattr(smart, "create_element_ref",
                        lambda el, app=None: ElementRef(id="r-fake1234",
                                                        app=app or "Notes",
                                                        role="AXButton",
                                                        title="New Note",
                                                        fingerprint="x" * 40))

    out = smart.smart_click("New Note", app="Notes")
    assert out["ok"] is True
    assert out["tier"] == "ax_title_exact"
    assert out["ref"] == "r-fake1234"
    assert "ocr_screen" not in out["tried"]
    assert "vision_handoff" not in out["tried"]


def test_smart_click_native_ax_does_not_use_screenshot(monkeypatch):
    """Critical contract: AX-success path must NEVER take a screenshot."""
    fake_el = object()
    monkeypatch.setattr(smart, "find", lambda app, **kw: fake_el if kw.get("title") == "OK" else None)
    monkeypatch.setattr(smart, "click_element", lambda el: True)
    monkeypatch.setattr(smart, "_app_class", lambda app: "native_ax")
    from desktop_harness.refs import ElementRef
    monkeypatch.setattr(smart, "create_element_ref",
                        lambda el, app=None: ElementRef(id="r-x", app="X",
                                                         role="AXButton", title="OK",
                                                         fingerprint="z"*40))

    # If something tries to take a screenshot, fail loudly
    import desktop_harness.screen as _scr
    def boom(*a, **kw): raise AssertionError("AX-success path must not screenshot")
    monkeypatch.setattr(_scr, "screenshot", boom)

    out = smart.smart_click("OK", app="Notes")
    assert out["ok"] is True
    assert "screenshot_path" not in out


def test_smart_click_falls_through_to_ocr_then_vision(monkeypatch):
    """Order check: AX → AX-fuzzy → AX-describe → OCR → vision."""
    monkeypatch.setattr(smart, "find", lambda app, **kw: None)
    monkeypatch.setattr(smart, "click_element", lambda el: False)
    monkeypatch.setattr(smart, "_app_class", lambda app: "native_ax")

    import sys
    monkeypatch.setattr(sys.modules["desktop_harness.ocr"],
                        "find_text_on_screen", lambda needle, **kw: None)

    called = {"vision_act": False}
    def fake_va(task, app=None, grid=12):
        called["vision_act"] = True
        return {"screenshot": {"path": "/tmp/x.png"}, "recommendations": []}
    import sys as _sys
    monkeypatch.setattr(_sys.modules["desktop_harness.vision"], "vision_act", fake_va)

    out = smart.smart_click("Mystery", app="Notes")
    assert out["ok"] is False
    assert called["vision_act"] is True
    # tier list ends with vision_handoff
    assert out["tried"][-1] == "vision_handoff"


# --- smart_menu --------------------------------------------------------------

def test_smart_menu_rejects_empty_path(monkeypatch):
    out = smart.smart_menu("Finder", "")
    assert out["ok"] is False
    assert "menu_path" in out["error"] or "empty" in out["error"].lower()
