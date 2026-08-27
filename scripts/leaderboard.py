"""Print the current rating table.

python -m scripts.leaderboard
python -m scripts.leaderboard --engine L5-Positional
"""

from __future__ import annotations

import argparse

from elo.database import DEFAULT_DB_PATH, EloDatabase
from elo.leaderboard import format_leaderboard, gauntlet_rating, head_to_head_matrix
from elo.tracker import EloTracker


def main() -> int:
    parser = argparse.ArgumentParser(description="Show the Elo leaderboard")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--engine", help="show one engine's record in detail")
    parser.add_argument("--matrix", action="store_true", help="head-to-head scores")
    args = parser.parse_args()

    db = EloDatabase(args.db)
    board = db.get_leaderboard()
    if not board:
        print("no engines registered yet — run `make tournament` first")
        return 0

    print(format_leaderboard(board))

    if args.matrix:
        names = [row["name"] for row in board]
        matrix = head_to_head_matrix(db, names)
        width = max(len(n) for n in names) + 1
        print("\nhead to head (row's score against column)\n")
        print(" " * width + "".join(f"{n[:7]:>8}" for n in names))
        for a in names:
            cells = "".join(
                "       -" if matrix[a][b] is None else f"{matrix[a][b]:>8.1%}" for b in names
            )
            print(f"{a:<{width}}{cells}")

    if args.engine:
        stats = EloTracker(db).statistics(args.engine)
        estimate = gauntlet_rating(db, args.engine)
        print(f"\n{stats['name']} (level {stats['level']})")
        print(
            f"  rating      {stats['elo']:.1f}  ({stats['elo_change']:+.1f} from {stats['initial_elo']:.0f})"
        )
        print(f"  peak / low  {stats['peak_elo']:.1f} / {stats['lowest_elo']:.1f}")
        print(
            f"  record      {stats['wins']}-{stats['draws']}-{stats['losses']} in {stats['games_played']} games ({stats['score_pct']:.1%})"
        )
        if estimate is not None:
            print(f"  performance {estimate:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
