"""Level 8 — Adaptive (~2400 Elo target).

Levels 1 to 7 all spend the same effort on every position. This one decides
how hard a position is before it starts, and spends accordingly.

**Where the tiering can actually go.** The obvious reading of "hybrid
evaluation" is to route each *leaf* to a cheap or expensive evaluator. That
does not survive contact with the numbers: a leaf evaluation costs about six
microseconds, a complexity estimate that includes a quiescence probe costs
tens of microseconds, and a language model costs seconds. Deciding per leaf
would cost more than the decision saves, and calling a model per leaf is off
by six orders of magnitude. So the routing happens once, at the root, where
a millisecond of thought can redirect seconds of search:

* **Adaptive time management** — a sharp position with hanging pieces and a
  large gap between the static and quiescence scores gets up to twice the
  clock; a locked or already-decided one gets half, and the saved time goes
  back into the game.
* **An optional language-model advisor** — consulted only when the engine's
  own top two moves are within a hair of each other *and* the position is
  complex *and* the clock allows. It is a tie-breaker between candidates the
  search has already vetted, never a calculator: the search knows the
  variations, the model may know which resulting structure is easier to play.

The learned evaluator this level is eventually meant to carry is not trained
yet; until it is, the leaf evaluation is Level 7's and the gain over Level 7
is the time management alone. ``static_eval`` is the hook it will slot into.
"""

from __future__ import annotations

from dataclasses import replace

import chess

from engine.base_engine import SearchResult
from engine.evaluation.complexity import ComplexitySignals, estimate_complexity
from engine.evaluation.tapered import positional_eval
from engine.levels.search_engine import AdvancedEngine
from engine.search.advanced import SearchConfig
from engine.search.context import RootResult, SearchStats

# How far the clock may stretch or shrink around the nominal budget.
MIN_TIME_FACTOR = 0.5
MAX_TIME_FACTOR = 2.0

# Two root moves closer than this are, as far as the search is concerned, the
# same move — which is exactly when a second opinion is worth having.
ADVISOR_MARGIN_CP = 30


class Level8Neural(AdvancedEngine):
    level = 8
    default_name = "L8-Adaptive"
    depth = 9
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

    def __init__(
        self,
        *args,
        time_limit: float | None = 3.0,
        adaptive_time: bool = True,
        evaluator=None,
        advisor=None,
        **kwargs,
    ) -> None:
        super().__init__(*args, time_limit=time_limit, **kwargs)
        self.adaptive_time = adaptive_time
        # A learned evaluator, once there is one; the classical evaluation
        # until then.
        self.evaluator = evaluator
        self.advisor = advisor
        self.last_complexity: ComplexitySignals | None = None
        self.last_time_factor = 1.0
        self.advisor_calls = 0

    def static_eval(self, board: chess.Board) -> int:
        if self.evaluator is not None:
            return int(self.evaluator(board))
        return positional_eval(board)

    # --- adaptive budget --------------------------------------------------

    def time_for(self, board: chess.Board) -> float | None:
        """Stretch or shrink the clock according to how sharp the position is."""
        if self.time_limit is None or not self.adaptive_time:
            return self.time_limit

        signals = estimate_complexity(board, self.static_eval)
        self.last_complexity = signals
        factor = MIN_TIME_FACTOR + (MAX_TIME_FACTOR - MIN_TIME_FACTOR) * signals.score
        self.last_time_factor = factor
        return self.time_limit * factor

    def _root_search(
        self, board: chess.Board, stats: SearchStats, root_moves: list[chess.Move]
    ) -> RootResult:
        stats.time_limit = self.time_for(board)
        if self.searcher.config.max_depth != self.depth:
            self.searcher.config = replace(self.searcher.config, max_depth=self.depth)
        return self.searcher.search(
            board, stats, root_moves, on_iteration=lambda r, st: self._report(r, st, board)
        )

    # --- optional second opinion -----------------------------------------

    def analyse(self, board: chess.Board) -> SearchResult:
        result = super().analyse(board)
        if self.advisor is not None and self._worth_asking(board, result):
            chosen = self.advisor.choose(board, result)
            if chosen is not None and chosen in board.legal_moves:
                self.advisor_calls += 1
                result.move = chosen
                self.last_result = result
        return result

    def _worth_asking(self, board: chess.Board, result: SearchResult) -> bool:
        """Only when the search itself is undecided and the position is sharp."""
        if self.last_complexity is None or self.last_complexity.score < 0.5:
            return False
        return self._root_margin(board, result) < ADVISOR_MARGIN_CP

    def _root_margin(self, board: chess.Board, result: SearchResult) -> float:
        """How far ahead the best root move is, in centipawns.

        Read out of the transposition table rather than re-searched: the root's
        children were all just scored, and asking again would double the cost
        of every move for a number that is already known.
        """
        if result.move is None or self.searcher.tt is None:
            return float("inf")

        from engine.search.transposition import position_key

        scores = []
        for move in board.legal_moves:
            board.push(move)
            entry = self.searcher.tt.lookup(position_key(board))
            board.pop()
            if entry is not None:
                scores.append(-entry.score)
        if len(scores) < 2:
            return float("inf")
        scores.sort(reverse=True)
        return float(scores[0] - scores[1])
