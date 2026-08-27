"""Level 4 — Alpha-Beta (~1200 Elo).

Same evaluation as Level 3, one ply deeper, and roughly a hundredth of the
nodes. Three things do the work:

* **Alpha-beta pruning** — lines the opponent would never permit are cut.
* **Move ordering** — captures and promotions first, so cutoffs happen early.
* **Iterative deepening** — depth 1, 2, 3, 4 in turn, each iteration seeding
  the next one's move order with the best move found so far. It also means a
  time limit can stop the search at any point and still leave a usable move.

Depth 4 is even, so a capture at the horizon is answered by the opponent's
recapture inside the tree — the blunder Level 3 keeps walking into.
"""

from __future__ import annotations

import chess

from engine.levels.search_engine import SearchEngine
from engine.search.alphabeta import search_alphabeta
from engine.search.context import RootResult, SearchStats


class Level4AlphaBeta(SearchEngine):
    level = 4
    default_name = "L4-AlphaBeta"
    depth = 4

    def __init__(self, *args, time_limit: float | None = 5.0, **kwargs) -> None:
        # A safety valve rather than a real time control: depth 4 is fast, but
        # a wild position should not be able to stall a tournament.
        super().__init__(*args, time_limit=time_limit, **kwargs)

    def _root_search(
        self, board: chess.Board, stats: SearchStats, root_moves: list[chess.Move]
    ) -> RootResult:
        return search_alphabeta(
            board,
            max_depth=self.depth,
            evaluate=self.static_eval,
            stats=stats,
            root_moves=root_moves,
            on_iteration=lambda r, st: self._report(r, st, board),
        )
