"""Round-robin: everybody plays everybody.

The fairest format and the most expensive one — the schedule grows with the
square of the field. Every pair meets an even number of times so both sides
get White equally often.
"""

from __future__ import annotations

import itertools

from tournament.base import Pairing, Tournament


class RoundRobinTournament(Tournament):
    format = "round-robin"

    def __init__(self, *args, games_per_pair: int = 2, **kwargs) -> None:
        if games_per_pair < 1:
            raise ValueError("games_per_pair must be at least 1")
        super().__init__(*args, **kwargs)
        self.games_per_pair = games_per_pair

    def generate_pairings(self) -> list[Pairing]:
        pairings: list[Pairing] = []
        index = 0
        for round_, (a, b) in enumerate(itertools.combinations(self.engines, 2), start=1):
            for game in range(self.games_per_pair):
                # Colours alternate within a pair, so an odd games_per_pair is
                # the only way either side gets an extra White.
                white, black = (a, b) if game % 2 == 0 else (b, a)
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

    @property
    def total_games(self) -> int:
        field_size = len(self.engines)
        return field_size * (field_size - 1) // 2 * self.games_per_pair
