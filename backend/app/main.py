"""FastAPI entry point.  Run locally with:  uvicorn app.main:app --reload"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.agent.kb import get_kb, sync
from app.config import get_settings
from app.db import init_db
from app.routers import budget, feedback, projects, public

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


def _kb_refresher(stop: threading.Event) -> None:
    """Pull the site's guides at startup, then every KB_REFRESH_HOURS."""
    s = get_settings()
    while not stop.is_set():
        try:
            sync(get_kb(), s.kb_source_url, s.kb_cache_path)
        except Exception as exc:  # keep serving the cached copy if the site is unreachable
            log.warning("Knowledge base sync failed (using cached copy): %s", exc)
        stop.wait(max(s.kb_refresh_hours, 0.1) * 3600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    get_kb()  # load cached knowledge base from disk
    stop = threading.Event()
    if get_settings().kb_sync_on_startup:
        threading.Thread(target=_kb_refresher, args=(stop,), daemon=True, name="kb-refresh").start()
    yield
    stop.set()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Backend for the Killette Innovations construction project management app "
        "(projects, budget alerts, client metadata, cloud folders, field feedback) and the "
        "Barndo Build Assistant on barndobible.com.",
        lifespan=lifespan,
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
            max_age=3600,
        )

    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok", "version": __version__, "environment": settings.environment}

    app.include_router(projects.router)
    app.include_router(budget.router)
    app.include_router(feedback.router)
    app.include_router(public.router)
    app.mount("/widget", StaticFiles(directory=STATIC_DIR, html=True), name="widget")
    return app


app = create_app()
