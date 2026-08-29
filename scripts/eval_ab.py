"""Does the smarter evaluation actually win games?

A new evaluation term is always an improvement on paper — it knows something
the old one did not. In a search it is also a cost, because every microsecond
at a leaf is depth not searched, and depth is the strongest thing an engine
has. The two effects point in opposite directions and no amount of reasoning
settles which is larger.

So the terms go in, and then they play. Same search, same time per move, only
the evaluation differs. A variant that cannot beat the one it replaces does
not ship.

    python -m scripts.eval_ab --games 24 --movetime 0.2
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

import chess

from elo.calculator import elo_diff_from_score
from engine.evaluation.tapered import (
    positional_eval,
    positional_eval_passers,
    positional_eval_rooks,
    positional_eval_v2,
    positional_eval_v3,
)
from engine.levels.level6_tactical import Level6Tactical
from scripts.telemetry import TelemetryRecorder
from tournament.match import play_match
from tournament.openings import book

VARIANTS = {
    # "v2" is the evaluation as it stood before the rook term was adopted, so
    # every measurement in the README that names it stays reproducible.
    "v2": lambda board: positional_eval_v2(board),
    "current": lambda board: positional_eval(board),
    "v3-passers": lambda board: positional_eval_passers(board),
    "v3-rooks": lambda board: positional_eval_rooks(board),
    "v3-shelter": lambda board: positional_eval_v3(board, king_attackers=False),
    "v3-full": lambda board: positional_eval_v3(board, king_attackers=True),
}


class VariantEngine(Level6Tactical):
    """Level 6's search with the evaluation swapped underneath it."""

    def __init__(self, variant: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.variant = variant
        self._evaluate = VARIANTS[variant]
        self.name = variant

    def static_eval(self, board: chess.Board) -> int:
        return self._evaluate(board)


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B the evaluation variants")
    parser.add_argument("--games", type=int, default=24, help="games per pairing")
    parser.add_argument("--movetime", type=float, default=0.2)
    parser.add_argument("--max-plies", type=int, default=200)
    parser.add_argument("--variants", default="v2,v3-shelter,v3-full")
    parser.add_argument("--out", default="data/eval_ab.json")
    args = parser.parse_args()

    names = [name.strip() for name in args.variants.split(",") if name.strip() in VARIANTS]
    if len(names) < 2:
        raise SystemExit(f"need at least two known variants; got {names}")

    recorder = TelemetryRecorder(
        "eval_ab",
        {
            "variants": names,
            "games_per_pairing": args.games,
            "movetime": args.movetime,
            "max_plies": args.max_plies,
        },
    )

    print(f"{'matchup':<28} {'score':>7} {'W-D-L':>10} {'elo':>7} {'time':>7}", flush=True)
    print("-" * 64, flush=True)

    rows = []
    started = time.perf_counter()
    for first, second in itertools.combinations(names, 2):
        elapsed = time.perf_counter()
        match = play_match(
            VariantEngine(first, seed=11, time_limit=args.movetime),
            VariantEngine(second, seed=22, time_limit=args.movetime),
            openings=book(max(1, args.games // 2)),
            games=args.games,
            max_plies=args.max_plies,
        )
        for game in match.games:
            recorder.add_nodes(game.nodes)
            recorder.add_games()
        elo = elo_diff_from_score(match.score)
        rows.append(
            {
                "a": first,
                "b": second,
                "score": match.score,
                "wins": match.wins,
                "draws": match.draws,
                "losses": match.losses,
                "elo": elo,
            }
        )
        print(
            f"{first + ' vs ' + second:<28} {match.score:>6.1%} "
            f"{f'{match.wins}-{match.draws}-{match.losses}':>10} {elo:>+7.0f} "
            f"{time.perf_counter() - elapsed:>6.0f}s",
            flush=True,
        )
        # Written after every pairing, not at the end: a run that is cut short
        # should still leave behind the matches it finished.
        _write(args.out, args, rows, time.perf_counter() - started)

    print("-" * 64)
    standard_error = 0.5 / (args.games**0.5)
    print(f"one standard error on a {args.games}-game match: {standard_error:.1%}", flush=True)
    for row in rows:
        if abs(row["score"] - 0.5) < standard_error:
            print(f"  {row['a']} vs {row['b']}: inside the noise — no verdict", flush=True)

    _write(args.out, args, rows, time.perf_counter() - started)
    recorder.write({"rows": rows, "standard_error": 0.5 / (args.games**0.5)})
    print(f"written to {args.out}")
    print(f"telemetry: {recorder.summary()}")
    print(f"           {recorder.path}")
    return 0


def _write(path: str, args, rows: list[dict], seconds: float) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "games": args.games,
                "movetime": args.movetime,
                "rows": rows,
                "seconds": seconds,
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
