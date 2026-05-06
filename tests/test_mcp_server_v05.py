"""MCP server — v0.5.0 additions wired correctly."""
from __future__ import annotations

import json

import pytest

from desktop_harness import mcp_server


def test_total_tool_count_grew():
    """v0.5.0 added at least 12 new desktop_* tools."""
    assert len(mcp_server.TOOLS) >= 64


def test_new_smart_tools_registered():
    expected = {
        "desktop_smart_click", "desktop_smart_type",
        "desktop_smart_set_value", "desktop_smart_menu", "desktop_smart_open",
    }
    assert expected <= set(mcp_server.TOOLS.keys())


def test_new_wait_tools_registered():
    assert "desktop_wait_for_element" in mcp_server.TOOLS
    assert "desktop_wait_for_window" in mcp_server.TOOLS


def test_safety_tools_registered():
    assert "desktop_classify_risk" in mcp_server.TOOLS
    assert "desktop_recent_actions" in mcp_server.TOOLS


def test_adapter_tools_registered():
    assert "desktop_list_adapters" in mcp_server.TOOLS
    assert "desktop_adapter_actions" in mcp_server.TOOLS
    assert "desktop_perform_adapter_action" in mcp_server.TOOLS


def test_ref_tools_registered():
    assert "desktop_resolve_ref" in mcp_server.TOOLS
    assert "desktop_list_refs" in mcp_server.TOOLS


def test_perform_adapter_action_tool_marked_destructive_in_description():
    desc = mcp_server.TOOLS["desktop_perform_adapter_action"]["description"]
    assert "destructive" in desc.lower() or "DESTRUCTIVE" in desc


def test_classify_risk_tool_returns_serializable_dict():
    handler = mcp_server.TOOLS["desktop_classify_risk"]["handler"]
    out = handler(action="send_email", target="hi", app="Mail")
    json.dumps(out)  # must serialise
    assert out["ok"] is True
    assert out["result"]["risk"] == "destructive"


def test_list_adapters_tool_returns_three_built_ins():
    handler = mcp_server.TOOLS["desktop_list_adapters"]["handler"]
    out = handler()
    assert out["ok"] is True
    names = {a["name"] for a in out["result"]}
    assert {"Finder", "Notes", "Mail"} <= names


def test_perform_adapter_action_destructive_blocks_without_confirm():
    handler = mcp_server.TOOLS["desktop_perform_adapter_action"]["handler"]
    # ConfirmationRequired propagates up from the underlying call — the
    # MCP dispatcher will translate it into an error response, but the
    # handler itself raises here.
    from desktop_harness.errors import ConfirmationRequired
    with pytest.raises(ConfirmationRequired):
        handler(app="Mail", action="send_email",
                args={"to": "x@example.com", "subject": "T", "body": "B"})


def test_smart_click_tool_returns_structured_dict_on_failure(monkeypatch):
    """End-to-end through MCP handler. App not running → structured error."""
    # Force find to raise
    from desktop_harness import smart
    monkeypatch.setattr(smart, "find", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("no app")))
    monkeypatch.setattr(smart, "click_element", lambda el: False)
    import sys
    monkeypatch.setattr(sys.modules["desktop_harness.ocr"],
                        "find_text_on_screen", lambda needle, **kw: None)
    # Stub vision so test runs offline
    monkeypatch.setattr(sys.modules["desktop_harness.vision"], "vision_act",
                        lambda task, app=None, grid=12: {
                            "screenshot": {"path": "/tmp/x.png"}, "recommendations": [],
                        })
    handler = mcp_server.TOOLS["desktop_smart_click"]["handler"]
    out = handler(target="NoSuchControl", app="Notes")
    # Result is a smart_click dict (not wrapped in _ok/_err — smart_click
    # already returns its own structured form).
    json.dumps(out, default=str)  # must be JSON-clean
    assert "tried" in out
    assert out["ok"] is False


def test_input_schema_present_on_every_new_tool():
    """Every desktop_* tool exposes an input_schema (JSON Schema dict)."""
    for name, spec in mcp_server.TOOLS.items():
        if not name.startswith("desktop_"):
            continue
        s = spec["input_schema"]
        assert isinstance(s, dict)
        assert s.get("type") == "object"


def test_legacy_tools_still_present():
    """v0.5.0 must not break v0.3 / v0.4 tools."""
    must_have = {
        "list_apps", "frontmost", "open_app", "ax_find", "ax_click",
        "screenshot", "smart_click", "vision_act",  # v0.4 vision tools
        "accessibility_snapshot",  # v0.3
    }
    assert must_have <= set(mcp_server.TOOLS.keys())
