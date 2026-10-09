import json
import subprocess
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from lh_dashboard.systemd_client import (
    SystemdClient,
    SystemdUnavailableError,
    journal_error_from_json,
)


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


def _journal_json(*messages: str, start_usec: int = 1_791_489_606_000_000) -> str:
    return "".join(
        json.dumps({"__REALTIME_TIMESTAMP": str(start_usec + i * 1_000_000), "MESSAGE": m}) + "\n"
        for i, m in enumerate(messages)
    )


def test_get_recent_errors_tails_to_max_lines():
    client = SystemdClient()
    with patch("subprocess.run", return_value=_completed(_journal_json("l1", "l2", "l3", "l4"))):
        errors = client.get_recent_errors("foo.service", "system", "1 hour ago", max_lines=2)

    assert [e.message for e in errors] == ["l3", "l4"]


def test_get_recent_errors_requests_json_and_keeps_timestamp():
    client = SystemdClient()
    usec = 1_791_489_606_410_298
    with patch("subprocess.run", return_value=_completed(_journal_json("boom", start_usec=usec))) as run:
        [err] = client.get_recent_errors("foo.service", "user", "24 hours ago")

    cmd = run.call_args[0][0]
    assert cmd[cmd.index("-o") + 1] == "json"
    expected = datetime.fromtimestamp(usec / 1_000_000, tz=timezone.utc).astimezone()
    assert datetime.fromisoformat(err.timestamp) == expected.replace(microsecond=0)
    assert err.when == expected.strftime("%b %d %H:%M:%S")


def test_journal_error_decodes_byte_array_message():
    err = journal_error_from_json({"__REALTIME_TIMESTAMP": "0", "MESSAGE": list(b"caf\xc3\xa9")})
    assert err.message == "café"


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
