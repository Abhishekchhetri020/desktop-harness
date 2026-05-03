"""MCP server — JSON-RPC protocol smoke tests over a subprocess pipe."""
import json
import subprocess
import sys
import threading
import time

import pytest


def _send(stdin, msg: dict) -> None:
    stdin.write((json.dumps(msg) + "\n").encode())
    stdin.flush()


def _wait_for_response(proc, target_id, timeout=8.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            time.sleep(0.05)
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("id") == target_id:
            return obj
    return None


@pytest.fixture
def mcp_proc():
    p = subprocess.Popen(
        ["desktop-harness", "mcp"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    # init handshake
    _send(p.stdin, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}})
    init_resp = _wait_for_response(p, 1)
    assert init_resp is not None and "result" in init_resp
    _send(p.stdin, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    yield p
    try:
        p.stdin.close()
        p.wait(timeout=3)
    except Exception:
        p.kill()


def test_tools_list_returns_many(mcp_proc):
    _send(mcp_proc.stdin, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    resp = _wait_for_response(mcp_proc, 2)
    assert resp is not None
    tools = resp["result"]["tools"]
    assert len(tools) >= 40
    names = {t["name"] for t in tools}
    for must in ("list_apps", "frontmost", "ax_find", "ax_click", "screenshot",
                 "type_text", "key_press", "doctor", "version", "list_windows"):
        assert must in names, f"missing tool: {must}"


def test_call_version_tool(mcp_proc):
    _send(mcp_proc.stdin, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                           "params": {"name": "version", "arguments": {}}})
    resp = _wait_for_response(mcp_proc, 3)
    assert resp is not None and "result" in resp
    text = resp["result"]["content"][0]["text"]
    obj = json.loads(text)
    assert obj["ok"] is True
    assert "version" in obj["result"]
    assert obj["result"]["tool_count"] >= 40


def test_call_frontmost(mcp_proc):
    _send(mcp_proc.stdin, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                           "params": {"name": "frontmost", "arguments": {}}})
    resp = _wait_for_response(mcp_proc, 4)
    assert resp is not None and "result" in resp
    obj = json.loads(resp["result"]["content"][0]["text"])
    assert obj["ok"] is True


def test_call_unknown_tool_returns_error(mcp_proc):
    _send(mcp_proc.stdin, {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                           "params": {"name": "no_such_tool_xyz", "arguments": {}}})
    resp = _wait_for_response(mcp_proc, 5)
    assert resp is not None and "error" in resp
    assert resp["error"]["code"] == -32601


def test_doctor_includes_permissions(mcp_proc):
    _send(mcp_proc.stdin, {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                           "params": {"name": "doctor", "arguments": {}}})
    # doctor calls osascript for automation check — give it 30s headroom
    resp = _wait_for_response(mcp_proc, 6, timeout=30.0)
    assert resp is not None, "doctor call timed out"
    obj = json.loads(resp["result"]["content"][0]["text"])
    assert "permissions" in obj["result"]
    assert "accessibility" in obj["result"]["permissions"]
