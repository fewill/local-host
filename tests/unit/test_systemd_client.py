import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lh_dashboard.systemd_client import SystemdClient, SystemdUnavailableError


def _completed(stdout):
    return MagicMock(stdout=stdout, returncode=0)


def test_get_unit_properties_parses_key_value_lines_regardless_of_order():
    """systemctl show --property=A,B,C,D does NOT return values in the
    requested order -- it uses its own internal ordering (confirmed on this
    box: requesting ActiveState,SubState,LoadState,Result came back as
    Result,LoadState,ActiveState,SubState). Lines must be parsed as
    Key=Value, never relied on positionally.
    """
    client = SystemdClient()
    out_of_order_stdout = "Result=success\nLoadState=loaded\nActiveState=inactive\nSubState=dead\n"
    with patch("subprocess.run", return_value=_completed(out_of_order_stdout)) as mock_run:
        result = client.get_unit_properties(
            "foo.service", "system", ["ActiveState", "SubState", "LoadState", "Result"]
        )

    assert result == {
        "ActiveState": "inactive",
        "SubState": "dead",
        "LoadState": "loaded",
        "Result": "success",
    }
    cmd = mock_run.call_args[0][0]
    assert cmd[:3] == ["systemctl", "show", "foo.service"]
    assert "--user" not in cmd
    assert "--value" not in cmd


def test_get_unit_properties_defaults_missing_property_to_empty_string():
    """A property that doesn't apply to this unit type (e.g. Type= for a
    .timer) is simply absent from systemctl's output, not an empty line.
    """
    client = SystemdClient()
    with patch("subprocess.run", return_value=_completed("ActiveState=inactive\n")):
        result = client.get_unit_properties(
            "foo.timer", "system", ["ActiveState", "Type"]
        )

    assert result == {"ActiveState": "inactive", "Type": ""}


def test_get_unit_properties_adds_user_flag_for_user_scope():
    client = SystemdClient()
    with patch("subprocess.run", return_value=_completed("ActiveState=active\n")) as mock_run:
        client.get_unit_properties("foo.service", "user", ["ActiveState"])

    cmd = mock_run.call_args[0][0]
    assert "--user" in cmd


def test_batches_all_properties_into_a_single_call():
    client = SystemdClient()
    with patch(
        "subprocess.run", return_value=_completed("A=a\nB=b\nC=c\n")
    ) as mock_run:
        client.get_unit_properties("foo.service", "system", ["A", "B", "C"])

    assert mock_run.call_count == 1
    cmd = mock_run.call_args[0][0]
    assert "--property=A,B,C" in cmd


def test_missing_binary_raises_unavailable():
    client = SystemdClient()
    with patch("subprocess.run", side_effect=FileNotFoundError()):
        with pytest.raises(SystemdUnavailableError):
            client.get_unit_properties("foo.service", "system", ["ActiveState"])


def test_timeout_raises_unavailable():
    client = SystemdClient()
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="systemctl", timeout=5),
    ):
        with pytest.raises(SystemdUnavailableError):
            client.get_unit_properties("foo.service", "system", ["ActiveState"])


def test_nonzero_exit_raises_unavailable():
    client = SystemdClient()
    err = subprocess.CalledProcessError(returncode=1, cmd=["systemctl"], stderr="boom")
    with patch("subprocess.run", side_effect=err):
        with pytest.raises(SystemdUnavailableError):
            client.get_unit_properties("foo.service", "system", ["ActiveState"])


def test_get_recent_errors_tails_to_max_lines():
    client = SystemdClient()
    with patch("subprocess.run", return_value=_completed("l1\nl2\nl3\nl4\n")):
        lines = client.get_recent_errors("foo.service", "system", "1 hour ago", max_lines=2)

    assert lines == ["l3", "l4"]


def test_get_recent_errors_empty_output():
    client = SystemdClient()
    with patch("subprocess.run", return_value=_completed("")):
        lines = client.get_recent_errors("foo.service", "system", "1 hour ago")

    assert lines == []


def test_list_timers_converts_epoch_microseconds_to_iso():
    client = SystemdClient()
    payload = (
        '[{"next": 1787892807000000, "unit": "foo.timer", "activates": "foo.service"}]'
    )
    with patch("subprocess.run", return_value=_completed(payload)):
        timers = client.list_timers("system")

    assert len(timers) == 1
    assert timers[0]["unit"] == "foo.timer"
    assert timers[0]["activates"] == "foo.service"
    assert timers[0]["next"] is not None
    assert timers[0]["next"].startswith("20")


def test_list_timers_empty_output():
    client = SystemdClient()
    with patch("subprocess.run", return_value=_completed("")):
        timers = client.list_timers("system")

    assert timers == []


def test_list_timers_null_next_stays_none():
    client = SystemdClient()
    payload = '[{"next": null, "unit": "foo.timer", "activates": "foo.service"}]'
    with patch("subprocess.run", return_value=_completed(payload)):
        timers = client.list_timers("system")

    assert timers[0]["next"] is None
