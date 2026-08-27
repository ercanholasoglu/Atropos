"""Plain minimax (negamax form) — no pruning at all.

This is Level 3's engine and the reference implementation the alpha-beta
search is checked against: for the same depth and evaluation the two must
return the same score, only at wildly different node counts.
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
from engine.utils.constants import MATE_SCORE

EvalFn = Callable[[chess.Board], int]


def _static_eval(board: chess.Board, evaluate: EvalFn) -> float:
    """White-relative evaluation flipped into the side-to-move's view."""
    score = float(evaluate(board))
    return score if board.turn == chess.WHITE else -score


def minimax(
    board: chess.Board,
    depth: int,
    ply: int,
    evaluate: EvalFn,
    stats: SearchStats,
    pv_table: list[list[chess.Move]] | None = None,
) -> float:
    """Search ``depth`` plies and return the score for the side to move."""
    stats.tick()

    if pv_table is not None:
        pv_table[ply] = []

    if ply > 0 and is_draw(board):
        return 0.0

    if depth <= 0:
        # Leaf. Generating moves here just to rule out mate would double the
        # cost of every leaf, so only positions in check pay for the check.
        if board.is_check() and not any(board.generate_legal_moves()):
            return -(MATE_SCORE - ply)
        return _static_eval(board, evaluate)

    moves = list(board.legal_moves)
    if not moves:
        # No legal moves: mate if in check, stalemate otherwise. Scoring mate
        # as MATE_SCORE - ply makes a quicker mate the better one.
        return -(MATE_SCORE - ply) if board.is_check() else 0.0

    best = -float("inf")
    for move in moves:
        board.push(move)
        score = -minimax(board, depth - 1, ply + 1, evaluate, stats, pv_table)
        board.pop()
        if score > best:
            best = score
            if pv_table is not None:
                pv_table[ply] = [move] + pv_table[ply + 1]
    return best


def search_minimax(
    board: chess.Board,
    depth: int,
    evaluate: EvalFn,
    stats: SearchStats | None = None,
    root_moves: list[chess.Move] | None = None,
) -> RootResult:
    """Run a fixed-depth minimax from the root.

    ``root_moves`` lets the caller decide the order the root is tried in —
    Level 3 shuffles it so self-play games are not carbon copies.
    """
    stats = stats or SearchStats()
    pv_table = new_pv_table()
    moves = root_moves if root_moves is not None else list(board.legal_moves)
    if not moves:
        raise ValueError("no legal moves — the game is already over")

    best_move = moves[0]
    best_score = -float("inf")
    stack_depth = len(board.move_stack)

    try:
        for move in moves:
            board.push(move)
            score = -minimax(board, depth - 1, 1, evaluate, stats, pv_table)
            board.pop()
            if score > best_score:
                best_score = score
                best_move = move
                pv_table[0] = [move] + pv_table[1]
    except SearchTimeout:
        # Fixed-depth search has no fallback iteration to fall back on, so it
        # keeps the best move found so far and reports the truncated depth.
        unwind_to(board, stack_depth)
        return RootResult(move=best_move, score=best_score, depth=0, pv=[best_move])

    return RootResult(move=best_move, score=best_score, depth=depth, pv=pv_table[0])
