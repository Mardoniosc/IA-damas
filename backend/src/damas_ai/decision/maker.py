"""Decision intelligence (G10, ADR-012): one recommended move, with confidence and reasons.

Pipeline:
1. Proposals: every capable engine proposes a move (G6).
2. Candidates: the proposals, plus the best forcing shot (G9), plus the internal engine's best
   alternatives if requested; capped at ``max_candidates``.
3. Evidence: every engine evaluates every candidate (G7 cross-evaluation, own units).
4. Veto: a candidate some engine judges a *proven loss* is dropped, unless every candidate
   would be dropped.
5. Choice: **minimax normalized regret**. For each engine ``e``,
   ``r_e(m) = (best_e - u_e(m)) / tol_e`` ("how many tolerances worse than e's favourite").
   Pick the candidate minimizing ``max_e w_e·r_e``, then the weighted mean, then the most
   proposers. Weights ``w_e`` default to 1.
6. Confidence:
   - ``high``: ≥ 2 independent engines, every engine accepts the choice (r ≤ 1), no
     contradiction;
   - ``medium``: ≥ 2 engines and a majority accepts it;
   - ``low``: single source, majority rejects, or a contradiction.

No raw score is ever compared across engines.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from damas_ai.analysis import EnginePool, MultiEngineAnalyzer
from damas_ai.analysis.orchestrator import RunMode
from damas_ai.consensus import DEFAULT_TOLERANCE, ConsensusAnalyzer
from damas_ai.consensus.values import MoveValue, OutcomeClass, contradicts
from damas_ai.engines import AnalysisRequest
from damas_ai.rules import Move, legal_moves
from damas_ai.strategy import StrategicProfile, profile
from damas_ai.tactics import Shot, find_shots

Confidence = str  # "high" | "medium" | "low" | "none"


@dataclass(frozen=True)
class CandidateEvidence:
    move: Move
    sources: tuple[str, ...]              # engine ids that proposed it, and/or "tactics"
    values: dict[str, MoveValue]          # engine id -> value (own units)
    normalized_regret: dict[str, float | None]
    vetoed_by: tuple[str, ...]
    max_regret: float | None
    mean_regret: float | None


@dataclass(frozen=True)
class Decision:
    move: Move | None
    confidence: Confidence
    reasons: tuple[str, ...]
    candidates: tuple[CandidateEvidence, ...]
    engines: tuple[str, ...]
    shot: Shot | None
    strategy: StrategicProfile
    notes: tuple[str, ...] = field(default=())


class DecisionMaker:
    def __init__(self, pool: EnginePool) -> None:
        self.pool = pool
        self.multi = MultiEngineAnalyzer(pool)
        self.consensus = ConsensusAnalyzer(pool)

    def decide(
        self,
        request: AnalysisRequest,
        engines: list[str] | None = None,
        mode: RunMode = "sequential",
        tolerance: float | Mapping[str, float] = DEFAULT_TOLERANCE,
        weights: Mapping[str, float] | None = None,
        max_candidates: int = 4,
    ) -> Decision:
        position = request.position
        strat = profile(position)
        moves = legal_moves(position)
        if not moves:
            raise ValueError("terminal position")
        notes: list[str] = []
        if len(moves) == 1:
            return Decision(moves[0], "high", ("only legal move",), (), (), None, strat)

        analysis = self.multi.analyze(request, engines, mode)
        if analysis.note:
            notes.append(analysis.note)
        ok = analysis.engines_ok
        if not ok:
            return Decision(None, "none", ("no engine produced a validated move",), (), (), None,
                            strat, tuple(notes))

        # 2. candidate set
        sources: dict[tuple[int, int, frozenset[int]], tuple[Move, list[str]]] = {}
        for p in analysis.proposals:
            sources[p.move.identity] = (p.move, list(p.engines))
        shots = find_shots(position)
        shot = shots[0] if shots else None
        if shot is not None:
            sources.setdefault(shot.first_move.identity, (shot.first_move, []))[1].append("tactics")
        cands = list(sources.values())[:max_candidates]

        # 3. evidence (every engine x every candidate, own units)
        values = {m.identity: self.consensus.evaluate_move(request, m, ok, notes) for m, _ in cands}
        tol = {e: float(tolerance.get(e, DEFAULT_TOLERANCE)) if isinstance(tolerance, Mapping)
               else float(tolerance) for e in ok}
        w = {e: float((weights or {}).get(e, 1.0)) for e in ok}

        best: dict[str, float | None] = {}
        for e in ok:
            us = [v.utility for m, _ in cands if (v := values[m.identity].get(e)) and v.utility is not None]
            best[e] = max(us) if us else None

        evidence: list[CandidateEvidence] = []
        for m, src in cands:
            vals = values[m.identity]
            norm: dict[str, float | None] = {}
            for e in ok:
                v, b = vals.get(e), best[e]
                norm[e] = None if v is None or v.utility is None or b is None else (b - v.utility) / tol[e]
            vetoed = tuple(e for e, v in vals.items() if v.outcome is OutcomeClass.LOSS
                           and best[e] is not None and best[e] > v.utility)  # type: ignore[operator]
            known = [w[e] * r for e, r in norm.items() if r is not None]
            evidence.append(CandidateEvidence(
                m, tuple(src), dict(vals), norm, vetoed,
                max(known) if known else None, sum(known) / len(known) if known else None))

        pool_ = [c for c in evidence if not c.vetoed_by] or evidence
        if len(pool_) < len(evidence):
            notes.append(f"{len(evidence) - len(pool_)} candidate(s) vetoed as proven losses")
        ranked = sorted(pool_, key=lambda c: (
            c.max_regret if c.max_regret is not None else float("inf"),
            c.mean_regret if c.mean_regret is not None else float("inf"),
            -len([s for s in c.sources if s != "tactics"])))
        choice = ranked[0]

        # 6. confidence and reasons
        accept = [e for e, r in choice.normalized_regret.items() if r is not None and r <= 1.0]
        conflict = any(contradicts(a, b) for c in evidence
                       for i, a in enumerate(c.values.values())
                       for b in list(c.values.values())[i + 1:])
        reasons: list[str] = []
        if choice.sources:
            reasons.append("proposed by " + ", ".join(choice.sources))
        reasons.append(f"accepted (within tolerance) by {len(accept)}/{len(ok)} engine(s): "
                       + (", ".join(accept) if accept else "none"))
        if choice.max_regret is not None:
            reasons.append(f"worst normalized regret {choice.max_regret:.2f} (1.0 = one tolerance)")
        if shot is not None and shot.first_move.identity == choice.move.identity:
            reasons.append(f"tactical shot gaining {shot.gain / 100:.2f} men")
        if len(ok) < 2:
            confidence = "low"
            reasons.append("single evidence source: confidence capped at low")
        elif conflict:
            confidence = "low"
            reasons.append("engines contradict each other on a candidate's outcome")
        elif len(accept) == len(ok):
            confidence = "high"
        elif len(accept) * 2 > len(ok):
            confidence = "medium"
        else:
            confidence = "low"
        return Decision(choice.move, confidence, tuple(reasons), tuple(evidence), ok, shot, strat,
                        tuple(notes))
