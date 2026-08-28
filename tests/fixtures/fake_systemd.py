"""In-memory stand-in for SystemdClientProtocol, used by tests instead of
shelling out to the real systemctl/journalctl.
"""
from __future__ import annotations


class FakeSystemdClient:
    def __init__(self) -> None:
        self._units: dict[tuple[str, str], dict[str, str]] = {}
        self._errors: dict[tuple[str, str], list[str]] = {}
        self._timers: dict[str, list[dict]] = {"system": [], "user": []}
        self.get_recent_errors_calls: list[tuple[str, str, str, int]] = []

    def set_unit(self, unit: str, scope: str, **properties: str) -> None:
        self._units[(unit, scope)] = properties

    def set_errors(self, unit: str, scope: str, lines: list[str]) -> None:
        self._errors[(unit, scope)] = list(lines)

    def set_timers(self, scope: str, timers: list[dict]) -> None:
        self._timers[scope] = timers

    def get_unit_properties(
        self, unit: str, scope: str, properties: list[str]
    ) -> dict[str, str]:
        stored = self._units.get((unit, scope))
        if stored is None:
            return {p: ("not-found" if p == "LoadState" else "") for p in properties}
        return {p: stored.get(p, "") for p in properties}

    def get_recent_errors(
        self, unit: str, scope: str, since: str, max_lines: int = 3
    ) -> list[str]:
        self.get_recent_errors_calls.append((unit, scope, since, max_lines))
        lines = self._errors.get((unit, scope), [])
        return lines[-max_lines:] if max_lines else lines

    def list_timers(self, scope: str) -> list[dict]:
        return self._timers.get(scope, [])
