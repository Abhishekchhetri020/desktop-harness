"""input.py — pure parsing tests (don't actually fire events)."""
import pytest
from desktop_harness.input import _parse_combo, KEYCODES


def test_parse_combo_simple():
    kc, flags = _parse_combo("a")
    assert kc == KEYCODES["a"]
    assert flags == 0


def test_parse_combo_cmd_a():
    kc, flags = _parse_combo("cmd+a")
    assert kc == KEYCODES["a"]
    assert flags != 0


def test_parse_combo_multi_modifier():
    kc, flags = _parse_combo("cmd+shift+t")
    assert kc == KEYCODES["t"]
    assert flags != 0


def test_parse_combo_unknown_modifier_raises():
    with pytest.raises(ValueError):
        _parse_combo("foo+a")


def test_parse_combo_unknown_key_raises():
    with pytest.raises(ValueError):
        _parse_combo("cmd+nosuchkey")


def test_keycodes_table_has_arrows():
    for k in ("left", "right", "up", "down"):
        assert k in KEYCODES
