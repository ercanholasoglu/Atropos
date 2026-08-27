"""Elo rating arithmetic.

Elo answers one question: given two ratings, what score does the stronger
player expect? Everything else — the update after a game, a performance
rating over a gauntlet — follows from that one curve. A 400-point gap means
the favourite is expected to score 10 out of 11.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

WIN = 1.0
DRAW = 0.5
LOSS = 0.0


@dataclass
class EloCalculator:
    """Standard Elo with an optional provisional K-factor.

    The K-factor is how far one game can move a rating. New engines start
    with a high K so their rating finds its level quickly, then settle to a
    lower one so a single result cannot swing an established rating.
    """

    k_factor: int = 32
    provisional_k: int = 40
    provisional_games: int = 30

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """What A is expected to score against B, between 0 and 1."""
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    def k_for(self, games_played: int) -> int:
        """The K-factor to apply to a player with this much history."""
        return self.provisional_k if games_played < self.provisional_games else self.k_factor

    def update_ratings(
        self,
        rating_a: float,
        rating_b: float,
        result: float,
        games_a: int | None = None,
        games_b: int | None = None,
    ) -> tuple[float, float]:
        """New ratings after one game. ``result`` is A's score: 1, 0.5 or 0."""
        if not 0.0 <= result <= 1.0:
            raise ValueError(f"result must be between 0 and 1, got {result}")

        expected_a = self.expected_score(rating_a, rating_b)
        k_a = self.k_for(games_a) if games_a is not None else self.k_factor
        k_b = self.k_for(games_b) if games_b is not None else self.k_factor

        new_a = rating_a + k_a * (result - expected_a)
        new_b = rating_b + k_b * ((1 - result) - (1 - expected_a))
        return new_a, new_b

    def rating_change(
        self, rating_a: float, rating_b: float, result: float, games_a: int | None = None
    ) -> float:
        """How much A's rating moves — the delta on its own."""
        new_a, _ = self.update_ratings(rating_a, rating_b, result, games_a=games_a)
        return new_a - rating_a


def expected_score_from_elo_diff(diff: float) -> float:
    """Expected score for a player rated ``diff`` points above the opponent."""
    return 1 / (1 + 10 ** (-diff / 400))


def elo_diff_from_score(score: float) -> float:
    """The rating gap a score implies — the inverse of the Elo curve.

    A clean sweep implies an unbounded gap, so perfect and zero scores are
    reported at the ±800 ceiling rather than as infinity.
    """
    if score <= 0.0:
        return -800.0
    if score >= 1.0:
        return 800.0
    return -400 * math.log10(1 / score - 1)


def performance_rating(opponent_ratings: list[float], score: float) -> float:
    """The rating that would have been *expected* to score this much.

    Solved numerically rather than with the usual "average opponent + 400 ×
    (wins − losses) / games" shortcut, which is only an approximation and
    drifts badly when the opponents are spread out — exactly the case in a
    gauntlet against a whole ladder.
    """
    if not opponent_ratings:
        raise ValueError("a performance rating needs at least one opponent")
    games = len(opponent_ratings)
    target = score * games

    low, high = min(opponent_ratings) - 800, max(opponent_ratings) + 800
    for _ in range(60):  # ~1e-16 of the starting interval; far past what Elo means
        mid = (low + high) / 2
        expected = sum(expected_score_from_elo_diff(mid - r) for r in opponent_ratings)
        if expected < target:
            low = mid
        else:
            high = mid
    return (low + high) / 2
