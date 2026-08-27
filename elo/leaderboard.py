"""Rankings and the tables built on top of them."""

from __future__ import annotations

from elo.calculator import performance_rating
from elo.database import EloDatabase


def rankings(db: EloDatabase) -> list[dict]:
    """The leaderboard, best rating first."""
    return db.get_leaderboard()


def head_to_head_matrix(db: EloDatabase, names: list[str] | None = None) -> dict:
    """Every pairing's score, as ``matrix[a][b] = a's score against b``."""
    if names is None:
        names = [engine["name"] for engine in db.get_leaderboard()]
    matrix: dict[str, dict[str, float | None]] = {}
    for a in names:
        matrix[a] = {}
        for b in names:
            if a == b:
                matrix[a][b] = None
                continue
            record = db.head_to_head(a, b)
            matrix[a][b] = record["score"] if record["games"] else None
    return matrix


def gauntlet_rating(db: EloDatabase, name: str) -> float | None:
    """What an engine's results say its rating should be.

    The stored Elo is a running average that depends on the order games were
    played in; this is the rating its whole record implies at once, which is
    the honest number to quote after a gauntlet.
    """
    games = db.get_games(engine_name=name)
    if not games:
        return None

    opponents: list[float] = []
    points = 0.0
    for game in games:
        is_white = game["white_engine"] == name
        opponent = game["black_engine"] if is_white else game["white_engine"]
        opponent_engine = db.get_engine(opponent)
        if opponent_engine is None:
            continue
        opponents.append(opponent_engine["elo"])
        if game["result"] == "1/2-1/2":
            points += 0.5
        elif (game["result"] == "1-0") == is_white:
            points += 1.0

    if not opponents:
        return None
    return performance_rating(opponents, points / len(opponents))


def format_leaderboard(rows: list[dict]) -> str:
    """A plain-text leaderboard for the CLI and the README."""
    if not rows:
        return "no engines registered"

    header = f"{'#':<3} {'engine':<16} {'elo':>7} {'±':>7} {'games':>6} {'W-D-L':>12} {'score':>7}"
    lines = [header, "-" * len(header)]
    for row in rows:
        record = f"{row['wins']}-{row['draws']}-{row['losses']}"
        lines.append(
            f"{row['rank']:<3} {row['name']:<16} {row['elo']:>7.1f} "
            f"{row['elo_change']:>+7.1f} {row['games_played']:>6} {record:>12} "
            f"{row['score_pct']:>6.1%}"
        )
    return "\n".join(lines)
