"""Loads config/units.yaml, the single source of truth for tracked units,
read by both the terminal renderer and the web dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

VALID_SCOPES = {"system", "user"}


class ConfigError(Exception):
    """Raised when units.yaml is missing, malformed, or fails validation."""


@dataclass
class UnitConfig:
    unit: str
    scope: str
    label: str
    project: str
    note: str | None = None
    error_window: str | None = None


@dataclass
class ProjectConfig:
    name: str
    repo: str | None
    units: list[UnitConfig] = field(default_factory=list)
    note: str | None = None


@dataclass
class Config:
    version: int
    projects: list[ProjectConfig] = field(default_factory=list)

    def units(self) -> list[UnitConfig]:
        return [unit for project in self.projects for unit in project.units]


def load_config(path: Path) -> Config:
    path = Path(path)
    try:
        raw_text = path.read_text()
    except OSError as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")

    projects_raw = data.get("projects")
    if projects_raw is None:
        raise ConfigError(f"{path}: missing required field 'projects'")
    if not isinstance(projects_raw, list):
        raise ConfigError(f"{path}: 'projects' must be a list")

    projects: list[ProjectConfig] = []
    for p_index, project_raw in enumerate(projects_raw):
        if not isinstance(project_raw, dict):
            raise ConfigError(f"{path}: projects[{p_index}] must be a mapping")

        name = project_raw.get("name")
        if not name:
            raise ConfigError(
                f"{path}: projects[{p_index}] missing required field 'name'"
            )

        units_raw = project_raw.get("units", [])
        if not isinstance(units_raw, list):
            raise ConfigError(f"{path}: project '{name}' field 'units' must be a list")
        if not units_raw and not project_raw.get("note"):
            raise ConfigError(
                f"{path}: project '{name}' must have either 'units' or a 'note'"
            )

        units: list[UnitConfig] = []
        for u_index, unit_raw in enumerate(units_raw):
            if not isinstance(unit_raw, dict):
                raise ConfigError(
                    f"{path}: project '{name}' units[{u_index}] must be a mapping"
                )
            for required in ("unit", "scope", "label"):
                if not unit_raw.get(required):
                    raise ConfigError(
                        f"{path}: project '{name}' units[{u_index}] "
                        f"missing required field '{required}'"
                    )
            scope = unit_raw["scope"]
            if scope not in VALID_SCOPES:
                raise ConfigError(
                    f"{path}: project '{name}' unit '{unit_raw['unit']}' has "
                    f"invalid scope '{scope}' (must be one of {sorted(VALID_SCOPES)})"
                )
            units.append(
                UnitConfig(
                    unit=unit_raw["unit"],
                    scope=scope,
                    label=unit_raw["label"],
                    project=name,
                    note=unit_raw.get("note"),
                    error_window=unit_raw.get("error_window"),
                )
            )

        projects.append(
            ProjectConfig(
                name=name,
                repo=project_raw.get("repo"),
                units=units,
                note=project_raw.get("note"),
            )
        )

    return Config(version=data.get("version") or 1, projects=projects)
