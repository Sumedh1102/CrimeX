"""FastAPI entry point: ``uvicorn backend.main:app --port 8000``."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.routes import router
from backend.app.services.store import NotReadyError
from backend.app.settings import get_settings
from ml.config import LIMITATION_STATEMENT


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CrimeX API",
        version="0.1.0",
        description=(
            "Explainable spatiotemporal crime-intelligence API for police-station decision "
            "support. Predictions are zone-level Risk(zone, crime_type, time_window) only; "
            "no individual-level output. " + LIMITATION_STATEMENT
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotReadyError)
    async def not_ready(_: Request, exc: NotReadyError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    app.include_router(router, prefix=settings.api_prefix)
    return app


app = create_app()
