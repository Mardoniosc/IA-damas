"""KnowledgeBase repository (G11, ADR-013).

Records are written from the JSON views the earlier gates already produce (G6 analysis,
G7 consensus, G8 adaptive, G9 tactics, G10 decision). The same JSON lines can therefore be
ingested from files or recorded live, and the stored ``detail`` keeps the full provenance.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from damas_ai.kb.models import (
    Base,
    ConsensusRow,
    DecisionRow,
    EngineAnalysisRow,
    GamePositionRow,
    GameRow,
    PositionRow,
    TacticalRow,
    TagRow,
    to_signed64,
)
from damas_ai.rules import RULESETS, Position, Ruleset
from damas_ai.rules.notation import from_fen, to_fen
from damas_ai.rules.zobrist import zobrist_key


def _ruleset(variant: str) -> Ruleset:
    for r in RULESETS.values():
        if r.variant == variant:
            return r
    raise ValueError(f"unknown variant {variant!r}")


@dataclass(frozen=True)
class PositionSummary:
    id: int
    variant: str
    fen: str
    tags: tuple[str, ...]
    critical: bool | None
    classifications: tuple[str, ...]


class KnowledgeBase:
    def __init__(self, url: str = "sqlite:///:memory:", create: bool = False, echo: bool = False) -> None:
        if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        if url in ("sqlite://", "sqlite:///:memory:"):
            # One shared connection, or every thread (e.g. FastAPI workers) sees its own empty DB.
            self.engine: Engine = create_engine(url, echo=echo, poolclass=StaticPool,
                                                connect_args={"check_same_thread": False})
        else:
            self.engine = create_engine(url, echo=echo)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        if create:
            Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self._sessions()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # ---------------------------------------------------------------- positions

    def upsert_position(self, s: Session, position: Position, ruleset: Ruleset) -> PositionRow:
        dsa = position.to_dsa()
        row = s.scalar(select(PositionRow).where(PositionRow.variant == ruleset.variant,
                                                 PositionRow.dsa == dsa))
        if row is not None:
            return row
        flipped = position.flipped().to_dsa()
        wm, wk, bm, bk = position.material()
        row = PositionRow(variant=ruleset.variant, ruleset_id=ruleset.id, dsa=dsa,
                          canonical_dsa=min(dsa, flipped), fen=to_fen(position),
                          zobrist=to_signed64(zobrist_key(position)),
                          side_to_move=position.side_to_move.value, white_men=wm, white_kings=wk,
                          black_men=bm, black_kings=bk)
        s.add(row)
        s.flush()
        return row

    def _position_from_view(self, s: Session, fen: str, variant: str) -> PositionRow:
        rs = _ruleset(variant)
        return self.upsert_position(s, from_fen(rs.geometry, fen), rs)

    def tag(self, s: Session, position: PositionRow, tag: str, source: str, note: str | None = None) -> None:
        exists = s.scalar(select(TagRow).where(TagRow.position_id == position.id, TagRow.tag == tag,
                                               TagRow.source == source))
        if exists is None:
            s.add(TagRow(position_id=position.id, tag=tag, source=source, note=note))

    # ---------------------------------------------------------------- record gate outputs

    def record_analysis(self, s: Session, view: dict[str, Any]) -> PositionRow:
        """G6 ``multi_view``."""
        pos = self._position_from_view(s, view["position"]["fen"], view["variant"])
        for r in view["results"]:
            fi = r.get("final_info") or {}
            score = fi.get("score") or {}
            s.add(EngineAnalysisRow(
                position_id=pos.id, run_id=view["run_id"], engine_id=r["engine"]["id"],
                engine_name=r["engine"].get("name"), engine_version=r["engine"].get("version"),
                status=r["status"], best_move=(r.get("best_move") or {}).get("numeric"),
                score_text=score.get("text"), score_value=score.get("value"), score_unit=score.get("unit"),
                score_kind=score.get("kind"), depth=fi.get("depth"), nodes=fi.get("nodes"),
                elapsed_s=r.get("elapsed_s"), limit=view["limit"],
                config_fingerprint=view.get("config_fingerprint")))
        return pos

    def record_consensus(self, s: Session, view: dict[str, Any], source: str = "consensus",
                         trajectory: list[str] | None = None) -> PositionRow:
        """G7 ``consensus_view`` (also used for the final step of G8 adaptive records)."""
        analysis = view["analysis"]
        pos = self.record_analysis(s, analysis)
        s.add(ConsensusRow(
            position_id=pos.id, run_id=analysis["run_id"], source=source,
            classification=view["classification"], proof_gap=view["proof_gap"],
            unanimous=view["unanimous"], agreement_ratio=view["agreement_ratio"],
            engines=analysis["requested_engines"], limit=analysis["limit"], trajectory=trajectory,
            detail={k: v for k, v in view.items() if k != "analysis"}))
        if view["classification"] in ("preference", "outcome_conflict"):
            self.tag(s, pos, f"divergence:{view['classification']}", source)
        if view["proof_gap"]:
            self.tag(s, pos, "proof_gap", source)
        return pos

    def record_adaptive(self, s: Session, view: dict[str, Any]) -> PositionRow:
        """G8 ``adaptive_view``: stored as its final consensus plus the trajectory."""
        pos = self.record_consensus(s, view["final"], "adaptive", view["trajectory"])
        traj = view["trajectory"]
        if len(traj) > 1 and all(c in ("preference", "outcome_conflict") for c in traj):
            self.tag(s, pos, "stable_divergence", "adaptive",
                     f"diverged at every level: {' > '.join(traj)}")
        return pos

    def record_tactics(self, s: Session, view: dict[str, Any], variant: str) -> PositionRow:
        """G9 ``criticality_view``."""
        pos = self._position_from_view(s, view["position"]["fen"], variant)
        shot = view["shots"][0] if view["shots"] else None
        s.add(TacticalRow(
            position_id=pos.id, critical=view["critical"], reasons=view["reasons"],
            shot_move=shot["line"][0] if shot else None, shot_gain_men=shot["gain_men"] if shot else None,
            shot_sacrifice=shot["sacrifice"] if shot else None, thresholds=view["thresholds"],
            detail={k: v for k, v in view.items() if k not in ("position",)}))
        if view["critical"]:
            self.tag(s, pos, "critical", "tactics")
        for reason in view["reasons"]:
            self.tag(s, pos, "tactics:" + reason.split(":")[0].replace(" ", "_"), "tactics")
        return pos

    def record_decision(self, s: Session, view: dict[str, Any], variant: str) -> PositionRow:
        """G10 ``decision_view``."""
        pos = self._position_from_view(s, view["position"]["fen"], variant)
        s.add(DecisionRow(position_id=pos.id, move=(view.get("move") or {}).get("numeric"),
                          confidence=view["confidence"], reasons=view["reasons"],
                          engines=view["engines"], detail=view))
        return pos

    def record_game(self, s: Session, game: Any, source: str, pdn_text: str,
                    analysis: Any | None = None) -> GameRow:
        """G13: a replayed game (``games.pdn.ReplayedGame``), optionally with its ``GameAnalysis``.
        Every position before a move is upserted and linked by ply."""
        if not game.ok:
            raise ValueError(f"game did not replay: {game.error}")
        tags = game.pdn.tags
        row = GameRow(source=source, event=tags.get("Event"), white=tags.get("White", "?"),
                      black=tags.get("Black", "?"), result=game.pdn.result, variant=game.ruleset.variant,
                      start_fen=to_fen(game.start), plies=len(game.moves),
                      termination=tags.get("Termination"), pdn=pdn_text)
        s.add(row)
        s.flush()
        labels = {p.ply - 1: p for p in analysis.plies} if analysis is not None else {}
        from damas_ai.rules.notation import format_move

        for ply, move in enumerate(game.moves):
            pos = self.upsert_position(s, game.states[ply].position, game.ruleset)
            pa = labels.get(ply)
            s.add(GamePositionRow(game_id=row.id, ply=ply, position_id=pos.id,
                                  move=format_move(game.start.geometry, move),
                                  label=pa.label if pa else None, regret=pa.regret if pa else None))
        return row

    # ---------------------------------------------------------------- queries

    def stats(self) -> dict[str, Any]:
        with self.session() as s:
            def count(model: type[Base]) -> int:
                return s.scalar(select(func.count()).select_from(model)) or 0

            by_variant = dict(s.execute(select(PositionRow.variant, func.count()).group_by(PositionRow.variant)).all())
            tags = dict(s.execute(select(TagRow.tag, func.count()).group_by(TagRow.tag)).all())
            classes = dict(s.execute(select(ConsensusRow.classification, func.count())
                                     .group_by(ConsensusRow.classification)).all())
            return {"positions": count(PositionRow), "positions_by_variant": by_variant,
                    "engine_analyses": count(EngineAnalysisRow), "consensus_records": count(ConsensusRow),
                    "tactical_records": count(TacticalRow), "decisions": count(DecisionRow),
                    "games": count(GameRow), "game_positions": count(GamePositionRow),
                    "tags": tags, "consensus_classes": classes}

    def find(self, variant: str | None = None, tag: str | None = None, classification: str | None = None,
             critical: bool | None = None, limit: int = 50, offset: int = 0) -> list[PositionSummary]:
        with self.session() as s:
            q = select(PositionRow).order_by(PositionRow.id)
            if variant:
                q = q.where(PositionRow.variant == variant)
            if tag:
                q = q.where(PositionRow.id.in_(select(TagRow.position_id).where(TagRow.tag == tag)))
            if classification:
                q = q.where(PositionRow.id.in_(select(ConsensusRow.position_id)
                                               .where(ConsensusRow.classification == classification)))
            if critical is not None:
                q = q.where(PositionRow.id.in_(select(TacticalRow.position_id)
                                               .where(TacticalRow.critical == critical)))
            rows = s.scalars(q.limit(limit).offset(offset)).all()
            return [self._summary(s, r) for r in rows]

    def get(self, position_id: int) -> dict[str, Any] | None:
        with self.session() as s:
            row = s.get(PositionRow, position_id)
            if row is None:
                return None
            def dump(model: type[Base], cols: Iterable[str]) -> list[dict[str, Any]]:
                items = s.scalars(select(model).where(model.position_id == row.id)).all()  # type: ignore[attr-defined]
                return [{c: getattr(i, c) for c in cols} for i in items]

            return {
                "id": row.id, "variant": row.variant, "ruleset_id": row.ruleset_id, "fen": row.fen,
                "dsa": row.dsa, "canonical_dsa": row.canonical_dsa, "side_to_move": row.side_to_move,
                "material": [row.white_men, row.white_kings, row.black_men, row.black_kings],
                "tags": [t.tag for t in row.tags],
                "analyses": dump(EngineAnalysisRow, ("run_id", "engine_id", "engine_name", "engine_version",
                                                     "status", "best_move", "score_text", "score_unit",
                                                     "score_kind", "depth", "limit")),
                "consensus": dump(ConsensusRow, ("run_id", "source", "classification", "proof_gap",
                                                 "unanimous", "trajectory", "engines")),
                "tactics": dump(TacticalRow, ("critical", "reasons", "shot_move", "shot_gain_men",
                                              "shot_sacrifice")),
                "decisions": dump(DecisionRow, ("move", "confidence", "reasons", "engines")),
            }

    def _summary(self, s: Session, row: PositionRow) -> PositionSummary:
        crit = s.scalars(select(TacticalRow.critical).where(TacticalRow.position_id == row.id)).all()
        classes = s.scalars(select(ConsensusRow.classification).where(ConsensusRow.position_id == row.id)).all()
        return PositionSummary(row.id, row.variant, row.fen, tuple(sorted({t.tag for t in row.tags})),
                               any(crit) if crit else None, tuple(classes))
