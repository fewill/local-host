import pytest

from lh_dashboard.config import ConfigError, load_config

VALID_YAML = """
version: 1
projects:
  - name: usb-encrypt
    repo: ../usb-encrypt
    units:
      - unit: backup-usb.timer
        scope: system
        label: Backup Timer
        note: "triggers backup-usb.service daily"
"""


def test_valid_config_loads(tmp_path):
    path = tmp_path / "units.yaml"
    path.write_text(VALID_YAML)

    config = load_config(path)
    units = config.units()

    assert len(units) == 1
    assert units[0].unit == "backup-usb.timer"
    assert units[0].scope == "system"
    assert units[0].label == "Backup Timer"
    assert units[0].project == "usb-encrypt"
    assert units[0].note == "triggers backup-usb.service daily"


def test_missing_required_field_raises_named_error(tmp_path):
    bad_yaml = """
version: 1
projects:
  - name: usb-encrypt
    units:
      - unit: backup-usb.timer
        scope: system
"""
    path = tmp_path / "units.yaml"
    path.write_text(bad_yaml)

    with pytest.raises(ConfigError, match="label"):
        load_config(path)


def test_invalid_scope_raises_named_error(tmp_path):
    bad_yaml = """
version: 1
projects:
  - name: usb-encrypt
    units:
      - unit: backup-usb.timer
        scope: bogus
        label: Backup Timer
"""
    path = tmp_path / "units.yaml"
    path.write_text(bad_yaml)

    with pytest.raises(ConfigError, match="scope"):
        load_config(path)


def test_malformed_yaml_raises(tmp_path):
    path = tmp_path / "units.yaml"
    path.write_text("projects: [this is not: valid: yaml")

    with pytest.raises(ConfigError):
        load_config(path)


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does-not-exist.yaml")


def test_unit_not_installed_on_machine_is_not_a_config_error(tmp_path):
    """A unit referenced in config that doesn't exist on this machine is a
    normal per-unit finding (LoadState != loaded), not a config error --
    load_config itself has no way to know and shouldn't try.
    """
    path = tmp_path / "units.yaml"
    path.write_text(VALID_YAML)

    config = load_config(path)

    assert config.units()[0].unit == "backup-usb.timer"
