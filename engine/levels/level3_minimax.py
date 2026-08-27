"""Level 3 — Minimax (~900 Elo).

The first level that considers the opponent's reply. Plain minimax to depth
3 over the same material evaluation Level 2 uses, with no pruning: every
node in the tree gets visited. That makes it slow and it makes the search
tree easy to reason about, which is exactly what it is here for.

Depth 3 is odd, so the last move in every line is its own — it can win a
piece at the horizon and never see the recapture. Level 4 fixes that by
looking one ply further.
"""

from __future__ import annotations

import chess

from engine.levels.search_engine import SearchEngine
from engine.search.context import RootResult, SearchStats
from engine.search.minimax import search_minimax


class Level3Minimax(SearchEngine):
    level = 3
    default_name = "L3-Minimax"
    depth = 3

    def _root_search(
        self, board: chess.Board, stats: SearchStats, root_moves: list[chess.Move]
    ) -> RootResult:
        return search_minimax(
            board,
            depth=self.depth,
            evaluate=self.static_eval,
            stats=stats,
            root_moves=root_moves,
        )
