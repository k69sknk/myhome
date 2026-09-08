"""Fixtures partagees."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from homekeeper_api.config import Settings
from homekeeper_api.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Reglages isoles : jamais /data, qui n'existe que dans le conteneur."""
    return Settings(data_dir=tmp_path / "data", frontend_dir=tmp_path / "www")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def client_avec_frontend(settings: Settings) -> Iterator[TestClient]:
    """Client avec une coquille HTML minimale, comme apres un build Vite."""
    settings.frontend_dir.mkdir(parents=True, exist_ok=True)
    (settings.frontend_dir / "index.html").write_text(
        '<!doctype html><html><head><base href="__HOMEKEEPER_BASE__">'
        '</head><body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client
