"""Terminal entry point: lh-status."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .core import StatusChecker, group_by_project
from .render_terminal import render
from .systemd_client import SystemdClient, SystemdClientProtocol

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "units.yaml"


def main(
    argv: list[str] | None = None,
    systemd_client: SystemdClientProtocol | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="lh-status", description="Local host process status dashboard"
    )
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG), help="Path to units.yaml"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable ANSI color output"
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(Path(args.config))
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    checker = StatusChecker(systemd_client or SystemdClient())
    statuses, tally = checker.check_all(config)
    groups = group_by_project(config, statuses)
    print(render(groups, tally, use_color=not args.no_color))
    return 0 if tally.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
