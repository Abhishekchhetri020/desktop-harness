"""screen.py — capture + display info."""
import os
import pytest
from desktop_harness.screen import displays, main_display_size, screenshot


def test_displays_nonempty():
    d = displays()
    assert isinstance(d, list) and len(d) >= 1
    main = [x for x in d if x.get("main")]
    assert len(main) == 1


def test_main_display_size_positive():
    w, h = main_display_size()
    assert w > 0 and h > 0


@pytest.mark.live
def test_screenshot_writes_png(tmp_path):
    out = tmp_path / "shot.png"
    p = screenshot(str(out))
    assert os.path.exists(p)
    assert os.path.getsize(p) > 1024
