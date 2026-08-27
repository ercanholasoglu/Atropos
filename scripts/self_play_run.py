"""Run TDLeaf(λ) self-play at a scale a notebook cannot afford.

The notebook shows the mechanism working over a hundred games and says plainly
that a hundred is two or three orders of magnitude short. This is the run that
tests the claim.

The measure at the end is playing strength, not weight similarity. A learned
table that correlates with the hand-written one but loses to it has not
learned chess, and one that looks nothing like it but wins has.

    python -m scripts.self_play_run --games 10000
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import chess
import numpy as np

from engine.evaluation.pst import RAW_MG
from engine.levels.search_engine import SearchEngine
from engine.search.alphabeta import search_alphabeta
from engine.search.context import RootResult, SearchStats
from research.self_play.value_learner import PieceSquareEvaluator, TDConfig, ValueLearner
from tournament.match import play_match
from tournament.openings import book

CENTRE = (chess.D4, chess.E4, chess.D5, chess.E5)
RIM = (chess.A1, chess.H1, chess.A8, chess.H8)
PIECE_NAMES = ("pawn", "knight", "bishop", "rook", "queen", "king")


class LearnedEngine(SearchEngine):
    """Alpha-beta over a learned piece-square table, so it can be played."""

    level = 5
    default_name = "learned"
    depth = 3

    def __init__(self, evaluator: PieceSquareEvaluator, *args, **kwargs) -> None:
        kwargs.setdefault("time_limit", 1.0)
        super().__init__(*args, **kwargs)
        self.evaluator = evaluator

    def static_eval(self, board: chess.Board) -> int:
        return self.evaluator.static_eval(board)

    def _root_search(
        self, board: chess.Board, stats: SearchStats, root_moves: list[chess.Move]
    ) -> RootResult:
        return search_alphabeta(
            board, self.depth, self.static_eval, stats=stats, root_moves=root_moves
        )


def centre_minus_rim(weights: np.ndarray, piece_index: int) -> float:
    table = weights[piece_index * 64 : (piece_index + 1) * 64]
    return float(np.mean([table[s] for s in CENTRE]) - np.mean([table[s] for s in RIM]))


def reference_centre_minus_rim(piece_type: chess.PieceType) -> float:
    table = RAW_MG[piece_type]
    return float(np.mean([table[s ^ 56] for s in CENTRE]) - np.mean([table[s ^ 56] for s in RIM]))


def shape_correlation(weights: np.ndarray, piece_index: int, piece_type: chess.PieceType) -> float:
    """How closely a learned table's *shape* matches the hand-written one.

    Compared after removing each table's mean, because the mean is the piece
    value — which was seeded, not learned, and would inflate every correlation
    to nearly one.
    """
    learned = weights[piece_index * 64 : (piece_index + 1) * 64]
    reference = np.array([RAW_MG[piece_type][s ^ 56] for s in range(64)], dtype=np.float64)
    learned = learned - learned.mean()
    reference = reference - reference.mean()
    if learned.std() < 1e-9 or reference.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(learned, reference)[0, 1])


def main() -> int:
    parser = argparse.ArgumentParser(description="TDLeaf(λ) self-play at scale")
    parser.add_argument("--games", type=int, default=10_000)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--max-plies", type=int, default=120)
    parser.add_argument("--learning-rate", type=float, default=40.0)
    parser.add_argument("--lam", type=float, default=0.7)
    parser.add_argument("--epsilon", type=float, default=0.12)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--match-games", type=int, default=16, help="0 to skip the match")
    parser.add_argument("--out", default="data/self_play_run.json")
    args = parser.parse_args()

    evaluator = PieceSquareEvaluator.material_only()
    learner = ValueLearner(
        evaluator,
        TDConfig(
            games=args.games,
            depth=args.depth,
            max_plies=args.max_plies,
            learning_rate=args.learning_rate,
            lam=args.lam,
            epsilon=args.epsilon,
            time_limit=0.05,
            seed=args.seed,
        ),
    )

    trace: list[dict] = []
    started = time.perf_counter()

    def track(index: int, game, error: float) -> None:
        if index % 100 == 0 or index == 1:
            snapshot = {
                "game": index,
                "td_error": error,
                "knight": centre_minus_rim(evaluator.weights, 1),
                "bishop": centre_minus_rim(evaluator.weights, 2),
                "rook": centre_minus_rim(evaluator.weights, 3),
                "elapsed": time.perf_counter() - started,
            }
            trace.append(snapshot)
            print(
                f"{index:>6} games  |TD| {error:.4f}  knight {snapshot['knight']:+7.1f}  "
                f"bishop {snapshot['bishop']:+7.1f}  rook {snapshot['rook']:+7.1f}  "
                f"{snapshot['elapsed']:.0f}s",
                flush=True,
            )

    result = learner.train(on_game=track)
    seconds = time.perf_counter() - started

    print(f"\n{args.games} games in {seconds / 60:.1f} min")
    print(
        "outcomes: white %d, black %d, draw %d"
        % (
            result.outcomes.count(1.0),
            result.outcomes.count(-1.0),
            result.outcomes.count(0.0),
        )
    )

    print(f"\n{'piece':<8} {'learned c-r':>12} {'reference':>10} {'shape corr':>11}")
    print("-" * 44)
    shapes = {}
    for index, piece_type in enumerate(
        (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)
    ):
        learned = centre_minus_rim(evaluator.weights, index)
        reference = reference_centre_minus_rim(piece_type)
        correlation = shape_correlation(evaluator.weights, index, piece_type)
        shapes[PIECE_NAMES[index]] = {
            "learned_centre_minus_rim": learned,
            "reference_centre_minus_rim": reference,
            "shape_correlation": correlation,
        }
        print(f"{PIECE_NAMES[index]:<8} {learned:>12.1f} {reference:>10.1f} {correlation:>11.3f}")

    match_scores = {}
    if args.match_games:
        print("\nthe only measure that counts: does it play better?")
        for label, opponent_weights in (
            ("material-only start", PieceSquareEvaluator.material_only().weights),
            ("hand-written tables", PieceSquareEvaluator.from_engine_tables().weights),
        ):
            learned_engine = LearnedEngine(
                PieceSquareEvaluator(evaluator.weights), name="learned", seed=1, time_limit=0.2
            )
            opponent = LearnedEngine(
                PieceSquareEvaluator(opponent_weights), name=label, seed=2, time_limit=0.2
            )
            match = play_match(
                learned_engine,
                opponent,
                openings=book(max(1, args.match_games // 2)),
                games=args.match_games,
                max_plies=200,
            )
            match_scores[label] = match.score
            print(f"  vs {label:<22} {match.summary()}")

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "games": args.games,
                "seconds": seconds,
                "trace": trace,
                "shapes": shapes,
                "match_scores": match_scores,
                "weights": evaluator.weights.tolist(),
            },
            indent=1,
        )
    )
    print(f"\nwritten to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
