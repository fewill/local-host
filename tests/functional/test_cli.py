from lh_dashboard.cli import main
from tests.fixtures.fake_systemd import FakeSystemdClient

DEMO_CONFIG = """
version: 1
projects:
  - name: demo
    units:
      - unit: good.service
        scope: system
        label: Good Service
"""


def _write_config(tmp_path):
    path = tmp_path / "units.yaml"
    path.write_text(DEMO_CONFIG)
    return path


def test_cli_prints_summary_and_exits_zero_when_all_ok(tmp_path, capsys):
    config_path = _write_config(tmp_path)
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

    exit_code = main(["--config", str(config_path), "--no-color"], systemd_client=fake)

    captured = capsys.readouterr()
    assert "Good Service" in captured.out
    assert "All 1 units OK" in captured.out
    assert exit_code == 0


def test_cli_exits_nonzero_when_any_unit_failed(tmp_path, capsys):
    config_path = _write_config(tmp_path)
    fake = FakeSystemdClient()
    fake.set_unit(
        "good.service",
        "system",
        ActiveState="failed",
        SubState="failed",
        LoadState="loaded",
        Result="exit-code",
        Type="simple",
    )

    exit_code = main(["--config", str(config_path), "--no-color"], systemd_client=fake)

    assert exit_code == 1


def test_cli_reports_config_error_and_exits_nonzero(tmp_path, capsys):
    bad_config = tmp_path / "units.yaml"
    bad_config.write_text("not: [valid")

    exit_code = main(["--config", str(bad_config)], systemd_client=FakeSystemdClient())

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "config" in captured.err.lower()


def test_cli_shows_resolved_oneshot_errors_as_earlier_with_timestamps(tmp_path, capsys):
    from datetime import datetime

    from lh_dashboard.systemd_client import JournalError

    path = tmp_path / "units.yaml"
    path.write_text(DEMO_CONFIG.replace("good.service", "job.service"))
    fake = FakeSystemdClient()
    fake.set_unit(
        "job.service", "system",
        ActiveState="inactive", SubState="dead", LoadState="loaded",
        Result="success", Type="oneshot", ExecMainStatus="0",
        InactiveEnterTimestamp="Thu 2026-10-08 21:15:04 MDT",
    )
    dt = datetime(2026, 10, 8, 14, 0, 6).astimezone()
    fake.set_errors("job.service", "system", [
        JournalError(timestamp=dt.isoformat(), when="Oct 08 14:00:06", message="Failed to start job.service"),
    ])

    main(["--config", str(path), "--no-color"], systemd_client=fake)

    out = capsys.readouterr().out
    assert "Earlier failures (before last successful run):" in out
    assert "Oct 08 14:00:06  Failed to start job.service" in out
