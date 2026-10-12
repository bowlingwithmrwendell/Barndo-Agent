import base64
import json
import os

import pytest

KEYS = {"admin-key": "admin", "manager-key": "manager", "field-key": "field", "viewer-key": "viewer"}

os.environ["ENVIRONMENT"] = "test"
os.environ["API_KEYS"] = json.dumps(KEYS)
os.environ["PII_ENCRYPTION_KEY"] = base64.b64encode(b"k" * 32).decode()
os.environ["KB_SYNC_ON_STARTUP"] = "false"  # never hit the real site from tests


def _reset_singletons():
    from app.agent.kb import reset_kb
    from app.config import get_settings
    from app.db import reset_engine
    from app.routers import public

    get_settings.cache_clear()
    reset_engine()
    reset_kb()
    public._limiter.cache_clear()
    public._estimate_limiter.cache_clear()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("KB_CACHE_PATH", str(tmp_path / "kb.json"))
    _reset_singletons()

    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c
    _reset_singletons()


def h(role: str) -> dict:
    return {"X-API-Key": f"{role}-key"}
