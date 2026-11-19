from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import Depends, FastAPI, HTTPException, Request
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import ROOT, Settings
from app.database import Base, create_database, get_db
from app.models import DailyUsage, SessionAttempt, SpeakingSession, UsageReservation
from app.schemas import CreateSessionRequest, ReleaseRequest, ReserveRequest, RetryRequest
from app.scoring import count_fillers, validate_scorecard
from app.security import COOKIE_NAME, new_visitor_id, sign_visitor, verify_visitor


logger = logging.getLogger("speakeasy")


def utc_now() -> float:
    return time.time()


def utc_date_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def cleanup_expired(db: Session) -> None:
    now = utc_now()
    expired_reservations = db.scalars(select(UsageReservation).where(UsageReservation.expires_at <= now)).all()
    for reservation in expired_reservations:
        if not reservation.consumed:
            usage_row = db.scalar(select(DailyUsage).where(
                DailyUsage.visitor_id == reservation.visitor_id,
                DailyUsage.date_key == reservation.date_key,
            ))
            if usage_row:
                usage_row.used_count = max(0, usage_row.used_count - 1)
        db.delete(reservation)
    db.execute(delete(SpeakingSession).where(SpeakingSession.expires_at <= now))
    cutoff_date = (datetime.now(timezone.utc).date() - timedelta(days=60)).isoformat()
    db.execute(delete(DailyUsage).where(DailyUsage.date_key < cutoff_date))
    db.commit()


def ensure_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    expected = request.headers.get("host", "")
    parsed = urlparse(origin)
    if not parsed.netloc or parsed.netloc.lower() != expected.lower():
        raise HTTPException(status_code=403, detail="Cross-origin requests are not accepted.")


def attempt_payload(attempt: SessionAttempt) -> dict:
    return {
        "attempt": attempt.attempt_number,
        "transcript": attempt.transcript,
        "scorecard": json.loads(attempt.scorecard_json),
        "inferenceSource": attempt.inference_source,
        "durationSeconds": attempt.duration_seconds,
        "fillerCount": attempt.filler_count,
        "createdAt": int(attempt.created_at * 1000),
        "overallScore": attempt.overall_score,
    }


def serialize_session(session: SpeakingSession) -> dict:
    latest = session.attempts[-1] if session.attempts else None
    return {
        "id": session.session_id,
        "mode": session.mode,
        "goal": session.goal,
        "category": session.category,
        "heat": session.heat,
        "prompt": session.prompt,
        "constraint": session.constraint_phrase,
        "createdAt": int(session.created_at * 1000),
        "expiresAt": int(session.expires_at * 1000),
        "retryUsed": session.retry_used,
        "latest": attempt_payload(latest) if latest else None,
        "attempts": [attempt_payload(item) for item in session.attempts],
    }


