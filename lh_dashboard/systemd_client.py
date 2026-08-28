"""The only module in this package that shells out to systemctl/journalctl.

Everything else depends on SystemdClientProtocol so tests never need a real
systemd to run against.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from typing import Protocol


class SystemdUnavailableError(Exception):
    """Raised when systemctl/journalctl cannot be queried for a unit."""


class SystemdClientProtocol(Protocol):
    def get_unit_properties(
        self, unit: str, scope: str, properties: list[str]
    ) -> dict[str, str]: ...

    def get_recent_errors(
        self, unit: str, scope: str, since: str, max_lines: int = 3
    ) -> list[str]: ...

    def list_timers(self, scope: str) -> list[dict]: ...


class SystemdClient:
    """Real implementation, backed by subprocess calls to systemctl/journalctl."""

    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout

    def _scope_flag(self, scope: str) -> list[str]:
        return ["--user"] if scope == "user" else []

    def _run(self, cmd: list[str]) -> str:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=True,
            )
        except FileNotFoundError as exc:
            raise SystemdUnavailableError(f"command not found: {cmd[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise SystemdUnavailableError(
                f"timed out running: {' '.join(cmd)}"
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise SystemdUnavailableError(
                f"command failed ({exc.returncode}): {' '.join(cmd)}: {stderr}"
            ) from exc
        return result.stdout

    def get_unit_properties(
        self, unit: str, scope: str, properties: list[str]
    ) -> dict[str, str]:
        cmd = [
            "systemctl",
            *self._scope_flag(scope),
            "show",
            unit,
            f"--property={','.join(properties)}",
        ]
        stdout = self._run(cmd)
        # Deliberately NOT using --value here: systemctl's --property output
        # order does not match the order the properties were requested in
        # (it uses its own internal ordering), so each line must be parsed
        # as Key=Value rather than relied on positionally. A property that
        # doesn't apply to this unit type (e.g. Type= for a .timer) is
        # simply absent from the output, hence the "" defaults below.
        result = {prop: "" for prop in properties}
        for line in stdout.splitlines():
            key, sep, value = line.partition("=")
            if sep and key in result:
                result[key] = value
        return result

    def get_recent_errors(
        self, unit: str, scope: str, since: str, max_lines: int = 3
    ) -> list[str]:
        cmd = [
            "journalctl",
            *self._scope_flag(scope),
            "-u",
            unit,
            "--since",
            since,
            "-p",
            "err",
            "-o",
            "cat",
            "--no-pager",
        ]
        stdout = self._run(cmd)
        lines = [line for line in stdout.splitlines() if line.strip()]
        return lines[-max_lines:] if max_lines else lines

    def list_timers(self, scope: str) -> list[dict]:
        cmd = [
            "systemctl",
            *self._scope_flag(scope),
            "list-timers",
            "--all",
            "-o",
            "json",
        ]
        stdout = self._run(cmd)
        raw = json.loads(stdout) if stdout.strip() else []
        timers = []
        for entry in raw:
            next_usec = entry.get("next")
            next_iso = None
            if next_usec:
                next_iso = (
                    datetime.fromtimestamp(next_usec / 1_000_000, tz=timezone.utc)
                    .astimezone()
                    .isoformat(timespec="seconds")
                )
            timers.append(
                {
                    "unit": entry.get("unit"),
                    "activates": entry.get("activates"),
                    "next": next_iso,
                }
            )
        return timers
