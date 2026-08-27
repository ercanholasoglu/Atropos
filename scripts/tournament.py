"""Run a tournament from the command line and write the results to the database.

python -m scripts.tournament --format round-robin --levels 1-4 --games 4
python -m scripts.tournament --format swiss --levels all --rounds 5
python -m scripts.tournament --format gauntlet --test 5 --levels 1-4 --games 6
"""

from __future__ import annotations

import argparse

from elo.database import DEFAULT_DB_PATH, EloDatabase
from elo.leaderboard import format_leaderboard
from elo.tracker import EloTracker
from engine.levels import available_levels, create_engine
from tournament.gauntlet import GauntletTournament
from tournament.match import GameRecord
from tournament.openings import book
from tournament.round_robin import RoundRobinTournament
from tournament.swiss import SwissTournament


def parse_levels(spec: str) -> list[int]:
    """Accept ``all``, ``1-4``, or ``1,3,5``."""
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
    unknown = [level for level in levels if level not in available_levels()]
    if unknown:
        raise SystemExit(f"levels not implemented: {unknown}")
    return levels


def progress(done: int, total: int, record: GameRecord) -> None:
    print(
        f"  [{done:>3}/{total}] {record.white} - {record.black}: "
        f"{record.result:<7} {record.plies:>3} plies ({record.reason})"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an engine tournament")
    parser.add_argument(
        "--format", choices=["round-robin", "swiss", "gauntlet"], default="round-robin"
    )
    parser.add_argument("--levels", default="all", help="'all', '1-4' or '1,3,5'")
    parser.add_argument("--test", type=int, help="gauntlet: the level under test")
    parser.add_argument("--games", type=int, default=2, help="games per pair / per opponent")
    parser.add_argument("--rounds", type=int, default=5, help="swiss: number of rounds")
    parser.add_argument("--max-plies", type=int, default=300)
    parser.add_argument(
        "--time", type=float, default=None, dest="time_limit", help="seconds per move"
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--no-rating", action="store_true", help="do not touch the database")
    args = parser.parse_args()

    levels = parse_levels(args.levels)
    engines = [create_engine(level, seed=level * 7, time_limit=args.time_limit) for level in levels]

    tracker = None
    db = None
    if not args.no_rating:
        db = EloDatabase(args.db)
        tracker = EloTracker(db)

    common = dict(
        openings=book(),
        max_plies=args.max_plies,
        tracker=tracker,
        on_game=progress,
    )

    tournament: RoundRobinTournament | SwissTournament | GauntletTournament
    if args.format == "gauntlet":
        if args.test is None:
            raise SystemExit("--test LEVEL is required for a gauntlet")
        test_engine = create_engine(args.test, seed=99, time_limit=args.time_limit)
        opponents = [e for e in engines if e.level != args.test]
        if not opponents:
            raise SystemExit("the gauntlet field cannot be only the engine under test")
        tournament = GauntletTournament(
            test_engine, opponents, games_per_opponent=args.games, **common
        )
    elif args.format == "swiss":
        tournament = SwissTournament(engines, rounds=args.rounds, **common)
    else:
        tournament = RoundRobinTournament(engines, games_per_pair=args.games, **common)

    print(f"{tournament.format}: {tournament.total_games} games\n")
    result = tournament.run()

    print(f"\n{tournament.format} standings\n")
    print(result.table())

    if isinstance(tournament, GauntletTournament):
        print(
            f"\nperformance rating for {tournament.test_engine.name}: "
            f"{tournament.estimate_rating(result):.0f}"
        )

    if db is not None:
        print("\nleaderboard\n")
        print(format_leaderboard(db.get_leaderboard()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
