from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (UniqueConstraint("visitor_id", "date_key", name="uq_usage_visitor_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visitor_id: Mapped[str] = mapped_column(String(36), index=True)
    date_key: Mapped[str] = mapped_column(String(10), index=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)


class UsageReservation(Base):
    __tablename__ = "usage_reservations"

    reservation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    visitor_id: Mapped[str] = mapped_column(String(36), index=True)
    date_key: Mapped[str] = mapped_column(String(10))
    expires_at: Mapped[float] = mapped_column(Float)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class SpeakingSession(Base):
    __tablename__ = "speaking_sessions"
    __table_args__ = (Index("ix_session_owner_created", "visitor_id", "created_at"),)

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    visitor_id: Mapped[str] = mapped_column(String(36), index=True)
    mode: Mapped[str] = mapped_column(String(20))
    goal: Mapped[str] = mapped_column(String(80), default="")
    category: Mapped[str] = mapped_column(String(80), default="")
    heat: Mapped[str] = mapped_column(String(20), default="")
    prompt: Mapped[str] = mapped_column(String(700))
    constraint_phrase: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[float] = mapped_column(Float, index=True)
    expires_at: Mapped[float] = mapped_column(Float, index=True)
    retry_used: Mapped[bool] = mapped_column(Boolean, default=False)

    attempts: Mapped[list["SessionAttempt"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="SessionAttempt.attempt_number"
    )


class SessionAttempt(Base):
    __tablename__ = "session_attempts"
    __table_args__ = (UniqueConstraint("session_id", "attempt_number", name="uq_session_attempt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("speaking_sessions.session_id", ondelete="CASCADE"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer)
    transcript: Mapped[str] = mapped_column(Text)
    scorecard_json: Mapped[str] = mapped_column(Text)
    inference_source: Mapped[str] = mapped_column(String(20), default="UNKNOWN")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    filler_count: Mapped[int] = mapped_column(Integer, default=0)
    overall_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[float] = mapped_column(Float)

    session: Mapped[SpeakingSession] = relationship(back_populates="attempts")
