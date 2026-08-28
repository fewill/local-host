"""Regenerates README.md's per-project unit tables from config/units.yaml so
the two can't drift apart the way CLAUDE.md's tracked-projects list already
had from README.md before this rewrite. Hand-written prose outside the
BEGIN/END markers (AWS backend notes, VPN/1Password dependencies, install
steps) is left untouched.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Config, load_config

BEGIN_MARKER = "<!-- BEGIN GENERATED UNITS -->"
END_MARKER = "<!-- END GENERATED UNITS -->"

DEFAULT_README = Path(__file__).resolve().parent.parent / "README.md"
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "units.yaml"


def _unit_kind(unit: str) -> str:
    return "Timer" if unit.endswith(".timer") else "Service"


def render_units_markdown(config: Config) -> str:
    lines: list[str] = []
    for project in config.projects:
        heading = f"### {project.name} (`{project.repo}`)" if project.repo else f"### {project.name}"
        lines.append(heading)
        lines.append("")
        if project.note:
            lines.append(project.note)
            lines.append("")
        if project.units:
            lines.append("| Unit | Type | Purpose |")
            lines.append("|---|---|---|")
            for unit in project.units:
                purpose = (unit.note or "").replace("|", "\\|")
                lines.append(f"| `{unit.unit}` | {_unit_kind(unit.unit)} | {purpose} |")
            lines.append("")
    return "\n".join(lines).rstrip("\n")


def update_readme(readme_path: Path, config_path: Path) -> None:
    config = load_config(config_path)
    generated = render_units_markdown(config)
    text = readme_path.read_text()
    if BEGIN_MARKER not in text or END_MARKER not in text:
        raise ValueError(
            f"{readme_path} is missing {BEGIN_MARKER}/{END_MARKER} markers"
        )
    before, rest = text.split(BEGIN_MARKER, 1)
    _, after = rest.split(END_MARKER, 1)
    new_text = f"{before}{BEGIN_MARKER}\n\n{generated}\n\n{END_MARKER}{after}"
    readme_path.write_text(new_text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lh-render-readme")
    parser.add_argument("--readme", default=str(DEFAULT_README))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    update_readme(Path(args.readme), Path(args.config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
