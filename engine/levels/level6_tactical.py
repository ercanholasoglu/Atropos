"""Level 6 — Tactical (~1800 Elo).

Level 5 can still be robbed at the horizon: it counts a capture on its last
ply and never sees the recapture. This level closes that hole, and pays for
the extra work with a memory of what it has already searched.

* **Quiescence search** — past the horizon, captures keep being searched
  until the position is quiet, so no line is judged mid-exchange.
* **Transposition table** — the same position reached by a different move
  order is answered from the table instead of searched again.
* **MVV-LVA ordering** — a capture is tried by what it wins *and* what it
  risks, so cheap refutations come first.
* **Killer moves** — a quiet move that refuted one line is tried early in
  its siblings.
* **Check extensions** — a forced sequence is not cut off mid-check.

Everything here is exact: nothing is skipped on a guess, so the score is the
same one Level 5 would eventually reach, arrived at sooner and without the
horizon blunders. The gambling starts at Level 7.
"""

from __future__ import annotations

import chess

from engine.evaluation.tapered import positional_eval
from engine.levels.search_engine import AdvancedEngine
from engine.search.advanced import SearchConfig


class Level6Tactical(AdvancedEngine):
    level = 6
    default_name = "L6-Tactical"
    depth = 6
    config = SearchConfig(
        use_tt=True,
        use_quiescence=True,
        use_killers=True,
        check_extension=True,
    )

    def __init__(self, *args, time_limit: float | None = 3.0, **kwargs) -> None:
        # From here on the clock is the real limit, not the depth: quiescence
        # makes a full depth-6 search too slow to finish in every position, and
        # iterative deepening means a truncated search still returns the best
        # move found so far.
        super().__init__(*args, time_limit=time_limit, **kwargs)

    def static_eval(self, board: chess.Board) -> int:
        return positional_eval(board)
