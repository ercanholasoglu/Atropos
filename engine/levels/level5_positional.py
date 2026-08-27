"""Level 5 — Positional (~1500 Elo).

The first level with an opinion about anything other than material. Level 4
happily trades a knight for a knight and shuffles rooks; this one knows that
a knight on the rim is worth less than one in the centre, that a king belongs
behind its pawns until the queens come off and in the centre afterwards, and
that three pawns on one file are not three pawns' worth.

Same alpha-beta search as Level 4, one ply deeper, with:

* **piece-square tables**, separate for middlegame and endgame,
* **tapered evaluation**, blending the two by the material still on the board,
* **pawn structure** — doubled and isolated pawns are penalised,
* **the bishop pair**, worth a bonus of its own.

The evaluation costs roughly twenty times a bare material count, which is
why the search needs the pruning Level 4 introduced to afford the extra ply.
"""

from __future__ import annotations

import chess

from engine.evaluation.tapered import positional_eval
from engine.levels.search_engine import SearchEngine
from engine.search.alphabeta import search_alphabeta
from engine.search.context import RootResult, SearchStats


class Level5Positional(SearchEngine):
    level = 5
    default_name = "L5-Positional"
    depth = 5

    def __init__(self, *args, time_limit: float | None = 5.0, **kwargs) -> None:
        super().__init__(*args, time_limit=time_limit, **kwargs)

    def static_eval(self, board: chess.Board) -> int:
        return positional_eval(board)

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
