"""Learning system CLI (G14, ADR-016).

    python -m damas_ai.learning compare --dataset ../reports/bench/g13-dataset-br --out compare.json
    python -m damas_ai.learning train   --dataset ../reports/bench/g13-dataset-br --out model.json
    python -m damas_ai.learning match   --model model.json --depth 4 --openings 16 --out match/
    python -m damas_ai.learning match   --model model.json --move-time 0.05 --openings 16 --out match/

``compare`` fits on train, selects regularization on val, reports test metrics for: constant,
material only, the baseline hand eval, the CHEAP and FULL linear models, and an MLP (PyTorch, if
installed). ``match`` plays learned-eval search vs baseline-eval search (G12 machinery).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from damas_ai.learning.linear import CHEAP, FULL, LinearModel, constant_baseline, fit, load_split, metrics


def _manifest(ds: Path) -> dict:  # type: ignore[type-arg]
    m = json.loads((ds / "manifest.json").read_text(encoding="utf-8"))
    return {"dataset": str(ds), "files": m["files"],
            "manifest_sha256": hashlib.sha256((ds / "manifest.json").read_bytes()).hexdigest()}


def _select_l2(ds: Path, features: tuple[str, ...]) -> tuple[LinearModel, dict]:  # type: ignore[type-arg]
    xt, yt, _ = load_split(ds / "train.jsonl", features)
    xv, yv, _ = load_split(ds / "val.jsonl", features)
    best = None
    for l2 in (0.01, 0.1, 1.0, 10.0, 100.0):
        m = fit(xt, yt, features, l2)
        loss = metrics(m.predict(xv), yv)["logloss"]
        if best is None or loss < best[0]:
            best = (loss, m)
    assert best is not None
    return best[1], {"val_logloss": best[0], "l2": best[1].l2}


def _baseline_eval_feature(rows: list[dict]) -> np.ndarray:  # type: ignore[type-arg]
    from damas_ai.rules import BOARD_8X8, BOARD_10X10
    from damas_ai.rules.notation import from_fen
    from damas_ai.search.evaluation import evaluate

    geo = {"brazilian-8x8": BOARD_8X8, "international-10x10": BOARD_10X10}
    return np.array([[evaluate(from_fen(geo[r["variant"]], r["fen"])) / 100.0] for r in rows])


def _mlp(ds: Path) -> dict | None:  # type: ignore[type-arg]
    try:
        import torch
        from torch import nn
    except ImportError:
        return None
    from damas_ai.rules import BOARD_8X8, Color
    from damas_ai.rules.notation import from_fen
    from damas_ai.rules.position import Piece

    def planes(rows: list[dict]) -> np.ndarray:  # type: ignore[type-arg]
        out = np.zeros((len(rows), 4 * 32), dtype=np.float32)
        for i, r in enumerate(rows):
            p = from_fen(BOARD_8X8, r["fen"])
            if p.side_to_move is Color.BLACK:
                p = p.flipped()  # always "the side to move is White"
            for sq, pc in enumerate(p.squares):
                k = {Piece.WHITE_MAN: 0, Piece.WHITE_KING: 1, Piece.BLACK_MAN: 2, Piece.BLACK_KING: 3}.get(pc)
                if k is not None:
                    out[i, k * 32 + sq] = 1.0
        return out

    split = {}
    for name in ("train", "val", "test"):
        _, y, rows = load_split(ds / f"{name}.jsonl", CHEAP)
        split[name] = (torch.tensor(planes(rows)), torch.tensor(y, dtype=torch.float32))
    torch.manual_seed(14)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = nn.Sequential(nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1)).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    lossf = nn.BCEWithLogitsLoss()
    xt, yt = (t.to(device) for t in split["train"])
    xv, yv = (t.to(device) for t in split["val"])
    best, best_state, patience = float("inf"), None, 0
    for _epoch in range(200):
        model.train()
        perm = torch.randperm(len(xt), device=device)
        for i in range(0, len(xt), 256):
            idx = perm[i:i + 256]
            opt.zero_grad()
            loss = lossf(model(xt[idx]).squeeze(1), yt[idx])
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            v = lossf(model(xv).squeeze(1), yv).item()
        if v < best - 1e-4:
            best, best_state, patience = v, {k: t.clone() for k, t in model.state_dict().items()}, 0
        else:
            patience += 1
            if patience >= 10:
                break
    model.load_state_dict(best_state)  # type: ignore[arg-type]
    with torch.no_grad():
        p = torch.sigmoid(model(split["test"][0].to(device)).squeeze(1)).cpu().numpy()
    return {**metrics(p, split["test"][1].numpy()), "params": sum(t.numel() for t in model.parameters()),
            "val_logloss": round(best, 5), "device": device}


def cmd_compare(ns: argparse.Namespace) -> int:
    ds = ns.dataset
    _, yt, rows_t = load_split(ds / "train.jsonl", CHEAP)
    _, ytest, rows_test = load_split(ds / "test.jsonl", CHEAP)
    report: dict[str, object] = {"provenance": _manifest(ds)}
    report["constant"] = constant_baseline(yt, ytest)
    for name, feats in (("material_only", ("material",)), ("linear_cheap", CHEAP), ("linear_full", FULL)):
        m, sel = _select_l2(ds, feats)
        x, y, _ = load_split(ds / "test.jsonl", feats)
        report[name] = {**metrics(m.predict(x), y), **sel, "weights": dict(zip(feats, m.weights)), "bias": m.bias}
    bt = fit(_baseline_eval_feature(rows_t), yt, ("baseline_eval",), 0.0)
    report["baseline_eval"] = {**metrics(bt.predict(_baseline_eval_feature(rows_test)), ytest),
                               "note": "hand eval (G8) mapped to probability by a 1-feature logistic fit on train"}
    report["mlp_planes"] = _mlp(ds)
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: (v if k == "provenance" else {kk: vv for kk, vv in v.items() if kk in ("logloss", "brier", "decisive_accuracy", "n")} if isinstance(v, dict) else v)
                      for k, v in report.items() if k != "provenance"}, indent=1))
    return 0


def cmd_train(ns: argparse.Namespace) -> int:
    model, sel = _select_l2(ns.dataset, CHEAP)
    x, y, _ = load_split(ns.dataset / "test.jsonl", CHEAP)
    model.train = {**_manifest(ns.dataset), **sel, "test": metrics(model.predict(x), y)}
    ns.out.parent.mkdir(parents=True, exist_ok=True)
    ns.out.write_text(model.to_json(), encoding="utf-8")
    print(json.dumps({"fingerprint": model.fingerprint(), "weights": dict(zip(model.features, model.weights)),
                      "bias": model.bias, **model.train["test"]}, indent=1))
    return 0


def cmd_match(ns: argparse.Namespace) -> int:
    from damas_ai.bench import SearchPlayer, generate_openings, run_match, write_outputs
    from damas_ai.learning.evaluator import load_evaluator
    from damas_ai.rules import BRAZILIAN_PROVISIONAL

    rs = BRAZILIAN_PROVISIONAL
    ev = load_evaluator(ns.model)
    tag = f"depth={ns.depth}" if ns.depth else f"{ns.move_time}s"
    learned = SearchPlayer(ns.depth, f"learned@{tag}", ev, None if ns.depth else ns.move_time)
    baseline = SearchPlayer(ns.depth, f"baseline@{tag}", None, None if ns.depth else ns.move_time)
    openings = generate_openings(rs, ns.openings, 6, ns.seed)
    m = run_match(learned, baseline, rs, openings, ns.max_plies)
    write_outputs(ns.out, f"G14 learned vs baseline ({tag})", [m],
                  {"model": str(ns.model), "model_fingerprint": ev.model.fingerprint(), "seed": ns.seed})
    s = m.stats
    print(json.dumps({"games": s.games, "W": s.wins, "D": s.draws, "L": s.losses, "score": s.score,
                      "elo": s.elo, "elo_ci": [s.elo_low, s.elo_high], "los": s.los}, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m damas_ai.learning", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare")
    c.add_argument("--dataset", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    t = sub.add_parser("train")
    t.add_argument("--dataset", type=Path, required=True)
    t.add_argument("--out", type=Path, required=True)
    m = sub.add_parser("match")
    m.add_argument("--model", type=Path, required=True)
    g = m.add_mutually_exclusive_group(required=True)
    g.add_argument("--depth", type=int)
    g.add_argument("--move-time", type=float)
    m.add_argument("--openings", type=int, default=16)
    m.add_argument("--seed", type=int, default=1414)
    m.add_argument("--max-plies", type=int, default=300)
    m.add_argument("--out", type=Path, required=True)
    ns = ap.parse_args(argv)
    return {"compare": cmd_compare, "train": cmd_train, "match": cmd_match}[ns.cmd](ns)


if __name__ == "__main__":
    raise SystemExit(main())
