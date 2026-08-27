"""Shared tournament machinery: pairings in, standings out.

Round-robin, Swiss and gauntlet differ only in *who plays whom*. Playing the
games, keeping the table, feeding results to the rating tracker and reporting
progress are the same job every time, so they live here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Iterator

from engine.base_engine import BaseEngine
from tournament.match import DEFAULT_MAX_PLIES, GameRecord, play_game
from tournament.openings import Opening, book

# (games played so far, total games, the game just finished)
ProgressHook = Callable[[int, int, GameRecord], None]


@dataclass
class Pairing:
    """One scheduled game."""

    white: BaseEngine
    black: BaseEngine
    opening: Opening
    round_: int = 1

    @property
    def label(self) -> str:
        return f"{self.white.name} - {self.black.name}"


@dataclass
class Standing:
    """One engine's line in the table."""

    name: str
    level: int
    played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    byes: int = 0
    elo_before: float = 0.0
    elo_after: float = 0.0

    @property
    def points(self) -> float:
        # A bye is a full point in Swiss, but it is not a win over anybody, so
        # it stays out of the W-D-L record.
        return self.wins + 0.5 * self.draws + self.byes

    @property
    def score_pct(self) -> float:
        return self.points / self.played if self.played else 0.0

    @property
    def elo_change(self) -> float:
        return self.elo_after - self.elo_before

    def record(self, score: float) -> None:
        self.played += 1
        if score == 1.0:
            self.wins += 1
        elif score == 0.0:
            self.losses += 1
        else:
            self.draws += 1

    def record_bye(self) -> None:
        self.played += 1
        self.byes += 1


@dataclass
class TournamentResult:
    """Everything a finished tournament produced."""

    format: str
    games: list[GameRecord] = field(default_factory=list)
    standings: list[Standing] = field(default_factory=list)
    rounds: int = 1

    @property
    def played(self) -> int:
        return len(self.games)

    def table(self) -> str:
        header = f"{'#':<3} {'engine':<16} {'pts':>6} {'games':>6} {'W-D-L':>12} {'score':>7} {'Δelo':>7}"
        lines = [header, "-" * len(header)]
        for rank, standing in enumerate(self.standings, start=1):
            record = f"{standing.wins}-{standing.draws}-{standing.losses}"
            lines.append(
                f"{rank:<3} {standing.name:<16} {standing.points:>6.1f} "
                f"{standing.played:>6} {record:>12} {standing.score_pct:>6.1%} "
                f"{standing.elo_change:>+7.1f}"
            )
        return "\n".join(lines)


class Tournament(ABC):
    """Base class: subclasses only decide the pairings."""

    format = "tournament"

    def __init__(
        self,
        engines: list[BaseEngine],
        openings: list[Opening] | None = None,
        max_plies: int = DEFAULT_MAX_PLIES,
        tracker=None,
        on_game: ProgressHook | None = None,
        event: str | None = None,
    ) -> None:
        if len(engines) < 2:
            raise ValueError("a tournament needs at least two engines")
        self.engines = engines
        self.openings = openings if openings is not None else book()
        self.max_plies = max_plies
        self.tracker = tracker
        self.on_game = on_game
        self.event = event or self.format
        self.standings: dict[str, Standing] = {
            e.name: Standing(name=e.name, level=e.level, elo_before=e.elo, elo_after=e.elo)
            for e in engines
        }

    # --- pairings ---------------------------------------------------------

    @abstractmethod
    def generate_pairings(self) -> list[Pairing]:
        """Every game to be played, in order."""

    def rounds_of_pairings(self) -> Iterator[list[Pairing]]:
        """Pairings a round at a time.

        Fixed-schedule formats yield everything at once. Swiss overrides this
        because who plays whom in round three depends on rounds one and two.
        """
        yield self.generate_pairings()

    @property
    def total_games(self) -> int:
        """How many games the format will play, known before it starts."""
        return len(self.generate_pairings())

    def opening_for(self, index: int) -> Opening:
        return self.openings[index % len(self.openings)]

    # --- running ----------------------------------------------------------

    def run(self) -> TournamentResult:
        """Play every pairing, keeping the table and the ratings in step."""
        result = TournamentResult(format=self.format)
        total = self.total_games
        played = 0

        if self.tracker is not None:
            self.tracker.register_all(self.engines)
            for engine in self.engines:
                self.standings[engine.name].elo_before = engine.elo
                self.standings[engine.name].elo_after = engine.elo

        for round_pairings in self.rounds_of_pairings():
            for pairing in round_pairings:
                record = play_game(
                    pairing.white,
                    pairing.black,
                    start_fen=pairing.opening.fen or None,
                    max_plies=self.max_plies,
                    event=self.event,
                    round_=str(pairing.round_),
                    opening=pairing.opening.name,
                )
                result.games.append(record)
                self._apply(record, pairing)
                result.rounds = max(result.rounds, pairing.round_)

                played += 1
                if self.on_game is not None:
                    self.on_game(played, total, record)

        result.standings = sorted(
            self.standings.values(), key=lambda s: (s.points, s.score_pct), reverse=True
        )
        return result

    def _apply(self, record: GameRecord, pairing: Pairing) -> None:
        white_score = record.white_score
        self.standings[pairing.white.name].record(white_score)
        self.standings[pairing.black.name].record(1 - white_score)

        if self.tracker is not None:
            update = self.tracker.record_game(record, event=self.event)
            self.standings[pairing.white.name].elo_after = update.white_after
            self.standings[pairing.black.name].elo_after = update.black_after
            self.tracker.sync(pairing.white)
            self.tracker.sync(pairing.black)
