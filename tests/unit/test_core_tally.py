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
