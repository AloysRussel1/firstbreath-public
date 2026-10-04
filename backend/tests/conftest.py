from __future__ import annotations

import pytest

from backend import database, services


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Base, images et cache d'extraction temporaires ; jamais d'appel payant, quel que soit le .env."""
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "firstbreath.sqlite3")
    monkeypatch.setattr(services, "IMAGE_DIR", tmp_path / "images")
    from extraction import client
    monkeypatch.setattr(client, "FOURNISSEUR", "simule")
    monkeypatch.setattr(client, "CACHE", tmp_path / "cache")
    database.initialize()
