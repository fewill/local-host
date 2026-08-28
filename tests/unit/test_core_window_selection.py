import pytest

from lh_dashboard.config import UnitConfig
from lh_dashboard.core import check_unit, select_error_window
from tests.fixtures.fake_systemd import FakeSystemdClient


def test_oneshot_gets_24h_window():
    assert select_error_window("oneshot") == "24 hours ago"


def test_long_running_gets_1h_window():
    assert select_error_window("simple") == "1 hour ago"
    assert select_error_window("notify") == "1 hour ago"


def test_override_wins_regardless_of_type():
    assert select_error_window("oneshot", override="6 hours ago") == "6 hours ago"
    assert select_error_window("simple", override="6 hours ago") == "6 hours ago"


@pytest.mark.parametrize("scope", ["system", "user"])
def test_user_scope_oneshot_gets_24h_window_not_1h(scope):
    """Regression test for the v1 bug: status.sh's print_user_unit hardcoded a
    1h journal window for ALL user-scope units, including oneshots, so a
    user-scope oneshot that failed overnight could still look clean by the
    time someone checked in the morning. The window must be 24h for oneshots
    regardless of scope.
    """
    fake = FakeSystemdClient()
    fake.set_unit(
        "some-job.service",
        scope,
        ActiveState="inactive",
        SubState="dead",
        LoadState="loaded",
        Result="success",
        Type="oneshot",
        ExecMainStatus="0",
        InactiveEnterTimestamp="Tue 2026-08-25 06:00:38 CDT",
    )
    unit_cfg = UnitConfig(
        unit="some-job.service", scope=scope, label="Some Job", project="test"
    )

    check_unit(unit_cfg, fake)

    assert fake.get_recent_errors_calls[-1][2] == "24 hours ago"


def test_long_running_unit_gets_1h_window_via_check_unit():
    fake = FakeSystemdClient()
    fake.set_unit(
        "poller.service",
        "system",
        ActiveState="active",
        SubState="running",
        LoadState="loaded",
        Result="success",
        Type="simple",
    )
    unit_cfg = UnitConfig(
        unit="poller.service", scope="system", label="Poller", project="test"
    )

    check_unit(unit_cfg, fake)

    assert fake.get_recent_errors_calls[-1][2] == "1 hour ago"


def test_per_unit_override_wins_via_check_unit():
    fake = FakeSystemdClient()
    fake.set_unit(
        "holdings.service",
        "user",
        ActiveState="inactive",
        SubState="dead",
        LoadState="loaded",
        Result="success",
        Type="oneshot",
        ExecMainStatus="0",
        InactiveEnterTimestamp="Tue 2026-08-25 06:00:38 CDT",
    )
    unit_cfg = UnitConfig(
        unit="holdings.service",
        scope="user",
        label="Holdings",
        project="test",
        error_window="6 hours ago",
    )

    check_unit(unit_cfg, fake)

    assert fake.get_recent_errors_calls[-1][2] == "6 hours ago"
