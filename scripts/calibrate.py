"""Place an external engine on this project's ladder.

A rating measured only against your own engines is self-consistent and could
still be uniformly wrong. This plays an external UCI engine against the rungs
until it finds the one it matches, which calibrates both sides at once: the
outsider gets a rating in this ladder's units, and the ladder gets a check
that its numbers mean something outside itself.

    python -m scripts.calibrate --engine /path/to/engine --levels 3-7
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from elo.calculator import elo_diff_from_score, performance_rating
from engine.levels import available_levels, create_engine
from engine.utils.constants import INITIAL_ELO
from tournament.match import play_match
from tournament.openings import book
from tournament.uci_engine import UciEngineError, UciEngineProcess, UciLimits


def parse_levels(spec: str) -> list[int]:
    if spec == "all":
        return available_levels()
    levels: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            levels.extend(range(int(start), int(end) + 1))
        else:
            levels.append(int(part))
    return [level for level in levels if level in available_levels()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Rate an external UCI engine against the ladder")
    parser.add_argument("--engine", required=True, help="path to the external UCI engine")
    parser.add_argument("--name", default=None)
    parser.add_argument("--levels", default="3-7")
    parser.add_argument("--games", type=int, default=8, help="games per level")
    parser.add_argument("--movetime", type=float, default=0.2, help="seconds per move, both sides")
    parser.add_argument("--max-plies", type=int, default=200)
    parser.add_argument("--out", default="data/calibration.json")
    args = parser.parse_args()

    levels = parse_levels(args.levels)
    if not levels:
        raise SystemExit(f"no implemented levels in {args.levels!r}")

    external = UciEngineProcess(
        [args.engine],
        name=args.name or Path(args.engine).name,
        limits=UciLimits(movetime=args.movetime),
    )

    print(f"{'matchup':<28} {'score':>7} {'W-D-L':>10} {'implied':>9} {'time':>7}")
    print("-" * 66)

    rows = []
    opponent_ratings: list[float] = []
    points = 0.0
    started = time.perf_counter()

    with external:
        for level in levels:
            # Fixed time per move on both sides. Fixed *depth* would compare
            # nothing: one engine's depth 6 is another's depth 3.
            ours = create_engine(level, seed=level * 13, time_limit=args.movetime)
            external.new_game()
            elapsed = time.perf_counter()
            try:
                match = play_match(
                    external,
                    ours,
                    openings=book(max(1, args.games // 2)),
                    games=args.games,
                    max_plies=args.max_plies,
                )
            except UciEngineError as error:
                print(f"{external.name} vs L{level}: aborted — {error}")
                break

            rating = INITIAL_ELO[level]
            opponent_ratings += [float(rating)] * match.played
            points += match.score * match.played
            rows.append(
                {
                    "level": level,
                    "level_elo": rating,
                    "score": match.score,
                    "wins": match.wins,
                    "draws": match.draws,
                    "losses": match.losses,
                    "implied_elo": rating + elo_diff_from_score(match.score),
                }
            )
            print(
                f"{external.name + ' vs L' + str(level):<28} {match.score:>6.1%} "
                f"{f'{match.wins}-{match.draws}-{match.losses}':>10} "
                f"{rating + elo_diff_from_score(match.score):>9.0f} "
                f"{time.perf_counter() - elapsed:>6.0f}s"
            )

    print("-" * 66)
    if opponent_ratings:
        overall = performance_rating(opponent_ratings, points / len(opponent_ratings))
        print(f"{external.name} performance rating over the whole gauntlet: {overall:.0f}")
        nearest = min(rows, key=lambda row: abs(row["score"] - 0.5))
        print(f"closest rung: Level {nearest['level']} (scored {nearest['score']:.1%} against it)")
    else:
        overall = None

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "engine": external.name,
                "reported_name": external.reported_name,
                "movetime": args.movetime,
                "games_per_level": args.games,
                "rows": rows,
                "performance_rating": overall,
                "seconds": time.perf_counter() - started,
            },
            indent=1,
        )
    )
    print(f"written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
