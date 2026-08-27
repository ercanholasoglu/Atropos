"""Alpha-beta search with iterative deepening — Level 4's engine.

Same tree as :mod:`engine.search.minimax`, same answer, a fraction of the
nodes: any line the opponent would never allow is cut off as soon as one
refutation is found. Iterative deepening pays for itself by feeding the
previous iteration's best move back in as the first move to try.
"""

from __future__ import annotations

from typing import Callable

import chess

from engine.search.context import (
    RootResult,
    SearchStats,
    SearchTimeout,
    is_draw,
    new_pv_table,
    unwind_to,
)
from engine.search.move_ordering import order_moves_basic
from engine.utils.constants import MATE_SCORE

EvalFn = Callable[[chess.Board], int]
OrderFn = Callable[[chess.Board, list[chess.Move]], list[chess.Move]]


def _static_eval(board: chess.Board, evaluate: EvalFn) -> float:
    score = float(evaluate(board))
    return score if board.turn == chess.WHITE else -score


def alphabeta(
    board: chess.Board,
    depth: int,
    ply: int,
    alpha: float,
    beta: float,
    evaluate: EvalFn,
    stats: SearchStats,
    pv_table: list[list[chess.Move]] | None = None,
    order: OrderFn = order_moves_basic,
) -> float:
    """Negamax with alpha-beta pruning; score is side-to-move relative."""
    stats.tick()

    if pv_table is not None:
        pv_table[ply] = []

    if ply > 0 and is_draw(board):
        return 0.0

    if depth <= 0:
        # See minimax.py: only positions in check pay for mate detection.
        if board.is_check() and not any(board.generate_legal_moves()):
            return -(MATE_SCORE - ply)
        return _static_eval(board, evaluate)

    moves = list(board.legal_moves)
    if not moves:
        return -(MATE_SCORE - ply) if board.is_check() else 0.0

    best = -float("inf")
    for move in order(board, moves):
        board.push(move)
        score = -alphabeta(
            board, depth - 1, ply + 1, -beta, -alpha, evaluate, stats, pv_table, order
        )
        board.pop()

        if score > best:
            best = score
            if pv_table is not None:
                pv_table[ply] = [move] + pv_table[ply + 1]
        if best > alpha:
            alpha = best
        if alpha >= beta:
            # The opponent would avoid this whole line; no need to look further.
            break
    return best


def search_alphabeta(
    board: chess.Board,
    max_depth: int,
    evaluate: EvalFn,
    stats: SearchStats | None = None,
    root_moves: list[chess.Move] | None = None,
    order: OrderFn = order_moves_basic,
    min_depth: int = 1,
    on_iteration=None,
) -> RootResult:
    """Iteratively deepen to ``max_depth``, or until the clock runs out.

    Only fully completed iterations are trusted: if the budget expires
    mid-iteration the result of the previous depth is returned unchanged.
    """
    stats = stats or SearchStats()
    moves = root_moves if root_moves is not None else list(board.legal_moves)
    if not moves:
        raise ValueError("no legal moves — the game is already over")

    best = RootResult(move=moves[0], score=0.0, depth=0, pv=[moves[0]])
    stack_depth = len(board.move_stack)

    for depth in range(min_depth, max_depth + 1):
        pv_table = new_pv_table()
        # The previous iteration's best move is the best guess available, and
        # trying it first is what makes deepening cheaper than it looks.
        ordered = order(board, moves)
        if best.move in ordered and best.depth > 0:
            ordered.remove(best.move)
            ordered.insert(0, best.move)

        iteration_move: chess.Move | None = None
        iteration_score = -float("inf")
        alpha = -float("inf")

        try:
            for move in ordered:
                board.push(move)
                score = -alphabeta(
                    board,
                    depth - 1,
                    1,
                    -float("inf"),
                    -alpha,
                    evaluate,
                    stats,
                    pv_table,
                    order,
                )
                board.pop()
                if score > iteration_score:
                    iteration_score = score
                    iteration_move = move
                    pv_table[0] = [move] + pv_table[1]
                    alpha = score
        except SearchTimeout:
            # The partial iteration is discarded: a move that only looks best
            # because its rivals were never examined is worse than nothing.
            unwind_to(board, stack_depth)
            break

        if iteration_move is not None:
            best = RootResult(
                move=iteration_move,
                score=iteration_score,
                depth=depth,
                pv=list(pv_table[0]),
            )
            if on_iteration is not None:
                # Reported per completed iteration, never mid-iteration: a
                # partial result is exactly the one that has not been checked.
                on_iteration(best, stats)

        # A forced mate is found, not improved on — stop deepening.
        if abs(best.score) >= MATE_SCORE - depth:
            break
        if stats.out_of_time():
            break

    return best
