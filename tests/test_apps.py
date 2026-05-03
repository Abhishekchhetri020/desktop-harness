"""apps.py — list, frontmost, query."""
from desktop_harness import list_apps, frontmost, is_running, pid_of, app_info


def test_list_apps_returns_nonempty():
    apps = list_apps()
    assert isinstance(apps, list)
    assert len(apps) > 0
    sample = apps[0]
    assert {"name", "bundle_id", "pid", "active", "hidden"} <= set(sample)


def test_frontmost_is_dict_or_none():
    f = frontmost()
    assert f is None or "name" in f


def test_is_running_finder_true():
    # Finder is essentially always running on macOS
    assert is_running("Finder") is True


def test_is_running_bogus_false():
    assert is_running("NotAnAppXyz123") is False


def test_pid_of_finder_is_int():
    pid = pid_of("Finder")
    assert isinstance(pid, int) and pid > 0


def test_app_info_finder():
    info = app_info("Finder")
    assert info is not None
    assert info["name"].lower() == "finder"
    assert info["pid"] > 0
