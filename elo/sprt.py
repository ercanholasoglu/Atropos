"""Sequential testing: stop as soon as the games have answered.

A fixed-length match asks the wrong question. Sixty games either resolve a
change or they do not, and which one it is depends on how big the change turned
out to be — something you only learn afterwards. Three times in this project a
fixed match came back "inside the noise", each time after spending the whole
budget to learn nothing.

A sequential test spends games until it has an answer instead. After every
game it asks how much more likely the results are under "this change is worth
at least *elo1*" than under "this change is worth at most *elo0*", and stops
the moment that ratio is decisive either way. A change that is clearly good is
confirmed in a few dozen games; one that is clearly bad is rejected just as
fast; only a change sitting exactly on the boundary costs the full budget —
and that is the case where the games really are needed.

The probability model is BayesElo's: a rating difference and a *draw elo* that
says how drawish the pairing is. Draws carry almost no information about which
side is better, so a pairing that draws 80% of the time needs far more games
than one that does not — and estimating that ratio from the games themselves,
rather than assuming it, is what keeps the test honest at both extremes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

WIN = 1.0
DRAW = 0.5
LOSS = 0.0


class Verdict(str, Enum):
    CONTINUE = "continue"
    ACCEPT_H1 = "accept H1"  # the change is at least elo1
    ACCEPT_H0 = "accept H0"  # the change is at most elo0
    EXHAUSTED = "out of games"


@dataclass
class SprtConfig:
    """The hypotheses and how wrong the test is allowed to be.

    ``elo0`` / ``elo1`` bracket the question. The usual pair for "is this an
    improvement at all" is [0, 10]: reject if it is no better, accept if it is
    worth ten Elo or more. A wider bracket answers faster and asks less.
    """

    elo0: float = 0.0
    elo1: float = 10.0
    alpha: float = 0.05  # chance of accepting a change that is not an improvement
    beta: float = 0.05  # chance of rejecting one that is
    max_games: int = 2000
    # Starting guess for how drawish the pairing is, replaced by the observed
    # ratio once there are enough games to estimate it.
    initial_draw_elo: float = 250.0
    min_games_for_draw_estimate: int = 20

    @property
    def lower_bound(self) -> float:
        return math.log(self.beta / (1 - self.alpha))

    @property
    def upper_bound(self) -> float:
        return math.log((1 - self.beta) / self.alpha)


def outcome_probabilities(elo: float, draw_elo: float) -> tuple[float, float, float]:
    """``(win, draw, loss)`` for a rating difference, BayesElo style."""
    win = 1.0 / (1.0 + 10 ** ((-elo + draw_elo) / 400.0))
    loss = 1.0 / (1.0 + 10 ** ((elo + draw_elo) / 400.0))
    return win, max(1.0 - win - loss, 1e-12), loss


def draw_elo_from_ratio(draw_ratio: float) -> float:
    """Turn an observed draw rate into the model's drawishness parameter."""
    draw_ratio = min(max(draw_ratio, 1e-6), 1 - 1e-6)
    return 400.0 * math.log10((1 + draw_ratio) / (1 - draw_ratio))


@dataclass
class Sprt:
    """Accumulates games until the evidence decides."""

    config: SprtConfig = field(default_factory=SprtConfig)
    wins: int = 0
    draws: int = 0
    losses: int = 0
    history: list[float] = field(default_factory=list)

    @property
    def games(self) -> int:
        return self.wins + self.draws + self.losses

    @property
    def score(self) -> float:
        return (self.wins + 0.5 * self.draws) / self.games if self.games else 0.5

    @property
    def draw_elo(self) -> float:
        """Estimated from the games once there are enough of them.

        Before that the configured starting guess is used: an early run of
        draws would otherwise push the estimate to an extreme and make the
        first few games count for far more or far less than they should.
        """
        if self.games < self.config.min_games_for_draw_estimate:
            return self.config.initial_draw_elo
        return draw_elo_from_ratio(self.draws / self.games)

    @property
    def llr(self) -> float:
        """Log-likelihood ratio of H1 over H0 for the games so far."""
        if not self.games:
            return 0.0
        draw_elo = self.draw_elo
        win0, draw0, loss0 = outcome_probabilities(self.config.elo0, draw_elo)
        win1, draw1, loss1 = outcome_probabilities(self.config.elo1, draw_elo)
        return (
            self.wins * math.log(win1 / win0)
            + self.draws * math.log(draw1 / draw0)
            + self.losses * math.log(loss1 / loss0)
        )

    def record(self, result: float) -> Verdict:
        """Add one game's result and report where the test stands."""
        if result == WIN:
            self.wins += 1
        elif result == LOSS:
            self.losses += 1
        else:
            self.draws += 1
        self.history.append(self.llr)
        return self.verdict

    @property
    def verdict(self) -> Verdict:
        if not self.games:
            return Verdict.CONTINUE
        value = self.llr
        if value >= self.config.upper_bound:
            return Verdict.ACCEPT_H1
        if value <= self.config.lower_bound:
            return Verdict.ACCEPT_H0
        if self.games >= self.config.max_games:
            return Verdict.EXHAUSTED
        return Verdict.CONTINUE

    @property
    def finished(self) -> bool:
        return self.verdict is not Verdict.CONTINUE

    def score_interval(self, z: float = 1.96) -> tuple[float, float]:
        """A confidence interval on the score, from the game outcomes.

        Draws are half a point with no variance of their own, so the spread
        comes from the decisive games — which is why a drawish match can look
        precise on paper and settle nothing.
        """
        if self.games < 2:
            return (0.0, 1.0)
        mean = self.score
        # Variance of a single game's score under the observed distribution.
        variance = (
            self.wins * (1.0 - mean) ** 2
            + self.draws * (0.5 - mean) ** 2
            + self.losses * (0.0 - mean) ** 2
        ) / self.games
        margin = z * math.sqrt(variance / self.games)
        return (max(0.0, mean - margin), min(1.0, mean + margin))

    def elo_interval(self, z: float = 1.96) -> tuple[float, float]:
        """The same interval in Elo, which is the unit the question is asked in.

        Worth reading even when the test has not decided: "somewhere between
        −5 and +60" is a real answer, and it says plainly that the bracket
        being tested sits inside the interval.
        """
        from elo.calculator import elo_diff_from_score

        low, high = self.score_interval(z)
        return (elo_diff_from_score(low), elo_diff_from_score(high))

    def diagnosis(self) -> str:
        """Why the test is still running, when it is."""
        if self.finished:
            return self.verdict.value
        low, high = self.elo_interval()
        if low <= self.config.elo0 and high >= self.config.elo1:
            return (
                f"the interval [{low:+.0f}, {high:+.0f}] still spans the whole bracket "
                f"[{self.config.elo0:+.0f}, {self.config.elo1:+.0f}] — more games"
            )
        if high < self.config.elo1 and low > self.config.elo0:
            return (
                f"the effect looks real but smaller than the bracket asks: "
                f"[{low:+.0f}, {high:+.0f}] sits under {self.config.elo1:+.0f}"
            )
        return f"interval [{low:+.0f}, {high:+.0f}], still deciding"

    def summary(self) -> str:
        low, high = self.elo_interval()
        return (
            f"{self.games} games  +{self.wins} ={self.draws} -{self.losses}  "
            f"({self.score:.1%})  LLR {self.llr:+.2f} "
            f"[{self.config.lower_bound:.2f}, {self.config.upper_bound:.2f}]  "
            f"Elo [{low:+.0f}, {high:+.0f}]  {self.verdict.value}"
        )
