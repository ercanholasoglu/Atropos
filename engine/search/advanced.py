"""The full-strength search: everything Levels 6 and 7 add to alpha-beta.

One search, configured two ways. Level 6 turns on the parts that cannot lose
material — a transposition table, quiescence, killer moves, check extensions.
Level 7 adds the forward pruning that trades a little accuracy for a lot of
depth: null-move pruning, late move reductions, the history heuristic and
aspiration windows.

Keeping them in one place means the levels differ by a config object rather
than by a second copy of a subtle algorithm, and a bug fixed for one is
fixed for both.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import chess

from engine.search.context import (
    MAX_PLY,
    RootResult,
    SearchStats,
    SearchTimeout,
    is_draw,
    new_pv_table,
    unwind_to,
)
from engine.search.move_ordering import HistoryHeuristic, KillerMoves, order_moves
from engine.search.pruning import (
    NULL_MOVE_REDUCTION,
    can_try_null_move,
    lmr_reduction,
)
from engine.search.quiescence import quiescence
from engine.search.transposition import (
    EXACT,
    LOWER,
    UPPER,
    TranspositionTable,
    position_key,
)
from engine.utils.constants import MATE_SCORE, MATE_THRESHOLD

EvalFn = Callable[[chess.Board], int]

# Aspiration windows: how wide the first guess is, and how fast it widens.
ASPIRATION_WINDOW = 50
ASPIRATION_MIN_DEPTH = 4


@dataclass
class SearchConfig:
    """Which techniques a level is allowed to use."""

    max_depth: int = 6
    use_tt: bool = True
    use_quiescence: bool = True
    use_killers: bool = True
    check_extension: bool = True
    use_history: bool = False
    use_null_move: bool = False
    use_lmr: bool = False
    use_aspiration: bool = False


class AdvancedSearch:
    """A reusable search. State (table, killers, history) lives across moves."""

    def __init__(
        self,
        evaluate: EvalFn,
        config: SearchConfig | None = None,
        tt: TranspositionTable | None = None,
    ) -> None:
        self.evaluate = evaluate
        self.config = config or SearchConfig()
        self.tt = tt or (TranspositionTable() if self.config.use_tt else None)
        self.killers = KillerMoves(MAX_PLY)
        self.history = HistoryHeuristic()
        self.pv_table = new_pv_table()

    def new_game(self) -> None:
        """Forget everything learned in the previous game."""
        if self.tt is not None:
            self.tt.clear()
        self.killers.clear()
        self.history.clear()

    # --- leaf ------------------------------------------------------------

    def _static_eval(self, board: chess.Board) -> float:
        score = float(self.evaluate(board))
        return score if board.turn == chess.WHITE else -score

    def _leaf(
        self, board: chess.Board, alpha: float, beta: float, stats: SearchStats, ply: int
    ) -> float:
        if self.config.use_quiescence:
            return quiescence(board, alpha, beta, self.evaluate, stats, ply)
        if board.is_check() and not any(board.generate_legal_moves()):
            return -(MATE_SCORE - ply)
        return self._static_eval(board)

    # --- main search ------------------------------------------------------

    def _negamax(
        self,
        board: chess.Board,
        depth: int,
        ply: int,
        alpha: float,
        beta: float,
        stats: SearchStats,
        allow_null: bool = True,
    ) -> float:
        stats.tick()
        self.pv_table[ply] = []

        if ply > 0 and is_draw(board):
            return 0.0
        if ply >= MAX_PLY:
            return self._static_eval(board)

        alpha_original = alpha
        tt_move: chess.Move | None = None
        key = 0
        if self.tt is not None:
            key = position_key(board)
            if ply > 0:
                cached, tt_move = self.tt.probe(key, depth, alpha, beta, ply)
                if cached is not None:
                    return cached

        in_check = board.is_check()
        if in_check and self.config.check_extension and ply < MAX_PLY - 1:
            # A forced sequence should not be cut off mid-check just because
            # the counter ran out; give it the ply back.
            depth += 1

        if depth <= 0:
            return self._leaf(board, alpha, beta, stats, ply)

        moves = list(board.legal_moves)
        if not moves:
            return -(MATE_SCORE - ply) if in_check else 0.0

        if (
            self.config.use_null_move
            and allow_null
            and ply > 0
            and beta < MATE_THRESHOLD
            and can_try_null_move(board, depth, in_check)
        ):
            board.push(chess.Move.null())
            score = -self._negamax(
                board,
                depth - 1 - NULL_MOVE_REDUCTION,
                ply + 1,
                -beta,
                -beta + 1,
                stats,
                allow_null=False,
            )
            board.pop()
            if score >= beta:
                # Even giving the opponent a free move fails to hurt us, so
                # this node is almost certainly good enough to cut.
                return score

        killers = self.killers if self.config.use_killers else None
        history = self.history if self.config.use_history else None
        ordered = order_moves(board, moves, tt_move, killers, history, ply)

        best = -float("inf")
        best_move: chess.Move | None = None

        for index, move in enumerate(ordered):
            quiet = not board.is_capture(move) and not move.promotion
            board.push(move)

            reduction = 0
            if (
                self.config.use_lmr
                and quiet
                and not in_check
                and not board.is_check()  # the move itself gives check
            ):
                reduction = lmr_reduction(depth, index)

            if reduction:
                # Search shallow on a null window first; only a move that
                # beats alpha anyway earns the full-depth search.
                score = -self._negamax(
                    board, depth - 1 - reduction, ply + 1, -alpha - 1, -alpha, stats
                )
                if score > alpha:
                    score = -self._negamax(board, depth - 1, ply + 1, -beta, -alpha, stats)
            else:
                score = -self._negamax(board, depth - 1, ply + 1, -beta, -alpha, stats)

            board.pop()

            if score > best:
                best = score
                best_move = move
                self.pv_table[ply] = [move] + self.pv_table[ply + 1]
            if best > alpha:
                alpha = best
            if alpha >= beta:
                if quiet:
                    if killers is not None:
                        killers.store(ply, move)
                    if history is not None:
                        history.record(board.turn, move, depth)
                break

        if self.tt is not None:
            if best <= alpha_original:
                flag = UPPER
            elif best >= beta:
                flag = LOWER
            else:
                flag = EXACT
            self.tt.store(key, depth, best, flag, best_move, ply)

        return best

    # --- root -------------------------------------------------------------

    def search(
        self,
        board: chess.Board,
        stats: SearchStats,
        root_moves: list[chess.Move] | None = None,
        on_iteration=None,
    ) -> RootResult:
        """Iteratively deepen to ``config.max_depth`` or until time runs out."""
        moves = root_moves if root_moves is not None else list(board.legal_moves)
        if not moves:
            raise ValueError("no legal moves — the game is already over")

        best = RootResult(move=moves[0], score=0.0, depth=0, pv=[moves[0]])
        stack_depth = len(board.move_stack)

        for depth in range(1, self.config.max_depth + 1):
            try:
                result = self._search_root(board, depth, stats, moves, best)
            except SearchTimeout:
                unwind_to(board, stack_depth)
                break

            if result.move is not None:
                best = result
                if on_iteration is not None:
                    on_iteration(best, stats)
                # Keep the root ordered by the last iteration's opinion.
                leader = result.move
                moves = [leader] + [m for m in moves if m != leader]

            if abs(best.score) >= MATE_SCORE - depth:
                break
            if stats.out_of_time():
                break

        return best

    def _search_root(
        self,
        board: chess.Board,
        depth: int,
        stats: SearchStats,
        moves: list[chess.Move],
        previous: RootResult,
    ) -> RootResult:
        """One iteration, optionally inside an aspiration window."""
        if not (
            self.config.use_aspiration
            and depth >= ASPIRATION_MIN_DEPTH
            and previous.depth > 0
            and abs(previous.score) < MATE_THRESHOLD
        ):
            return self._root_window(board, depth, stats, moves, -float("inf"), float("inf"))

        # Assume this iteration lands near the last one and search a narrow
        # window; a guess that holds prunes far more. A miss costs a re-search.
        window = ASPIRATION_WINDOW
        while True:
            alpha = previous.score - window
            beta = previous.score + window
            result = self._root_window(board, depth, stats, moves, alpha, beta)
            if alpha < result.score < beta:
                return result
            window *= 4
            if window > 2000:
                return self._root_window(board, depth, stats, moves, -float("inf"), float("inf"))

    def _root_window(
        self,
        board: chess.Board,
        depth: int,
        stats: SearchStats,
        moves: list[chess.Move],
        alpha: float,
        beta: float,
    ) -> RootResult:
        best_move: chess.Move | None = None
        best_score = -float("inf")

        for move in moves:
            board.push(move)
            score = -self._negamax(board, depth - 1, 1, -beta, -max(alpha, best_score), stats)
            board.pop()
            if score > best_score:
                best_score = score
                best_move = move
                self.pv_table[0] = [move] + self.pv_table[1]

        return RootResult(
            move=best_move,
            score=best_score,
            depth=depth,
            pv=list(self.pv_table[0]) if best_move else [],
        )
