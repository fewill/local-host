from lh_dashboard.config import Config, ProjectConfig, UnitConfig
from lh_dashboard.core import StatusChecker, Tally
from tests.fixtures.fake_systemd import FakeSystemdClient


def test_all_ok_summary():
    tally = Tally(total=5, ok=5, failed=0)
    assert tally.summary() == "All 5 units OK"


def test_some_failed_summary():
    tally = Tally(total=5, ok=3, failed=2)
    assert tally.summary() == "3 OK • 2 FAILED (of 5 total)"


def test_check_all_tally_mixed_ok_and_failed():
    fake = FakeSystemdClient()
    fake.set_unit(
        "good.service",
        "system",
        ActiveState="active",
        SubState="running",
        LoadState="loaded",
        Result="success",
        Type="simple",
    )
    fake.set_unit(
        "bad.service",
        "system",
        ActiveState="failed",
        SubState="failed",
        LoadState="loaded",
        Result="exit-code",
        Type="simple",
    )
    units = [
        UnitConfig(unit="good.service", scope="system", label="Good", project="test"),
        UnitConfig(unit="bad.service", scope="system", label="Bad", project="test"),
    ]
    config = Config(version=1, projects=[ProjectConfig(name="test", repo=None, units=units)])

    statuses, tally = StatusChecker(fake).check_all(config)

    assert tally.total == 2
    assert tally.ok == 1
    assert tally.failed == 1
    assert tally.summary() == "1 OK • 1 FAILED (of 2 total)"
    assert {s.unit: s.ok for s in statuses} == {"good.service": True, "bad.service": False}


def test_not_loaded_unit_counts_as_failed():
    fake = FakeSystemdClient()
    units = [UnitConfig(unit="ghost.service", scope="system", label="Ghost", project="test")]
    config = Config(version=1, projects=[ProjectConfig(name="test", repo=None, units=units)])

    statuses, tally = StatusChecker(fake).check_all(config)

    assert tally.failed == 1
    assert statuses[0].ok is False
    assert "not found" in statuses[0].state_display.lower()


def _oneshot_tally(**props):
    fake = FakeSystemdClient()
    fake.set_unit(
        "job.service",
        "user",
        LoadState="loaded",
        Type="oneshot",
        **props,
    )
    units = [UnitConfig(unit="job.service", scope="user", label="Job", project="test")]
    config = Config(version=1, projects=[ProjectConfig(name="test", repo=None, units=units)])
    return StatusChecker(fake).check_all(config)


def test_oneshot_nonzero_exit_counts_as_failed_after_state_cleared():
    """Mirrors waiting-monitor.service on 2026-10-12: the last run exited 1,
    but systemd reported inactive (dead) with Result=success, and the footer
    claimed every unit was OK while the row rendered red."""
    statuses, tally = _oneshot_tally(
        ActiveState="inactive",
        SubState="dead",
        Result="success",
        ExecMainStatus="1",
    )

    assert statuses[0].ok is False
    assert statuses[0].color == "red"
    assert tally.failed == 1
    assert tally.summary() == "0 OK • 1 FAILED (of 1 total)"


def test_oneshot_zero_exit_counts_as_ok():
    statuses, tally = _oneshot_tally(
        ActiveState="inactive",
        SubState="dead",
        Result="success",
        ExecMainStatus="0",
    )

    assert statuses[0].ok is True
    assert tally.summary() == "All 1 units OK"


def test_oneshot_in_progress_is_not_failed_by_stale_exit():
    statuses, tally = _oneshot_tally(
        ActiveState="activating",
        SubState="start",
        Result="success",
        ExecMainStatus="1",
    )

    assert statuses[0].ok is True
    assert tally.failed == 0


def test_oneshot_never_run_counts_as_ok():
    statuses, tally = _oneshot_tally(
        ActiveState="inactive",
        SubState="dead",
        Result="success",
        ExecMainStatus="",
    )

    assert statuses[0].ok is True
    assert tally.failed == 0
