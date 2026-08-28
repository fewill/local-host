from lh_dashboard.core import classify_oneshot


def test_mid_run_never_surfaces_stale_fields():
    """systemd resets ExecMainStatus to 0 and leaves InactiveEnterTimestamp
    pointing at the previous run while a oneshot is in flight -- both must be
    withheld, not surfaced as if they described the run in progress.
    """
    props = {
        "ActiveState": "active",
        "Type": "oneshot",
        "ExecMainStatus": "0",
        "InactiveEnterTimestamp": "Mon 2026-08-24 02:00:00 CDT",
    }
    info = classify_oneshot(props)
    assert info.in_progress is True
    assert info.exit_code is None
    assert info.exit_ok is None
    assert info.finished_at is None


def test_activating_counts_as_in_progress():
    props = {"ActiveState": "activating", "Type": "oneshot"}
    info = classify_oneshot(props)
    assert info.in_progress is True


def test_idle_success():
    props = {
        "ActiveState": "inactive",
        "Type": "oneshot",
        "ExecMainStatus": "0",
        "InactiveEnterTimestamp": "Tue 2026-08-25 06:00:38 CDT",
    }
    info = classify_oneshot(props)
    assert info.in_progress is False
    assert info.exit_code == 0
    assert info.exit_ok is True
    assert info.finished_at == "Tue 2026-08-25 06:00:38 CDT"


def test_idle_failure():
    props = {
        "ActiveState": "failed",
        "Type": "oneshot",
        "ExecMainStatus": "1",
        "InactiveEnterTimestamp": "Tue 2026-08-11 02:27:00 CDT",
    }
    info = classify_oneshot(props)
    assert info.in_progress is False
    assert info.exit_code == 1
    assert info.exit_ok is False


def test_never_run_has_no_exit_info():
    props = {
        "ActiveState": "inactive",
        "Type": "oneshot",
        "ExecMainStatus": "",
        "InactiveEnterTimestamp": "",
    }
    info = classify_oneshot(props)
    assert info.in_progress is False
    assert info.exit_code is None
    assert info.exit_ok is None
    assert info.finished_at is None
