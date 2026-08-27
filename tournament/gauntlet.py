"""Gauntlet: one engine against a field.

The format for answering "how strong is this new version?". Only the test
engine's results matter, so every game it plays is signal — unlike a
round-robin, where most of the schedule is opponents playing each other.
"""

from __future__ import annotations

from engine.base_engine import BaseEngine
from tournament.base import Pairing, Tournament, TournamentResult


class GauntletTournament(Tournament):
    format = "gauntlet"

    def __init__(
        self,
        test_engine: BaseEngine,
        opponents: list[BaseEngine],
        *args,
        games_per_opponent: int = 2,
        **kwargs,
    ) -> None:
        if not opponents:
            raise ValueError("a gauntlet needs at least one opponent")
        if games_per_opponent < 1:
            raise ValueError("games_per_opponent must be at least 1")
        super().__init__([test_engine, *opponents], *args, **kwargs)
        self.test_engine = test_engine
        self.opponents = opponents
        self.games_per_opponent = games_per_opponent

    def generate_pairings(self) -> list[Pairing]:
        pairings: list[Pairing] = []
        index = 0
        for round_, opponent in enumerate(self.opponents, start=1):
            for game in range(self.games_per_opponent):
                white, black = (
                    (self.test_engine, opponent) if game % 2 == 0 else (opponent, self.test_engine)
                )
                pairings.append(
                    Pairing(
                        white=white,
                        black=black,
                        opening=self.opening_for(index // 2),
                        round_=round_,
                    )
                )
                index += 1
        return pairings

    def estimate_rating(self, result: TournamentResult) -> float:
        """The rating the test engine's score implies against this field.

        Computed from the whole record at once rather than game by game, so
        it does not depend on the order the gauntlet happened to run in.
        """
        from elo.calculator import performance_rating

        opponent_ratings: list[float] = []
        points = 0.0
        for record in result.games:
            is_white = record.white == self.test_engine.name
            opponent_name = record.black if is_white else record.white
            opponent = next(o for o in self.opponents if o.name == opponent_name)
            opponent_ratings.append(opponent.elo)
            points += record.white_score if is_white else 1 - record.white_score

        return performance_rating(opponent_ratings, points / len(opponent_ratings))
