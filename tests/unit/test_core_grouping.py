from lh_dashboard.config import Config, ProjectConfig, UnitConfig
from lh_dashboard.core import StatusChecker, group_by_project
from tests.fixtures.fake_systemd import FakeSystemdClient


def test_note_only_project_with_no_units_is_preserved():
    """A project like versionpulse (runs on remote EC2, nothing to check
    locally) has a note but zero units -- it must still appear as a group so
    its context isn't silently dropped from the dashboard.
    """
    config = Config(
        version=1,
        projects=[
            ProjectConfig(name="versionpulse", repo="../versionpulse", units=[], note="runs on EC2"),
            ProjectConfig(
                name="usb-encrypt",
                repo="../usb-encrypt",
                units=[UnitConfig(unit="backup-usb.timer", scope="system", label="Backup Timer", project="usb-encrypt")],
            ),
        ],
    )
    fake = FakeSystemdClient()
    fake.set_unit(
        "backup-usb.timer", "system",
        ActiveState="active", SubState="waiting", LoadState="loaded", Result="success", Type="",
    )
    statuses, _ = StatusChecker(fake).check_all(config)

    groups = group_by_project(config, statuses)

    assert [g.name for g in groups] == ["versionpulse", "usb-encrypt"]
    assert groups[0].note == "runs on EC2"
    assert groups[0].units == []
    assert len(groups[1].units) == 1
    assert groups[1].units[0].unit == "backup-usb.timer"
