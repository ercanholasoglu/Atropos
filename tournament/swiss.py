"""Swiss system: pair the leaders with the leaders.

A round-robin over eight engines is 28 pairings; a Swiss gets a usable
ranking out of five rounds because nobody wastes games on opponents far from
their own level. Each round pairs engines on similar scores, avoids repeat
pairings while it can, and evens out the colours.
"""

from __future__ import annotations

from typing import Iterator

from engine.base_engine import BaseEngine
from tournament.base import Pairing, Tournament


class SwissTournament(Tournament):
    format = "swiss"

    def __init__(self, *args, rounds: int = 5, **kwargs) -> None:
        if rounds < 1:
            raise ValueError("a Swiss tournament needs at least one round")
        super().__init__(*args, **kwargs)
        self.rounds = rounds
        self.met: set[frozenset[str]] = set()
        # Colour bookkeeping: the running White-minus-Black balance, and who
        # played what last, so colours can alternate as well as even out.
        self.balance: dict[str, int] = {e.name: 0 for e in self.engines}
        self.last_colour: dict[str, str] = {}
        self.byes: set[str] = set()

    @property
    def total_games(self) -> int:
        return self.rounds * (len(self.engines) // 2)

    def generate_pairings(self) -> list[Pairing]:
        """The next round's pairings, from the standings so far."""
        return self._pair_round(round_=1, opening_index=0)

    def rounds_of_pairings(self) -> Iterator[list[Pairing]]:
        opening_index = 0
        for round_ in range(1, self.rounds + 1):
            pairings = self._pair_round(round_, opening_index)
            opening_index += len(pairings)
            yield pairings

    # --- pairing ----------------------------------------------------------

    def _pair_round(self, round_: int, opening_index: int) -> list[Pairing]:
        order = sorted(
            self.engines,
            key=lambda e: (self.standings[e.name].points, e.elo),
            reverse=True,
        )
        unpaired = list(order)
        pairings: list[Pairing] = []

        while len(unpaired) >= 2:
            first = unpaired.pop(0)
            index = self._pick_opponent(first, unpaired)
            second = unpaired.pop(index)

            white, black = self._assign_colours(first, second)
            self.met.add(frozenset({first.name, second.name}))
            self.balance[white.name] += 1
            self.balance[black.name] -= 1
            self.last_colour[white.name] = "white"
            self.last_colour[black.name] = "black"
            pairings.append(
                Pairing(
                    white=white,
                    black=black,
                    opening=self.opening_for(opening_index + len(pairings)),
                    round_=round_,
                )
            )

        if unpaired:
            # Odd field: the lowest-scoring engine that has not had one yet
            # sits out for a free point.
            self._give_bye(unpaired[0])

        return pairings

    def _pick_opponent(self, engine: BaseEngine, candidates: list[BaseEngine]) -> int:
        """The nearest score who has not been played yet, else the nearest."""
        for index, candidate in enumerate(candidates):
            if frozenset({engine.name, candidate.name}) not in self.met:
                return index
        return 0

    def _assign_colours(
        self, first: BaseEngine, second: BaseEngine
    ) -> tuple[BaseEngine, BaseEngine]:
        """Give White to whoever is owed it.

        Counting raw Whites is not enough — it lets an engine take White
        again on a tie and drift two games ahead. The balance decides first,
        and when that is level, whoever played Black last alternates in.
        """
        if self.balance[first.name] != self.balance[second.name]:
            return (
                (first, second)
                if self.balance[first.name] < self.balance[second.name]
                else (second, first)
            )
        if self.last_colour.get(first.name) == "black":
            return first, second
        if self.last_colour.get(second.name) == "black":
            return second, first
        return first, second

    def _give_bye(self, engine: BaseEngine) -> None:
        candidate = engine
        if candidate.name in self.byes:
            # Already had one; hand it to the next engine that has not.
            for other in reversed(self.engines):
                if other.name not in self.byes:
                    candidate = other
                    break
        self.byes.add(candidate.name)
        self.standings[candidate.name].record_bye()
