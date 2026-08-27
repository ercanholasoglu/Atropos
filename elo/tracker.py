"""Wiring the engines, the match runner and the rating database together.

The tracker is the only place that knows how a finished game becomes two new
ratings: it reads both engines' current ratings, asks the calculator what the
result implies, and writes the game and the updates in one transaction.
"""

from __future__ import annotations

from dataclasses import dataclass

from elo.calculator import EloCalculator
from elo.database import EloDatabase
from engine.base_engine import BaseEngine
from engine.utils.helpers import result_to_score
from tournament.match import GameRecord, MatchResult


@dataclass
class RatingUpdate:
    """What one game did to two ratings."""

    game_id: int
    white: str
    black: str
    result: str
    white_before: float
    black_before: float
    white_after: float
    black_after: float

    @property
    def white_delta(self) -> float:
        return self.white_after - self.white_before

    @property
    def black_delta(self) -> float:
        return self.black_after - self.black_before


class EloTracker:
    """Keeps engine ratings in step with the games they play."""

    def __init__(
        self,
        db: EloDatabase | None = None,
        calculator: EloCalculator | None = None,
    ) -> None:
        self.db = db or EloDatabase()
        self.calculator = calculator or EloCalculator()

    # --- engines ----------------------------------------------------------

    def register(self, engine: BaseEngine) -> None:
        """Make sure an engine exists in the database and adopt its rating.

        The engine object starts each session at its level's nominal rating;
        if the database already knows better, the database wins.
        """
        self.db.register_engine(engine.name, engine.level, engine.elo)
        stored = self.db.get_engine(engine.name)
        if stored:
            engine.elo = stored["elo"]
            engine.games_played = stored["games_played"]

    def register_all(self, engines: list[BaseEngine]) -> None:
        for engine in engines:
            self.register(engine)

    def rating(self, name: str, default: float = 1000.0) -> float:
        stored = self.db.get_rating(name)
        return stored if stored is not None else default

    # --- results ----------------------------------------------------------

    def record_game(self, record: GameRecord, event: str = "") -> RatingUpdate:
        """Rate one finished game and store it."""
        white = self.db.get_engine(record.white)
        black = self.db.get_engine(record.black)
        if white is None or black is None:
            missing = record.white if white is None else record.black
            raise KeyError(f"engine {missing!r} is not registered")

        score = result_to_score(record.result)
        white_after, black_after = self.calculator.update_ratings(
            white["elo"],
            black["elo"],
            score,
            games_a=white["games_played"],
            games_b=black["games_played"],
        )

        game_id = self.db.record_game(
            white=record.white,
            black=record.black,
            result=record.result,
            white_elo_before=white["elo"],
            black_elo_before=black["elo"],
            white_elo_after=white_after,
            black_elo_after=black_after,
            pgn=record.pgn,
            moves_count=record.plies,
            opening=record.opening,
            termination=record.reason,
            event=event,
        )

        return RatingUpdate(
            game_id=game_id,
            white=record.white,
            black=record.black,
            result=record.result,
            white_before=white["elo"],
            black_before=black["elo"],
            white_after=white_after,
            black_after=black_after,
        )

    def record_match(self, match: MatchResult, event: str = "") -> list[RatingUpdate]:
        return [self.record_game(game, event=event) for game in match.games]

    def sync(self, engine: BaseEngine) -> None:
        """Copy the stored rating and record back onto a live engine object."""
        stored = self.db.get_engine(engine.name)
        if stored:
            engine.elo = stored["elo"]
            engine.games_played = stored["games_played"]

    # --- reporting --------------------------------------------------------

    def statistics(self, name: str) -> dict:
        """Everything the UI shows about one engine."""
        engine = self.db.get_engine(name)
        if engine is None:
            raise KeyError(f"engine {name!r} is not registered")

        history = [entry["elo"] for entry in self.db.get_elo_history(name)]
        played = engine["games_played"]
        points = engine["wins"] + 0.5 * engine["draws"]
        return {
            "name": name,
            "level": engine["level"],
            "elo": engine["elo"],
            "initial_elo": engine["initial_elo"],
            "elo_change": engine["elo"] - engine["initial_elo"],
            "peak_elo": max(history) if history else engine["elo"],
            "lowest_elo": min(history) if history else engine["elo"],
            "games_played": played,
            "wins": engine["wins"],
            "losses": engine["losses"],
            "draws": engine["draws"],
            "points": points,
            "score_pct": points / played if played else 0.0,
        }

    def rebuild(self) -> None:
        """Recompute every rating by replaying the game log.

        The log is the source of truth and the ratings in ``engines`` are a
        cache of it. This rebuilds that cache — useful after changing the
        K-factor, and the property that makes the claim testable.
        """
        games = sorted(self.db.get_games(), key=lambda g: g["id"])
        engines = self.db.list_engines()
        ratings = {e["name"]: e["initial_elo"] for e in engines}
        counts = {e["name"]: 0 for e in engines}

        with self.db.connect() as conn:
            conn.execute("DELETE FROM elo_history")
            for name, rating in ratings.items():
                conn.execute(
                    """UPDATE engines SET elo = ?, games_played = 0, wins = 0,
                              losses = 0, draws = 0 WHERE name = ?""",
                    (rating, name),
                )

            for game in games:
                white, black = game["white_engine"], game["black_engine"]
                score = result_to_score(game["result"])
                white_after, black_after = self.calculator.update_ratings(
                    ratings[white],
                    ratings[black],
                    score,
                    games_a=counts[white],
                    games_b=counts[black],
                )
                conn.execute(
                    """UPDATE games SET white_elo_before = ?, black_elo_before = ?,
                              white_elo_after = ?, black_elo_after = ? WHERE id = ?""",
                    (ratings[white], ratings[black], white_after, black_after, game["id"]),
                )
                ratings[white], ratings[black] = white_after, black_after
                counts[white] += 1
                counts[black] += 1

                for name, rating, result_for in (
                    (white, white_after, score),
                    (black, black_after, 1 - score),
                ):
                    conn.execute(
                        """UPDATE engines
                              SET elo = ?, games_played = games_played + 1,
                                  wins = wins + ?, losses = losses + ?, draws = draws + ?
                            WHERE name = ?""",
                        (
                            rating,
                            1 if result_for == 1.0 else 0,
                            1 if result_for == 0.0 else 0,
                            1 if result_for == 0.5 else 0,
                            name,
                        ),
                    )
                    conn.execute(
                        """INSERT INTO elo_history (engine_name, elo, game_id, recorded_at)
                           VALUES (?, ?, ?, ?)""",
                        (name, rating, game["id"], game["played_at"]),
                    )