def create_app(database_url: str | None = None, settings: Settings | None = None, create_tables: bool = True) -> FastAPI:
    settings = settings or Settings()
    if settings.is_production and (
        settings.app_secret == "local-development-secret-change-before-deploy"
        or len(settings.app_secret) < 32
    ):
        raise RuntimeError("Set APP_SECRET to a random value with at least 32 characters before deploying SpeakEasy.")
    engine, session_factory = create_database(database_url or settings.database_url or None)
    if create_tables:
        Base.metadata.create_all(engine)

    app = FastAPI(
        title="SpeakEasy",
        version="2.0.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.settings = settings
    templates = Jinja2Templates(directory=str(ROOT / "templates"))
    # Vercel serves public/ assets directly through its CDN. Locally, FastAPI serves the same files.
    if not settings.is_production:
        app.mount("/static", StaticFiles(directory=str(ROOT / "public" / "static")), name="static")

    @app.middleware("http")
    async def guest_identity_and_security_headers(request: Request, call_next):
        visitor_id = verify_visitor(request.cookies.get(COOKIE_NAME), settings.app_secret)
        new_cookie = visitor_id is None
        if visitor_id is None:
            visitor_id = new_visitor_id()
        request.state.visitor_id = visitor_id
        response = await call_next(request)
        if new_cookie:
            response.set_cookie(
                COOKIE_NAME,
                sign_visitor(visitor_id, settings.app_secret),
                max_age=60 * 60 * 24 * 30,
                httponly=True,
                secure=settings.is_production,
                samesite="lax",
                path="/",
            )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    def db_dependency(request: Request):
        yield from get_db(request)

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
        }
        return templates.TemplateResponse(request, "index.html", {"config": config})

    @app.get("/health")
    def health():
        return {"status": "ok", "app": "speakeasy", "aiConfigured": settings.firebase_ready}

    @app.get("/api/usage")
    def usage(request: Request, db: Session = Depends(db_dependency)):
        cleanup_expired(db)
        date_key = utc_date_key()
        row = db.scalar(select(DailyUsage).where(
            DailyUsage.visitor_id == request.state.visitor_id,
            DailyUsage.date_key == date_key,
        ))
        return {"used": row.used_count if row else 0, "limit": settings.free_daily_sessions, "date": date_key}

    @app.post("/api/usage/reserve")
    def reserve_usage(body: ReserveRequest, request: Request, db: Session = Depends(db_dependency)):
        ensure_same_origin(request)
        cleanup_expired(db)
        visitor_id = request.state.visitor_id
        existing = db.get(UsageReservation, body.reservation_id)
        if existing:
            if existing.visitor_id != visitor_id:
                raise HTTPException(status_code=409, detail="Reservation identifier is already in use.")
            if existing.expires_at <= utc_now():
                raise HTTPException(status_code=409, detail="This reservation expired. Start a new session.")
            usage_row = db.scalar(select(DailyUsage).where(
                DailyUsage.visitor_id == visitor_id,
                DailyUsage.date_key == existing.date_key,
            ))
            return {"reservationId": existing.reservation_id, "used": usage_row.used_count if usage_row else 0, "limit": settings.free_daily_sessions}

        date_key = utc_date_key()
        usage_row = db.scalar(select(DailyUsage).where(
            DailyUsage.visitor_id == visitor_id,
            DailyUsage.date_key == date_key,
        ))
        if usage_row is None:
            usage_row = DailyUsage(visitor_id=visitor_id, date_key=date_key, used_count=0)
            db.add(usage_row)
            db.flush()
        if usage_row.used_count >= settings.free_daily_sessions:
            raise HTTPException(status_code=429, detail=f"Daily practice limit reached ({settings.free_daily_sessions}). Try again after 00:00 UTC.")
        usage_row.used_count += 1
        reservation = UsageReservation(
            reservation_id=body.reservation_id,
            visitor_id=visitor_id,
            date_key=date_key,
            expires_at=utc_now() + 20 * 60,
            consumed=False,
        )
        db.add(reservation)
        db.commit()
        return {"reservationId": reservation.reservation_id, "used": usage_row.used_count, "limit": settings.free_daily_sessions}

    @app.post("/api/usage/release")
    def release_usage(body: ReleaseRequest, request: Request, db: Session = Depends(db_dependency)):
        ensure_same_origin(request)
        reservation = db.get(UsageReservation, body.reservation_id)
        if not reservation or reservation.visitor_id != request.state.visitor_id:
            return {"ok": True}
        if not reservation.consumed:
            usage_row = db.scalar(select(DailyUsage).where(
                DailyUsage.visitor_id == reservation.visitor_id,
                DailyUsage.date_key == reservation.date_key,
            ))
            if usage_row:
                usage_row.used_count = max(0, usage_row.used_count - 1)
            db.delete(reservation)
            db.commit()
        return {"ok": True}

    @app.post("/api/sessions", status_code=201)
    def create_session(body: CreateSessionRequest, request: Request, db: Session = Depends(db_dependency)):
        ensure_same_origin(request)
        cleanup_expired(db)
        visitor_id = request.state.visitor_id
        existing_session = db.get(SpeakingSession, body.session_id)
        if existing_session:
            if existing_session.visitor_id != visitor_id:
                raise HTTPException(status_code=409, detail="Session identifier already exists.")
            replay_reservation = db.get(UsageReservation, body.reservation_id)
            if replay_reservation:
                if replay_reservation.visitor_id != visitor_id:
                    raise HTTPException(status_code=409, detail="Reservation identifier is already in use.")
                if replay_reservation.consumed and replay_reservation.session_id != body.session_id:
                    raise HTTPException(status_code=409, detail="Reservation was consumed by another session.")
                if not replay_reservation.consumed:
                    usage_row = db.scalar(select(DailyUsage).where(
                        DailyUsage.visitor_id == visitor_id,
                        DailyUsage.date_key == replay_reservation.date_key,
                    ))
                    if usage_row:
                        usage_row.used_count = max(0, usage_row.used_count - 1)
                    db.delete(replay_reservation)
                    db.commit()
            return {"ok": True, "session": serialize_session(existing_session), "idempotent": True}

        reservation = db.get(UsageReservation, body.reservation_id)
        if not reservation or reservation.visitor_id != visitor_id:
            raise HTTPException(status_code=403, detail="A valid session reservation is required.")
        if reservation.expires_at <= utc_now() or reservation.consumed:
            raise HTTPException(status_code=409, detail="The session reservation is expired or already used.")

        try:
            scorecard = validate_scorecard(body.scorecard, body.transcript, body.mode == "hot-take")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        now = utc_now()
        session = SpeakingSession(
            session_id=body.session_id,
            visitor_id=visitor_id,
            mode=body.mode,
            goal=body.goal,
            category=body.category,
            heat=body.heat,
            prompt=body.prompt,
            constraint_phrase=body.constraint_phrase,
            created_at=now,
            expires_at=now + settings.retention_days * 86400,
            retry_used=False,
        )
        attempt = SessionAttempt(
            attempt_number=1,
            transcript=body.transcript,
            scorecard_json=json.dumps(scorecard),
            inference_source=body.inference_source,
            duration_seconds=body.duration_seconds,
            filler_count=sum(count_fillers(body.transcript).values()),
            overall_score=scorecard["overallScore"],
            created_at=now,
        )
        session.attempts.append(attempt)
        reservation.consumed = True
        reservation.session_id = body.session_id
        db.add(session)
        db.commit()
        db.refresh(session)
        return {"ok": True, "session": serialize_session(session), "idempotent": False}

    @app.post("/api/sessions/{session_id}/retry")
    def retry_session(session_id: str, body: RetryRequest, request: Request, db: Session = Depends(db_dependency)):
        ensure_same_origin(request)
        session = db.scalar(select(SpeakingSession).where(
            SpeakingSession.session_id == session_id,
            SpeakingSession.visitor_id == request.state.visitor_id,
        ))
        if not session:
            raise HTTPException(status_code=404, detail="Practice session not found.")
        if session.expires_at <= utc_now():
            raise HTTPException(status_code=410, detail="This session has expired.")
        if session.retry_used:
            raise HTTPException(status_code=409, detail="The free retry has already been used.")
        latest = session.attempts[-1] if session.attempts else None
        if not latest or latest.attempt_number != 1:
            raise HTTPException(status_code=409, detail="The original attempt is missing.")
        try:
            scorecard = validate_scorecard(body.scorecard, body.transcript, session.mode == "hot-take")
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        now = utc_now()
        session.retry_used = True
        session.attempts.append(SessionAttempt(
            attempt_number=2,
            transcript=body.transcript,
            scorecard_json=json.dumps(scorecard),
            inference_source=body.inference_source,
            duration_seconds=body.duration_seconds,
            filler_count=sum(count_fillers(body.transcript).values()),
            overall_score=scorecard["overallScore"],
            created_at=now,
        ))
        db.commit()
        db.refresh(session)
        return {"ok": True, "session": serialize_session(session)}

    @app.get("/api/sessions")
    def list_sessions(request: Request, limit: int = 30, db: Session = Depends(db_dependency)):
        cleanup_expired(db)
        limit = max(1, min(limit, 50))
        items = db.scalars(
            select(SpeakingSession)
            .where(SpeakingSession.visitor_id == request.state.visitor_id, SpeakingSession.expires_at > utc_now())
            .order_by(SpeakingSession.created_at.desc())
            .limit(limit)
        ).all()
        return {"sessions": [serialize_session(item) for item in items]}

    @app.delete("/api/sessions/{session_id}")
    def delete_session(session_id: str, request: Request, db: Session = Depends(db_dependency)):
        ensure_same_origin(request)
        session = db.scalar(select(SpeakingSession).where(
            SpeakingSession.session_id == session_id,
            SpeakingSession.visitor_id == request.state.visitor_id,
        ))
        if session:
            db.delete(session)
            db.commit()
        return {"ok": True}

    @app.post("/api/maintenance/cleanup")
    def scheduled_cleanup(request: Request, db: Session = Depends(db_dependency)):
        secret = os.getenv("CRON_SECRET", "")
        if not secret or request.headers.get("authorization") != f"Bearer {secret}":
            raise HTTPException(status_code=401, detail="Unauthorized.")
        before = db.query(SpeakingSession).count()
        cleanup_expired(db)
        after = db.query(SpeakingSession).count()
        return {"ok": True, "deletedSessions": max(0, before - after)}

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        # API clients receive JSON; browser navigation receives a branded HTML page.
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
        # Never expose exception messages, stack traces, SQL, or configuration to clients.
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
