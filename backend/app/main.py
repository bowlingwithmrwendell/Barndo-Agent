"""FastAPI entry point.  Run locally with:  uvicorn app.main:app --reload"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.db import init_db
from app.routers import budget, feedback, projects


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Backend for the Killette Innovations construction project management app "
        "(projects, budget alerts, client metadata, cloud folders, field feedback).",
        lifespan=lifespan,
    )
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok", "version": __version__, "environment": settings.environment}

    app.include_router(projects.router)
    app.include_router(budget.router)
    app.include_router(feedback.router)
    return app


app = create_app()
