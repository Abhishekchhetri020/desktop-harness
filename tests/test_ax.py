"""ax.py — live tests against TextEdit."""
import pytest
from desktop_harness import (
    app_ax, find, find_all, ax_dump, ax_tree, role, title, get_attr, AXError,
)


@pytest.mark.live
def test_app_ax_returns_root(textedit):
    root = app_ax(textedit)
    assert root is not None
    assert role(root) == "AXApplication"


@pytest.mark.live
def test_find_window(textedit):
    win = find(textedit, role="AXWindow")
    assert win is not None
    assert role(win) == "AXWindow"


@pytest.mark.live
def test_find_all_menu_bar_items(textedit):
    items = find_all(textedit, role="AXMenuBarItem", limit=20)
    titles = [title(i) for i in items if title(i)]
    # TextEdit has File/Edit/Format/View/Window/Help
    assert any("File" in t for t in titles)


@pytest.mark.live
def test_ax_dump_contains_application(textedit):
    s = ax_dump(textedit, max_depth=2)
    assert "AXApplication" in s


@pytest.mark.live
def test_ax_tree_is_dict(textedit):
    t = ax_tree(textedit, max_depth=3)
    assert isinstance(t, dict)
    assert t.get("role") == "AXApplication"


def test_app_ax_for_missing_app_raises():
    with pytest.raises(AXError):
        app_ax("NotAnAppXyz123")
