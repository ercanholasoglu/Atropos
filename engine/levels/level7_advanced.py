"""Level 7 — Advanced (~2100 Elo).

Same evaluation as Level 6, same clock — and several plies deeper, because
this level is willing to guess. Everything Level 6 does is exact; everything
added here trades a small risk of missing something for a much smaller tree.

* **Null-move pruning** — "if I skip my turn and the position still beats
  beta, I do not need to search it properly." Disabled when the side to move
  has only pawns, where doing nothing can genuinely be best.
* **Late move reductions** — by the tenth quiet move at a node, the odds of
  a surprise are low; search it shallow and only re-search if it beats alpha.
* **History heuristic** — quiet moves that caused cutoffs anywhere in the
  tree get tried earlier, which is what makes reductions safe to apply.
* **Aspiration windows** — the score rarely moves far between iterations, so
  each one starts inside a narrow window around the last.

Together they buy roughly two extra plies at the same time control, which is
where the rating difference comes from.
"""

from __future__ import annotations

import chess

from engine.evaluation.tapered import positional_eval
from engine.levels.search_engine import AdvancedEngine
from engine.search.advanced import SearchConfig


class Level7Advanced(AdvancedEngine):
    level = 7
    default_name = "L7-Advanced"
    depth = 8
    config = SearchConfig(
        use_tt=True,
        use_quiescence=True,
        use_killers=True,
        check_extension=True,
        use_history=True,
        use_null_move=True,
        use_lmr=True,
        use_aspiration=True,
    )

    def __init__(self, *args, time_limit: float | None = 3.0, **kwargs) -> None:
        super().__init__(*args, time_limit=time_limit, **kwargs)

    def static_eval(self, board: chess.Board) -> int:
        return positional_eval(board)
