"""Common base for every level that actually searches (Level 3 upwards).

Each level differs in only two ways: how deep it looks and how it judges a
leaf. Everything else — root shuffling, the time budget, converting negamax
scores back to White's perspective, filling in ``SearchResult`` — is the
same, and lives here.
"""

from __future__ import annotations

import chess

from dataclasses import replace

from engine.base_engine import BaseEngine, SearchResult
from engine.evaluation.material import material_score, terminal_score
from engine.search.advanced import AdvancedSearch, SearchConfig
from engine.search.context import RootResult, SearchStats


class SearchEngine(BaseEngine):
    """A level driven by a root search."""

    depth: int = 1

    def __init__(self, *args, depth: int | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if depth is not None:
            self.depth = depth

    # --- evaluation -------------------------------------------------------

    def static_eval(self, board: chess.Board) -> int:
        """Leaf evaluation used *inside* the search: fast, White-relative.

        No mate or draw detection here — the search finds those itself from
        an empty move list, and paying for ``is_checkmate()`` at every leaf
        would cost more than it ever returns.
        """
        return material_score(board)

    def evaluate(self, board: chess.Board) -> float:
        """Public evaluation: static score, but honest about finished games."""
        terminal = terminal_score(board)
        if terminal is not None:
            return float(terminal)
        return float(self.static_eval(board))

    # --- search -----------------------------------------------------------

    def _root_search(
        self, board: chess.Board, stats: SearchStats, root_moves: list[chess.Move]
    ) -> RootResult:
        raise NotImplementedError

    def _report(self, result: RootResult, stats: SearchStats, board: chess.Board) -> None:
        """Hand a completed iteration to whoever asked to see them."""
        if self.on_iteration is not None:
            self.on_iteration(result, stats, board)

    def analyse(self, board: chess.Board) -> SearchResult:
        moves = list(board.legal_moves)
        if not moves:
            raise ValueError("no legal moves — the game is already over")

        # Shuffling the root before ordering leaves equally-scored moves in a
        # seed-dependent order, so two engines never replay the same game.
        self.rng.shuffle(moves)

        stats = SearchStats(
            time_limit=self.time_limit,
            node_limit=self.node_limit,
            node_limit_hard=self.node_limit_hard,
            stop_event=self.stop_event,
        )
        result = self._root_search(board, stats, moves)
        self.nodes = stats.nodes

        # RootResult.score is side-to-move relative; the public contract is
        # White-relative.
        score = result.score if board.turn == chess.WHITE else -result.score

        search_result = SearchResult(
            move=result.move,
            score=score,
            depth=result.depth,
            nodes=stats.nodes,
            time_ms=stats.elapsed_ms,
            pv=list(result.pv),
        )
        self.last_result = search_result
        return search_result

    def get_best_move(self, board: chess.Board) -> chess.Move:
        move = self.analyse(board).move
        assert move is not None  # analyse raises when there is nothing to play
        return move


class AdvancedEngine(SearchEngine):
    """A level driven by :class:`AdvancedSearch`.

    Levels 6 and 7 differ only in which techniques their ``config`` enables,
    and the searcher outlives the move: its transposition table, killers and
    history carry over from one move to the next and are cleared per game.
    """

    config: SearchConfig = SearchConfig()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.searcher = AdvancedSearch(self.static_eval, replace(self.config, max_depth=self.depth))

    def new_game(self) -> None:
        super().new_game()
        self.searcher.new_game()

    def _root_search(
        self, board: chess.Board, stats: SearchStats, root_moves: list[chess.Move]
    ) -> RootResult:
        # `self.depth` is the authority, re-read every search rather than
        # frozen into the config at construction. It used to be frozen, which
        # meant a UCI `go depth 4` was accepted and silently ignored by every
        # level from 6 up — the strongest ones, and the likeliest to be asked.
        if self.searcher.config.max_depth != self.depth:
            self.searcher.config = replace(self.searcher.config, max_depth=self.depth)
        return self.searcher.search(
            board, stats, root_moves, on_iteration=lambda r, st: self._report(r, st, board)
        )
