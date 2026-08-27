"""Validate the level ladder: does each level really beat the one below it?

This is the long-running gauntlet behind the numbers in the README. The test
suite only carries a cheap regression guard — certifying the ">70% against
the level below" criterion needs a sample far larger than a test run should
take.

    python -m scripts.ladder                  # adjacent pairs, 16 games each
    python -m scripts.ladder --games 40
    python -m scripts.ladder --all            # every pairing
    python -m scripts.ladder --time 0.2       # fixed time control instead
"""

from __future__ import annotations

import argparse
import itertools
import time

from engine.levels import available_levels, create_engine
from tournament.match import MatchResult, play_match
from tournament.openings import book


def run_pair(
    higher: int, lower: int, games: int, max_plies: int, time_limit: float | None
) -> MatchResult:
    openings = book()
    # Enough openings that no line is played more than twice per colour.
    needed = max(1, games // 2)
    if needed > len(openings):
        openings = (openings * (needed // len(openings) + 1))[:needed]
    return play_match(
        create_engine(higher, seed=higher * 1000 + games, time_limit=time_limit),
        create_engine(lower, seed=lower * 1000 + games, time_limit=time_limit),
        openings=openings[:needed],
        games=games,
        max_plies=max_plies,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the level ladder gauntlet")
    parser.add_argument("--games", type=int, default=16, help="games per pairing")
    parser.add_argument("--max-plies", type=int, default=300)
    parser.add_argument("--all", action="store_true", help="every pairing, not just adjacent ones")
    parser.add_argument("--pair", help="a single matchup, e.g. 7:6")
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument(
        "--time",
        type=float,
        default=None,
        dest="time_limit",
        help="seconds per move for every engine; default is each level's own setting",
    )
    args = parser.parse_args()

    levels = available_levels()
    if args.pair:
        high, low = (int(part) for part in args.pair.split(":"))
        pairs = [(high, low)]
    elif args.all:
        pairs = [(hi, lo) for lo, hi in itertools.combinations(levels, 2)]
    else:
        pairs = [(hi, lo) for lo, hi in zip(levels, levels[1:])]

    print(f"{'matchup':<28} {'score':>7} {'W-D-L':>10} {'decisive':>9} {'time':>7}")
    print("-" * 66)

    failures = []
    for higher, lower in pairs:
        start = time.perf_counter()
        match = run_pair(higher, lower, args.games, args.max_plies, args.time_limit)
        elapsed = time.perf_counter() - start
        decisive = sum(1 for g in match.games if g.decisive)
        label = f"L{higher} vs L{lower}"
        print(
            f"{label:<28} {match.score:>6.1%} "
            f"{f'{match.wins}-{match.draws}-{match.losses}':>10} "
            f"{f'{decisive}/{match.played}':>9} {elapsed:>6.0f}s"
        )
        if match.score <= args.threshold:
            failures.append(f"{label} scored {match.score:.1%}")

    print("-" * 66)
    if failures:
        print(f"below the {args.threshold:.0%} threshold: " + "; ".join(failures))
        return 1
    print(f"every pairing clears {args.threshold:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
