import base64
import json
import os

import pytest

KEYS = {"admin-key": "admin", "manager-key": "manager", "field-key": "field", "viewer-key": "viewer"}

os.environ["ENVIRONMENT"] = "test"
os.environ["API_KEYS"] = json.dumps(KEYS)
os.environ["PII_ENCRYPTION_KEY"] = base64.b64encode(b"k" * 32).decode()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "storage"))

    from app.config import get_settings
    from app.db import reset_engine

    get_settings.cache_clear()
    reset_engine()

    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
    reset_engine()
    get_settings.cache_clear()


def h(role: str) -> dict:
    return {"X-API-Key": f"{role}-key"}
