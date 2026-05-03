"""applescript.py — small AppleScripts that don't touch app state."""
import pytest
from desktop_harness import osascript, jxa, osascript_app


def test_osascript_arithmetic():
    out = osascript("return 1 + 2 + 3")
    assert out.strip() == "6"


def test_osascript_string():
    out = osascript('return "hello"')
    assert out.strip() == "hello"


def test_jxa_arithmetic():
    out = jxa("(1+2+3).toString()")
    assert out.strip() == "6"


def test_osascript_app_finder_get_name():
    out = osascript_app("Finder", "return name")
    assert "Finder" in out


def test_osascript_failure_raises():
    with pytest.raises(RuntimeError):
        osascript('this is not valid applescript at all !!!')
