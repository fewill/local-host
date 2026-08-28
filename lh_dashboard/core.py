"""Status-checking core shared by the terminal (cli.py) and web (web.py) renderers.

All systemd interaction goes through SystemdClientProtocol so this module
never shells out itself and can be unit-tested with a fake.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Config, UnitConfig
from .systemd_client import SystemdClientProtocol, SystemdUnavailableError

ONESHOT_WINDOW = "24 hours ago"
DEFAULT_WINDOW = "1 hour ago"

PROPERTIES = [
    "ActiveState",
    "SubState",
    "LoadState",
    "Result",
    "Type",
    "ExecMainExitTimestamp",
    "ActiveEnterTimestamp",
    "InactiveEnterTimestamp",
    "ExecMainStatus",
]


@dataclass
class OneshotInfo:
    in_progress: bool
    finished_at: str | None = None
    exit_code: int | None = None
    exit_ok: bool | None = None


def classify_oneshot(props: dict[str, str]) -> OneshotInfo:
    """Classify a Type=oneshot unit's current run state from raw systemd properties.

    A oneshot sits at inactive (dead) between runs, so ActiveState alone can't
    say whether the last run succeeded. While a run is in flight, systemd
    resets ExecMainStatus to 0 and leaves InactiveEnterTimestamp pointing at
    the *previous* run -- reporting either mid-run would misreport a stale
    result as current, so both fields are deliberately withheld while
    in_progress is True.
    """
    active_state = props.get("ActiveState", "")
    if active_state in ("active", "activating"):
        return OneshotInfo(in_progress=True)

    exit_code_raw = (props.get("ExecMainStatus") or "").strip()
    exit_code = int(exit_code_raw) if exit_code_raw else None
    finished_at = props.get("InactiveEnterTimestamp") or None
    exit_ok = None if exit_code is None else exit_code == 0
    return OneshotInfo(
        in_progress=False,
        finished_at=finished_at,
        exit_code=exit_code,
        exit_ok=exit_ok,
    )


def select_error_window(unit_type: str, override: str | None = None) -> str:
    """Pick the journalctl --since window for a unit's recent-errors check.

    Oneshots get a 24h window regardless of scope, since they only run when
    triggered (e.g. by a timer) and a short window can hide an overnight
    failure entirely by the time someone looks. Everything else gets 1h.
    An explicit per-unit config override always wins. Scope is deliberately
    not a parameter here: the v1 script's bug was a user-scope oneshot
    silently getting the wrong (1h) window, and scope-blindness is what
    prevents that class of bug from being reintroduced.
    """
    if override:
        return override
    return ONESHOT_WINDOW if unit_type == "oneshot" else DEFAULT_WINDOW


@dataclass
class UnitStatus:
    unit: str
    scope: str
    label: str
    project: str
    note: str | None
    ok: bool
    color: str  # "green" | "yellow" | "red"
    state_display: str
    unit_type: str = ""
    active_state: str = ""
    sub_state: str = ""
    result: str = ""
    active_since: str | None = None
    next_run: str | None = None
    oneshot: OneshotInfo | None = None
    recent_errors: list[str] = field(default_factory=list)
    query_error: str | None = None


def check_unit(
    unit_cfg: UnitConfig,
    systemd: SystemdClientProtocol,
    timers: list[dict] | None = None,
) -> UnitStatus:
    try:
        props = systemd.get_unit_properties(unit_cfg.unit, unit_cfg.scope, PROPERTIES)
    except SystemdUnavailableError as exc:
        return UnitStatus(
            unit=unit_cfg.unit,
            scope=unit_cfg.scope,
            label=unit_cfg.label,
            project=unit_cfg.project,
            note=unit_cfg.note,
            ok=False,
            color="red",
            state_display="Query failed",
            query_error=str(exc),
        )

    load_state = props.get("LoadState", "")
    if load_state != "loaded":
        return UnitStatus(
            unit=unit_cfg.unit,
            scope=unit_cfg.scope,
            label=unit_cfg.label,
            project=unit_cfg.project,
            note=unit_cfg.note,
            ok=False,
            color="red",
            state_display="Unit not found / not loaded",
            active_state=props.get("ActiveState", ""),
            sub_state=props.get("SubState", ""),
        )

    active_state = props.get("ActiveState", "")
    sub_state = props.get("SubState", "")
    result = props.get("Result", "")
    unit_type = props.get("Type", "")

    ok = active_state != "failed" and result != "failed"

    oneshot: OneshotInfo | None = None
    if unit_type == "oneshot":
        oneshot = classify_oneshot(props)
        if oneshot.in_progress:
            color = "yellow"
        elif oneshot.exit_ok is True:
            color = "green"
        elif oneshot.exit_ok is False:
            color = "red"
        else:
            color = "yellow"
    elif not ok:
        color = "red"
    elif active_state == "active":
        color = "green"
    else:
        color = "yellow"

    state_display = f"{active_state} ({sub_state})" if sub_state else active_state

    window = select_error_window(unit_type, unit_cfg.error_window)
    query_error: str | None = None
    try:
        recent_errors = systemd.get_recent_errors(unit_cfg.unit, unit_cfg.scope, window)
    except SystemdUnavailableError as exc:
        recent_errors = []
        query_error = str(exc)

    next_run = None
    if timers:
        for entry in timers:
            if entry.get("unit") == unit_cfg.unit:
                next_run = entry.get("next")
                break

    return UnitStatus(
        unit=unit_cfg.unit,
        scope=unit_cfg.scope,
        label=unit_cfg.label,
        project=unit_cfg.project,
        note=unit_cfg.note,
        ok=ok,
        color=color,
        state_display=state_display,
        unit_type=unit_type,
        active_state=active_state,
        sub_state=sub_state,
        result=result,
        active_since=props.get("ActiveEnterTimestamp") or None,
        next_run=next_run,
        oneshot=oneshot,
        recent_errors=recent_errors,
        query_error=query_error,
    )


@dataclass
class ProjectGroup:
    name: str
    note: str | None
    units: list[UnitStatus] = field(default_factory=list)


def group_by_project(config: Config, statuses: list[UnitStatus]) -> list[ProjectGroup]:
    """Groups flat check_all() results back into config order, including
    note-only projects (e.g. versionpulse, which runs on remote EC2 and has
    no locally-checkable unit) that would otherwise have no statuses at all.
    """
    status_by_key = {(s.unit, s.scope): s for s in statuses}
    groups = []
    for project in config.projects:
        unit_statuses = [
            status_by_key[(unit_cfg.unit, unit_cfg.scope)] for unit_cfg in project.units
        ]
        groups.append(ProjectGroup(name=project.name, note=project.note, units=unit_statuses))
    return groups


@dataclass
class Tally:
    total: int
    ok: int
    failed: int

    def summary(self) -> str:
        if self.failed == 0:
            return f"All {self.total} units OK"
        return f"{self.ok} OK • {self.failed} FAILED (of {self.total} total)"


class StatusChecker:
    def __init__(self, systemd: SystemdClientProtocol) -> None:
        self.systemd = systemd

    def check_all(self, config: Config) -> tuple[list[UnitStatus], Tally]:
        timers_by_scope: dict[str, list[dict]] = {}
        for scope in ("system", "user"):
            try:
                timers_by_scope[scope] = self.systemd.list_timers(scope)
            except SystemdUnavailableError:
                timers_by_scope[scope] = []

        statuses = [
            check_unit(unit_cfg, self.systemd, timers_by_scope.get(unit_cfg.scope))
            for unit_cfg in config.units()
        ]

        total = len(statuses)
        ok_count = sum(1 for status in statuses if status.ok)
        return statuses, Tally(total=total, ok=ok_count, failed=total - ok_count)
