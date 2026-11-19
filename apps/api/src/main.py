"""Reaboard FastAPI Application Entrypoint.

Configures CORS, security headers, cleanup background tasks,
health probes, rate limiting, and API route registration.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from apps.api.src.api.routes import limiter, router
from apps.api.src.core.config import settings
from apps.api.src.schemas.schemas import ErrorCode, ErrorDetail, ErrorEnvelope
from apps.api.src.services.cleanup_service import CleanupService
from apps.api.src.services.job_service import InvalidStateTransitionError, job_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("reaboard.api")

cleanup_service = CleanupService(job_service=job_service, interval_seconds=300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start cleanup sweeper
    logger.info("Starting Reaboard API service & ephemeral cleanup sweeper...")
    cleanup_service.start()
    yield
    # Shutdown: stop cleanup sweeper
    logger.info("Stopping Reaboard cleanup sweeper...")
    cleanup_service.stop()


app = FastAPI(
    title="Reaboard API",
    version="1.1.0",
    description="Privacy-first, lossless-by-default media metadata inspection and sanitization engine.",
    lifespan=lifespan,
)

# Connect slowapi limiter state
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Handle rate limit breaches with standard error envelope."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=ErrorEnvelope(
            error=ErrorDetail(
                code=ErrorCode.RATE_LIMITED,
                message=f"Rate limit exceeded: {exc.detail}",
                hint="Please wait before uploading additional files.",
            )
        ).model_dump(by_alias=True),
    )


@app.exception_handler(InvalidStateTransitionError)
async def state_transition_handler(request: Request, exc: InvalidStateTransitionError):
    """Handle invalid state transitions with 409 Conflict."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=ErrorEnvelope(
            error=ErrorDetail(
                code=ErrorCode.INVALID_STATE,
                message=str(exc),
            )
        ).model_dump(by_alias=True),
    )


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Ensure consistent error envelope {error: {code, message, hint, requestId}}."""
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}},
    )


# CORS configuration
origins = settings.cors_origins if settings.cors_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Enforce strict security headers across all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
    return response


@app.get("/healthz", tags=["Health"])
async def healthz():
    return {"status": "ok"}


@app.get("/readyz", tags=["Health"])
async def readyz():
    storage_ok = job_service.storage.base_dir.exists()
    return {
        "status": "ready" if storage_ok else "unhealthy",
        "storageWritable": storage_ok,
    }


# Include v1 API routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.src.main:app", host="0.0.0.0", port=8000, reload=True)
