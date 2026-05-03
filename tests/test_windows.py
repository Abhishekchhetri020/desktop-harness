"""windows.py — live tests against TextEdit."""
import time
import pytest
from desktop_harness.windows import (
    list_windows, windows_of, main_window, window_bounds,
    window_move, window_resize, maximize, tile_left,
)


@pytest.mark.live
def test_list_windows_finds_textedit(textedit):
    wins = list_windows(textedit)
    assert isinstance(wins, list)
    assert len(wins) >= 1
    w = wins[0]
    assert {"id", "owner", "x", "y", "width", "height"} <= set(w)


@pytest.mark.live
def test_windows_of_textedit(textedit):
    wins = windows_of(textedit)
    assert isinstance(wins, list)
    assert len(wins) >= 1


@pytest.mark.live
def test_main_window_textedit(textedit):
    w = main_window(textedit)
    assert w is not None


@pytest.mark.live
def test_window_move_resize_textedit(textedit):
    assert window_move(textedit, 100, 100) is True
    assert window_resize(textedit, 700, 500) is True
    time.sleep(0.5)
    b = window_bounds(textedit)
    assert b is not None
    assert abs(b["x"] - 100) < 5
    assert abs(b["width"] - 700) < 5


@pytest.mark.live
def test_window_tile_left(textedit):
    assert tile_left(textedit) is True
    time.sleep(0.3)
