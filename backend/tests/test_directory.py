import httpx
import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.routers.directory import public_companies


def test_directory_disabled(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        public_companies()
    assert exc.value.status_code == 503


def test_public_whitelist(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    get_settings.cache_clear()

    def read(url, **kwargs):
        assert kwargs["params"]["published"] == "eq.true"
        assert "Authorization" not in kwargs["headers"]
        return httpx.Response(
            200, request=httpx.Request("GET", url), json=[{"id": "test", "notes": "private", "name": "Example"}]
        )

    monkeypatch.setattr(httpx, "get", read)
    assert "notes" not in public_companies()[0]


def test_upstream_error_hidden(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    get_settings.cache_clear()

    def fail(*args, **kwargs):
        raise httpx.ConnectError("secret connection detail")

    monkeypatch.setattr(httpx, "get", fail)
    with pytest.raises(HTTPException) as exc:
        public_companies()
    assert exc.value.detail == "Builder directory is temporarily unavailable"
