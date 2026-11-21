"""Knowledge-base schema (G11, ADR-013). SQLAlchemy 2.0 ORM with portable types (SQLite and
PostgreSQL). Schema changes go through Alembic migrations (backend/alembic).

Design rules:
- ``positions`` are unique per (variant, dsa). ``canonical_dsa`` groups a position with its
  colour-flipped twin (the only board symmetry, ADR-003).
- Zobrist keys (unsigned 64-bit) are stored as signed 64-bit integers (``to_signed64``).
- Every record keeps its provenance: run id, engine name/version, limit, config fingerprint,
  ruleset id, and the producing gate's JSON (``detail``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SCHEMA_VERSION = "0002"


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_signed64(key: int) -> int:
    return key - (1 << 64) if key >= (1 << 63) else key


class Base(DeclarativeBase):
    pass


class PositionRow(Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("variant", "dsa", name="uq_positions_variant_dsa"),
                      Index("ix_positions_canonical", "variant", "canonical_dsa"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variant: Mapped[str] = mapped_column(String(40))
    ruleset_id: Mapped[str] = mapped_column(String(60))
    dsa: Mapped[str] = mapped_column(String(64))
    canonical_dsa: Mapped[str] = mapped_column(String(64))
    fen: Mapped[str] = mapped_column(String(400))
    zobrist: Mapped[int] = mapped_column(BigInteger, index=True)
    side_to_move: Mapped[str] = mapped_column(String(1))
    white_men: Mapped[int] = mapped_column(Integer)
    white_kings: Mapped[int] = mapped_column(Integer)
    black_men: Mapped[int] = mapped_column(Integer)
    black_kings: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analyses: Mapped[list[EngineAnalysisRow]] = relationship(back_populates="position")
    tags: Mapped[list[TagRow]] = relationship(back_populates="position")


class EngineAnalysisRow(Base):
    __tablename__ = "engine_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    engine_id: Mapped[str] = mapped_column(String(60), index=True)
    engine_name: Mapped[str | None] = mapped_column(String(60))
    engine_version: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    best_move: Mapped[str | None] = mapped_column(String(80))
    score_text: Mapped[str | None] = mapped_column(String(20))
    score_value: Mapped[float | None] = mapped_column(Float)
    score_unit: Mapped[str | None] = mapped_column(String(40))
    score_kind: Mapped[str | None] = mapped_column(String(20))
    depth: Mapped[int | None] = mapped_column(Integer)
    nodes: Mapped[int | None] = mapped_column(BigInteger)
    elapsed_s: Mapped[float | None] = mapped_column(Float)
    limit: Mapped[dict[str, Any]] = mapped_column(JSON)
    config_fingerprint: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    position: Mapped[PositionRow] = relationship(back_populates="analyses")


class ConsensusRow(Base):
    __tablename__ = "consensus_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(40), index=True)
    source: Mapped[str] = mapped_column(String(20))  # "consensus" | "adaptive"
    classification: Mapped[str] = mapped_column(String(30), index=True)
    proof_gap: Mapped[bool] = mapped_column(Boolean)
    unanimous: Mapped[bool] = mapped_column(Boolean)
    agreement_ratio: Mapped[float | None] = mapped_column(Float)
    engines: Mapped[list[str]] = mapped_column(JSON)
    limit: Mapped[dict[str, Any]] = mapped_column(JSON)
    trajectory: Mapped[list[str] | None] = mapped_column(JSON)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TacticalRow(Base):
    __tablename__ = "tactical_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), index=True)
    critical: Mapped[bool] = mapped_column(Boolean, index=True)
    reasons: Mapped[list[str]] = mapped_column(JSON)
    shot_move: Mapped[str | None] = mapped_column(String(80))
    shot_gain_men: Mapped[float | None] = mapped_column(Float)
    shot_sacrifice: Mapped[bool | None] = mapped_column(Boolean)
    thresholds: Mapped[dict[str, Any]] = mapped_column(JSON)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DecisionRow(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), index=True)
    move: Mapped[str | None] = mapped_column(String(80))
    confidence: Mapped[str] = mapped_column(String(10), index=True)
    reasons: Mapped[list[str]] = mapped_column(JSON)
    engines: Mapped[list[str]] = mapped_column(JSON)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TagRow(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("position_id", "tag", "source", name="uq_tags_position_tag_source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), index=True)
    tag: Mapped[str] = mapped_column(String(60), index=True)
    source: Mapped[str] = mapped_column(String(60))
    note: Mapped[str | None] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    position: Mapped[PositionRow] = relationship(back_populates="tags")


class GameRow(Base):
    """A game (G13): PDN text plus metadata; positions linked through ``game_positions``."""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(200))
    event: Mapped[str | None] = mapped_column(String(200))
    white: Mapped[str] = mapped_column(String(100), index=True)
    black: Mapped[str] = mapped_column(String(100), index=True)
    result: Mapped[str] = mapped_column(String(10))
    variant: Mapped[str] = mapped_column(String(40))
    start_fen: Mapped[str] = mapped_column(String(400))
    plies: Mapped[int] = mapped_column(Integer)
    termination: Mapped[str | None] = mapped_column(String(200))
    pdn: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GamePositionRow(Base):
    __tablename__ = "game_positions"
    __table_args__ = (UniqueConstraint("game_id", "ply", name="uq_game_positions_game_ply"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    ply: Mapped[int] = mapped_column(Integer)
    position_id: Mapped[int] = mapped_column(ForeignKey("positions.id"), index=True)
    move: Mapped[str | None] = mapped_column(String(80))
    label: Mapped[str | None] = mapped_column(String(20))      # G13 analysis label, if analysed
    regret: Mapped[float | None] = mapped_column(Float)
