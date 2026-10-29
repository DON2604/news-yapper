from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import api_router
from app.config import get_settings
from app.db import get_engine
from app.errors import DomainError

log = logging.getLogger("aks.api")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Aajke Ki Scene? API",
        version="0.1.0",
        description="Banglish-first current affairs + exam prep. User-facing reads never call an AI provider.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.app_base_url],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"detail": str(exc) or exc.__class__.__name__}
        )

    @app.get("/health", tags=["health"])
    def health() -> dict[str, Any]:
        db_ok = True
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001 - health must report, not raise
            log.exception("Health check database probe failed")
            db_ok = False
        return {
            "status": "ok" if db_ok else "degraded",
            "database": "ok" if db_ok else "unreachable",
            "demo_mode": settings.demo_mode,
            "live_ingestion": settings.enable_live_ingestion,
            "version": app.version,
        }

    app.include_router(api_router)
    return app


app = create_app()
