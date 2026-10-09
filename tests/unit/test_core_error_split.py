"""Errors from before a oneshot's last successful run are split out as 'earlier'.

Regression for the waiting-monitor case: a unit that failed at 14:00 and then
succeeded every run after still showed three red 'Failed to start' lines under
'Last exit: 0 (success)' until the 24h window aged them out.
"""
from datetime import datetime

import pytest

from lh_dashboard.config import UnitConfig
from lh_dashboard.core import (
    OneshotInfo,
    check_unit,
    parse_systemd_timestamp,
    split_errors_at_success,
)
from lh_dashboard.systemd_client import JournalError
from tests.fixtures.fake_systemd import FakeSystemdClient

FINISHED = "Thu 2026-10-08 21:15:04 MDT"


def _err(hhmmss: str, message: str = "Failed to start job.service") -> JournalError:
    dt = datetime.strptime(f"2026-10-08 {hhmmss}", "%Y-%m-%d %H:%M:%S").astimezone()
    return JournalError(timestamp=dt.isoformat(), when=dt.strftime("%b %d %H:%M:%S"), message=message)


def _oneshot(exit_ok, finished_at=FINISHED, in_progress=False) -> OneshotInfo:
    return OneshotInfo(
        in_progress=in_progress,
        finished_at=finished_at,
        exit_code=None if exit_ok is None else (0 if exit_ok else 1),
        exit_ok=exit_ok,
    )


def test_parse_systemd_timestamp_reads_local_time():
    parsed = parse_systemd_timestamp(FINISHED)
    assert parsed is not None
    assert parsed.replace(tzinfo=None) == datetime(2026, 10, 8, 21, 15, 4)
    assert parsed.tzinfo is not None


@pytest.mark.parametrize("raw", [None, "", "n/a", "Thu garbage here"])
def test_parse_systemd_timestamp_bad_input(raw):
    assert parse_systemd_timestamp(raw) is None


def test_errors_before_success_are_earlier():
    errors = [_err("13:45:04"), _err("14:00:06")]
    recent, earlier = split_errors_at_success(errors, _oneshot(True))
    assert recent == []
    assert earlier == errors


def test_error_after_success_stays_recent():
    before, after = _err("14:00:06"), _err("21:20:00")
    recent, earlier = split_errors_at_success([before, after], _oneshot(True))
    assert recent == [after]
    assert earlier == [before]


@pytest.mark.parametrize("oneshot", [
    None,                                   # not a oneshot
    _oneshot(False),                        # last run failed
    _oneshot(None),                         # exit unknown
    _oneshot(True, in_progress=True),       # mid-run: finish time is stale
    _oneshot(True, finished_at=None),       # no finish time
    _oneshot(True, finished_at="garbage"),  # unparseable finish time
])
def test_no_split_unless_last_run_known_good(oneshot):
    errors = [_err("14:00:06")]
    assert split_errors_at_success(errors, oneshot) == (errors, [])


def test_check_unit_populates_earlier_errors():
    fake = FakeSystemdClient()
    fake.set_unit(
        "job.service", "user",
        ActiveState="inactive", SubState="dead", LoadState="loaded",
        Result="success", Type="oneshot", ExecMainStatus="0",
        InactiveEnterTimestamp=FINISHED,
    )
    fake.set_errors("job.service", "user", [_err("13:45:04"), _err("14:00:06")])

    status = check_unit(UnitConfig(unit="job.service", scope="user", label="Job", project="t"), fake)

    assert status.color == "green"
    assert status.recent_errors == []
    assert [e.when for e in status.earlier_errors] == ["Oct 08 13:45:04", "Oct 08 14:00:06"]
