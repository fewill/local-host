"""Terminal renderer -- ports status.sh's colored output onto the shared core."""
from __future__ import annotations

from .core import ProjectGroup, Tally

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"

_COLOR_CODES = {"green": GREEN, "yellow": YELLOW, "red": RED}


def _c(text: str, color: str, use_color: bool) -> str:
    if not use_color or color not in _COLOR_CODES:
        return text
    return f"{_COLOR_CODES[color]}{text}{RESET}"


def _dim(text: str, use_color: bool) -> str:
    return f"{DIM}{text}{RESET}" if use_color else text


def render(groups: list[ProjectGroup], tally: Tally, use_color: bool = True) -> str:
    lines: list[str] = []

    for group in groups:
        lines.append("")
        lines.append(f"{BOLD}{group.name}{RESET}" if use_color else group.name)
        if group.note:
            lines.append(f"  {_dim(group.note, use_color)}")

        for status in group.units:
            lines.append(
                f"  ▸ {status.label:<20} {_c(status.state_display, status.color, use_color)}"
            )
            if status.note:
                lines.append(f"      {_dim(status.note, use_color)}")

            if status.oneshot:
                if status.oneshot.in_progress:
                    lines.append("      Last run: in progress — result pending")
                else:
                    if status.oneshot.finished_at:
                        lines.append(f"      Finished: {status.oneshot.finished_at}")
                    if status.oneshot.exit_code is not None:
                        exit_color = "green" if status.oneshot.exit_ok else "red"
                        exit_label = (
                            f"{status.oneshot.exit_code} (success)"
                            if status.oneshot.exit_ok
                            else f"{status.oneshot.exit_code} (failed)"
                        )
                        lines.append(f"      Last exit: {_c(exit_label, exit_color, use_color)}")
            elif status.active_since:
                lines.append(f"      Active since: {status.active_since}")

            if status.next_run:
                lines.append(f"      Next run: {status.next_run}")
            if status.query_error:
                lines.append(f"      {_c('Query error: ' + status.query_error, 'red', use_color)}")
            for err in status.recent_errors:
                lines.append(f"      {_c(err, 'red', use_color)}")

    lines.append("")
    summary_color = "green" if tally.failed == 0 else "red"
    lines.append(_c(tally.summary(), summary_color, use_color))
    lines.append(_dim("Run 'journalctl -u <unit> -f' to tail live logs", use_color))
    return "\n".join(lines)
