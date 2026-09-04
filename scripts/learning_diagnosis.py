"""Four hypotheses for why the learning curve falls after 3,000 games.

The curve rises to 3,000 self-play games and drops after (+10 Elo at 3,000,
−63 at 10,000, −193 at 30,000). Before that is published, three things have to
be separated, and two of them need no games at all:

* **overfitting** — the learner fits its own self-play and generalises worse.
  Measured as the same TD loss the training uses, on human games from the
  Lichess January 2013 dump, which predates this project by a decade and has
  no path into training (`scripts/validation_set.py`).
* **divergence** — TD with function approximation and off-policy exploration
  can diverge (Sutton & Barto's deadly triad). Measured as the weight norm and
  the value scale over training.
* **a training-pipeline fault** — measured by rerunning at a lower learning
  rate and at a different seed.

This script computes the first two for a set of weights.

    python -m scripts.learning_diagnosis --checkpoints 1000 3000 10000 30000
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import chess
import numpy as np

from engine.search.alphabeta import search_alphabeta
from engine.search.context import SearchStats
from research.self_play.value_learner import PieceSquareEvaluator

HELDOUT = Path("data/validation/heldout.json")
PIECES = ("pawn", "knight", "bishop", "rook", "queen", "king")


def validation_loss(
    evaluator: PieceSquareEvaluator, games: list[dict], depth: int = 2, time_limit: float = 0.05
) -> dict[str, float]:
    """Mean |TD error| on games the learner never played.

    Deliberately the same quantity ``ValueLearner.update`` returns: values are
    taken at the leaf of the same shallow search, the last one is anchored to
    what actually happened, and the loss is the mean absolute temporal
    difference. What differs is only where the positions came from.
    """
    totals, counts = 0.0, 0
    scale_sum, scale_n = 0.0, 0
    # A shrinking value function makes every temporal difference smaller for
    # free, so |TD| alone cannot tell "predicts better" from "predicts less".
    # These three are scale-free or move the other way under shrinkage.
    terminal, terminal_n = 0.0, 0
    agree, decided = 0, 0
    vs: list[float] = []
    outcomes: list[float] = []
    for game in games:
        board = chess.Board()
        values: list[float] = []
        for uci in game["moves"]:
            stats = SearchStats(time_limit=time_limit)
            result = search_alphabeta(board, depth, evaluator.static_eval, stats=stats)
            leaf = board.copy(stack=False)
            for move in result.pv:
                if move in leaf.legal_moves:
                    leaf.push(move)
            values.append(evaluator.value(leaf))
            board.push(chess.Move.from_uci(uci))
        if len(values) < 2:
            continue
        deltas = [values[i + 1] - values[i] for i in range(len(values) - 1)]
        deltas.append(game["outcome"] - values[-1])
        totals += float(np.sum(np.abs(deltas)))
        counts += len(deltas)
        scale_sum += float(np.sum(np.abs(values)))
        scale_n += len(values)
        terminal += abs(game["outcome"] - values[-1])
        terminal_n += 1
        if game["outcome"] != 0.0:
            # Second half only: the first moves of a game carry little signal
            # about who wins, and counting them dilutes the measurement.
            for v in values[len(values) // 2 :]:
                decided += 1
                agree += int(np.sign(v) == np.sign(game["outcome"]))
        vs.extend(values)
        outcomes.extend([game["outcome"]] * len(values))
    return {
        "validation_td_error": totals / counts,
        "mean_abs_value": scale_sum / scale_n,
        "terminal_error": terminal / terminal_n,
        "sign_agreement": agree / decided,
        "correlation": float(np.corrcoef(vs, outcomes)[0, 1]),
        "positions": counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoints", type=int, nargs="+", default=[1000, 3000, 10000, 30000])
    parser.add_argument("--dir", default="data/learning_curve")
    parser.add_argument("--games", type=int, default=60, help="held-out games to score")
    parser.add_argument("--out", default="data/learning_diagnosis.json")
    args = parser.parse_args()

    heldout = json.loads(HELDOUT.read_text())["games"][: args.games]
    print(f"{len(heldout)} held-out human games from {HELDOUT}\n")

    print(
        f"{'train games':>12} {'weight L2':>10} {'value scale':>12} "
        f"{'train |TD|':>11} {'valid |TD|':>11} {'terminal':>9} {'sign %':>7} "
        f"{'corr':>6} {'pawn':>7}"
    )
    rows = []
    for games in args.checkpoints:
        record = json.loads((Path(args.dir) / f"weights_{games}.json").read_text())
        weights = np.array(record["weights"], dtype=float)
        evaluator = PieceSquareEvaluator()
        evaluator.set_weights(weights)
        # The training loss the run itself reported, averaged over its last
        # five snapshots so one noisy game does not stand for the run.
        trace = record["trace"]
        train_td = float(np.mean([t["td_error"] for t in trace[-5:]]))
        result = validation_loss(evaluator, heldout)
        means = evaluator.piece_means()
        rows.append(
            {
                "training_games": games,
                "weight_l2": float(np.linalg.norm(weights)),
                "weight_linf": float(np.abs(weights).max()),
                "train_td_error": train_td,
                **result,
                "piece_means": means,
            }
        )
        print(
            f"{games:>12,} {np.linalg.norm(weights):>10.0f} {result['mean_abs_value']:>12.4f} "
            f"{train_td:>11.4f} {result['validation_td_error']:>11.4f} "
            f"{result['terminal_error']:>9.4f} {result['sign_agreement']:>7.1%} "
            f"{result['correlation']:>6.3f} {means['pawn']:>7.1f}"
        )

    Path(args.out).write_text(json.dumps({"rows": rows}, indent=1))
    print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
