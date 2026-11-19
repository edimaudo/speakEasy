from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parent

# .env is a local-development convenience. Vercel supplies environment
# variables directly, so python-dotenv is optional at runtime.
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - deployment fallback
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, HTTPException, Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import ROOT, Settings
from app.schemas import ScorecardValidationRequest
from app.scoring import validate_scorecard

logger = logging.getLogger("speakeasy")


def ensure_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    expected = request.headers.get("host", "")
    parsed = urlparse(origin)
    if not parsed.netloc or parsed.netloc.lower() != expected.lower():
        raise HTTPException(status_code=403, detail="Cross-origin requests are not accepted.")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="SpeakEasy",
        version="3.0.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    templates = Jinja2Templates(directory=str(ROOT / "templates"))

    # Vercel serves /static/* from public/static through its CDN. Mount the
    # same directory only for local FastAPI development.
    if not settings.is_production:
        app.mount("/static", StaticFiles(directory=str(ROOT / "public" / "static")), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        config = {
            "firebase": settings.firebase_config,
            "firebaseReady": settings.firebase_ready,
            "recaptchaSiteKey": settings.recaptcha_site_key,
            "appCheckDebug": settings.app_check_debug and not settings.is_production,
            "aiLocation": settings.firebase_ai_location,
            "modelName": settings.firebase_ai_model,
            "dailyLimit": settings.free_daily_sessions,
            "retentionDays": settings.retention_days,
        }
        return templates.TemplateResponse(request, "index.html", {"config": config})

    @app.get("/health")
    def health():
        return {"status": "ok", "app": "speakeasy", "aiConfigured": settings.firebase_ready}

    @app.post("/api/scorecard/validate")
    def validate_session_scorecard(body: ScorecardValidationRequest, request: Request):
        """Stateless validation only; no session or transcript is persisted server-side."""
        ensure_same_origin(request)
        try:
            scorecard = validate_scorecard(
                body.scorecard,
                body.transcript,
                body.mode == "hot-take",
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"scorecard": scorecard, "overallScore": scorecard["overallScore"]}

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith("/api/") or "application/json" in request.headers.get("accept", ""):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        if exc.status_code == 404:
            return templates.TemplateResponse(
                request,
                "404.html",
                {"status_code": 404},
                status_code=404,
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception):
        logger.exception("Unhandled application error for %s %s", request.method, request.url.path)
        if request.url.path.startswith("/api/") or "application/json" in request.headers.get("accept", ""):
            return JSONResponse(
                status_code=500,
                content={"detail": "An unexpected error occurred. Please try again."},
            )
        return templates.TemplateResponse(
            request,
            "500.html",
            {"status_code": 500},
            status_code=500,
        )

    return app


app = create_app()
