import pytest

from tests.fixtures.fake_systemd import FakeSystemdClient


@pytest.fixture
def fake_systemd() -> FakeSystemdClient:
    return FakeSystemdClient()
