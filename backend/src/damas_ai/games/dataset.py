"""Training datasets from games (G13, ADR-015).

One record per position before a move: features (strategic profile from the side to move's
view), the game outcome from the side to move's view (1 / 0.5 / 0), and, when the game carries
it, the mover's own engine eval. Leakage control:

- the split is **by game** (a deterministic hash of the game id), never by position;
- a position whose canonical form (colour-twin grouping, ADR-003) appears in ``train`` is
  removed from ``val``/``test``. The removed count is reported.

Every output file is listed in ``manifest.json`` with its SHA-256, so a training run can name
exactly the data it used.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from damas_ai.games.pdn import ReplayedGame
from damas_ai.rules import Color
from damas_ai.rules.notation import format_move, to_fen
from damas_ai.strategy import profile
from damas_ai.tactics import material

FEATURES = ("material", "men", "kings", "tempo", "center", "back_rank", "mobility", "runaways")


@dataclass(frozen=True)
class SourceGame:
    game_id: str
    replay: ReplayedGame
    evals: dict[int, float] | None = None   # ply index -> mover's eval (engine units), optional
    eval_source: str | None = None


def _split(game_id: str, fractions: tuple[float, float, float], seed: int) -> str:
    h = int(hashlib.sha256(f"{seed}:{game_id}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    if h < fractions[0]:
        return "train"
    return "val" if h < fractions[0] + fractions[1] else "test"


def _outcome(result: str, side: Color) -> float | None:
    if result == "1/2-1/2":
        return 0.5
    if result in ("1-0", "0-1"):
        white_won = result == "1-0"
        return 1.0 if (white_won == (side is Color.WHITE)) else 0.0
    return None


def position_record(game: SourceGame, ply: int) -> dict[str, Any] | None:
    rg = game.replay
    state = rg.states[ply]
    pos = state.position
    y = _outcome(rg.pdn.result, pos.side_to_move)
    if y is None:
        return None
    sp = profile(pos)
    sign = 1 if pos.side_to_move is Color.WHITE else -1
    delta = sp.delta()
    feats = {k: sign * delta[k] for k in FEATURES if k != "material"}
    feats["material"] = material(pos, pos.side_to_move) / 100
    rec: dict[str, Any] = {
        "game_id": game.game_id, "ply": ply, "plies": len(rg.moves), "variant": rg.ruleset.variant,
        "ruleset_id": rg.ruleset.id, "fen": to_fen(pos), "dsa": pos.to_dsa(),
        "canonical_dsa": min(pos.to_dsa(), pos.flipped().to_dsa()),
        "side_to_move": pos.side_to_move.value, "outcome": y, "features": feats,
        "played": format_move(pos.geometry, rg.moves[ply]) if ply < len(rg.moves) else None,
    }
    if game.evals is not None and ply in game.evals:
        rec["eval"] = game.evals[ply]
        rec["eval_source"] = game.eval_source
    return rec


def build_dataset(games: Iterable[SourceGame], out_dir: Path, fractions: tuple[float, float, float] = (0.8, 0.1, 0.1),
                  seed: int = 13, skip_plies: int = 0, sources: list[str] | None = None) -> dict[str, Any]:
    by_split: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    games_per_split: Counter[str] = Counter()
    skipped_games = 0
    for game in games:
        if not game.replay.ok or _outcome(game.replay.pdn.result, Color.WHITE) is None:
            skipped_games += 1
            continue
        split = _split(game.game_id, fractions, seed)
        games_per_split[split] += 1
        for ply in range(skip_plies, len(game.replay.moves)):
            rec = position_record(game, ply)
            if rec is not None:
                rec["split"] = split
                by_split[split].append(rec)

    train_keys = {(r["variant"], r["canonical_dsa"]) for r in by_split["train"]}
    leaked: Counter[str] = Counter()
    for split in ("val", "test"):
        kept = []
        for r in by_split[split]:
            if (r["variant"], r["canonical_dsa"]) in train_keys:
                leaked[split] += 1
            else:
                kept.append(r)
        by_split[split] = kept

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for split, rows in by_split.items():
        path = out_dir / f"{split}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        files[path.name] = {"records": len(rows), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {
        "schema_version": 1, "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "label": "outcome = final game result from the side to move's view (1 / 0.5 / 0)",
        "features": list(FEATURES), "feature_view": "side to move (positive = good for the side to move)",
        "split": {"by": "game", "fractions": fractions, "seed": seed},
        "leakage_removed": dict(leaked), "games_per_split": dict(games_per_split),
        "skipped_games": skipped_games, "skip_plies": skip_plies, "sources": sources or [],
        "files": files,
        "outcome_balance": {s: dict(Counter(r["outcome"] for r in rows)) for s, rows in by_split.items()},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
