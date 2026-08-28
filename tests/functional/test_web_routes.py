from lh_dashboard.web import create_app
from tests.fixtures.fake_systemd import FakeSystemdClient

DEMO_CONFIG = """
version: 1
projects:
  - name: demo
    units:
      - unit: good.service
        scope: system
        label: Good Service
        note: "always running"
      - unit: missing.service
        scope: system
        label: Missing Service
"""


def _make_config(tmp_path):
    path = tmp_path / "units.yaml"
    path.write_text(DEMO_CONFIG)
    return path


def test_health_endpoint(tmp_path):
    app = create_app(config_path=_make_config(tmp_path), systemd_client=FakeSystemdClient())
    client = app.test_client()

    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.get_json() == {"service": "local-host-dashboard", "status": "ok"}


def test_api_status_shape_and_not_found_unit(tmp_path):
    fake = FakeSystemdClient()
    fake.set_unit(
        "good.service",
        "system",
        ActiveState="active",
        SubState="running",
        LoadState="loaded",
        Result="success",
        Type="simple",
    )
    app = create_app(config_path=_make_config(tmp_path), systemd_client=fake)
    client = app.test_client()

    resp = client.get("/api/status")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["tally"]["total"] == 2
    assert data["tally"]["ok"] == 1
    assert data["tally"]["failed"] == 1

    units_by_name = {u["unit"]: u for p in data["projects"] for u in p["units"]}
    assert units_by_name["good.service"]["ok"] is True
    assert units_by_name["good.service"]["color"] == "green"
    assert units_by_name["missing.service"]["ok"] is False
    assert "not found" in units_by_name["missing.service"]["state_display"].lower()


def test_index_page_renders_labels(tmp_path):
    fake = FakeSystemdClient()
    fake.set_unit(
        "good.service",
        "system",
        ActiveState="active",
        SubState="running",
        LoadState="loaded",
        Result="success",
        Type="simple",
    )
    app = create_app(config_path=_make_config(tmp_path), systemd_client=fake)
    client = app.test_client()

    resp = client.get("/")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Good Service" in body
    assert "Missing Service" in body


def test_unregistered_unit_does_not_crash_status_endpoint(tmp_path):
    app = create_app(config_path=_make_config(tmp_path), systemd_client=FakeSystemdClient())
    client = app.test_client()

    resp = client.get("/api/status")

    assert resp.status_code == 200


def test_bad_config_renders_error_page_not_500_traceback(tmp_path):
    bad_config = tmp_path / "units.yaml"
    bad_config.write_text("not: [valid: yaml")
    app = create_app(config_path=bad_config, systemd_client=FakeSystemdClient())
    client = app.test_client()

    resp = client.get("/")

    assert resp.status_code == 500
    assert b"Traceback" not in resp.data
