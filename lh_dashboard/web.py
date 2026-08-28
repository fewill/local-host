"""Flask app: HTML dashboard + JSON API, both built on the shared core."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from flask import Flask, jsonify, render_template
from markupsafe import escape

from .config import ConfigError, load_config
from .core import StatusChecker, Tally, group_by_project
from .systemd_client import SystemdClient, SystemdClientProtocol

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "units.yaml"


def _serialize(config, statuses, tally: Tally) -> dict:
    groups = group_by_project(config, statuses)
    return {
        "tally": {
            "total": tally.total,
            "ok": tally.ok,
            "failed": tally.failed,
            "summary": tally.summary(),
        },
        "projects": [
            {
                "name": group.name,
                "note": group.note,
                "units": [asdict(status) for status in group.units],
            }
            for group in groups
        ],
    }


def create_app(
    config_path: Path | None = None,
    systemd_client: SystemdClientProtocol | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["CONFIG_PATH"] = Path(config_path) if config_path else DEFAULT_CONFIG
    app.config["SYSTEMD_CLIENT"] = systemd_client or SystemdClient()

    def _snapshot() -> dict:
        config = load_config(app.config["CONFIG_PATH"])
        checker = StatusChecker(app.config["SYSTEMD_CLIENT"])
        statuses, tally = checker.check_all(config)
        return _serialize(config, statuses, tally)

    @app.get("/health")
    def health():
        return jsonify({"service": "local-host-dashboard", "status": "ok"})

    @app.get("/api/status")
    def api_status():
        try:
            data = _snapshot()
        except ConfigError as exc:
            return jsonify({"error": str(exc)}), 500
        return jsonify(data)

    @app.get("/")
    def index():
        try:
            data = _snapshot()
        except ConfigError as exc:
            return (
                f"<h1>Config error</h1><pre>{escape(str(exc))}</pre>",
                500,
            )
        return render_template("index.html", data=data)

    return app
