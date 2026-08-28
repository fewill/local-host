from lh_dashboard.config import Config, ProjectConfig, UnitConfig
from lh_dashboard.render_readme import BEGIN_MARKER, END_MARKER, render_units_markdown, update_readme


def _demo_config():
    return Config(
        version=1,
        projects=[
            ProjectConfig(
                name="usb-encrypt",
                repo="../usb-encrypt",
                units=[
                    UnitConfig(
                        unit="backup-usb.timer",
                        scope="system",
                        label="Backup Timer",
                        project="usb-encrypt",
                        note="triggers backup-usb.service daily",
                    ),
                ],
            ),
            ProjectConfig(name="versionpulse", repo="../versionpulse", note="runs on EC2"),
        ],
    )


def test_render_units_markdown_includes_table_and_note_only_project():
    markdown = render_units_markdown(_demo_config())

    assert "### usb-encrypt (`../usb-encrypt`)" in markdown
    assert "| `backup-usb.timer` | Timer | triggers backup-usb.service daily |" in markdown
    assert "### versionpulse (`../versionpulse`)" in markdown
    assert "runs on EC2" in markdown


def test_update_readme_replaces_only_content_between_markers(tmp_path):
    readme_path = tmp_path / "README.md"
    readme_path.write_text(
        f"# Title\n\nSome prose before.\n\n{BEGIN_MARKER}\nold stale content\n{END_MARKER}\n\nProse after.\n"
    )
    config_path = tmp_path / "units.yaml"
    config_path.write_text(
        """
version: 1
projects:
  - name: usb-encrypt
    units:
      - unit: backup-usb.timer
        scope: system
        label: Backup Timer
        note: "triggers backup-usb.service daily"
"""
    )

    update_readme(readme_path, config_path)

    result = readme_path.read_text()
    assert "Some prose before." in result
    assert "Prose after." in result
    assert "old stale content" not in result
    assert "backup-usb.timer" in result
