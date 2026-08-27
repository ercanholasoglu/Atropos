"""Quiescence search — the cure for the horizon effect.

A fixed-depth search stops wherever the counter runs out, which may be
halfway through a queen trade. It then evaluates that position as if the
board were settled, and reports a queen up. Quiescence keeps going past the
horizon, but only along captures, until the position is quiet enough for a
static evaluation to mean something.

Two things keep it from exploding:

* **Stand pat** — the side to move is never obliged to capture, so the static
  score is a lower bound. If it already beats beta, the node is done.
* **Delta pruning** — a capture that cannot possibly drag the score up to
  alpha, even generously, is not searched at all.
"""

from __future__ import annotations

from typing import Callable

import chess

from engine.search.context import SearchStats
from engine.search.move_ordering import order_loud_moves
from engine.utils.constants import MATE_SCORE, PIECE_VALUES

EvalFn = Callable[[chess.Board], int]

# How much a capture is allowed to be worth beyond the material it wins
# before delta pruning stops believing it can rescue the position.
DELTA_MARGIN = 200

# Captures can chain a long way; this stops a pathological position from
# running forever.
MAX_QUIESCENCE_PLY = 8


def _static_eval(board: chess.Board, evaluate: EvalFn) -> float:
    score = float(evaluate(board))
    return score if board.turn == chess.WHITE else -score


def _captured_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return PIECE_VALUES[chess.PAWN]
    victim = board.piece_type_at(move.to_square)
    value = PIECE_VALUES[victim] if victim else 0
    if move.promotion:
        value += PIECE_VALUES[move.promotion] - PIECE_VALUES[chess.PAWN]
    return value


def quiescence(
    board: chess.Board,
    alpha: float,
    beta: float,
    evaluate: EvalFn,
    stats: SearchStats,
    ply: int,
    qply: int = 0,
) -> float:
    """Search captures until the position is quiet; side-to-move relative."""
    stats.tick()

    in_check = board.is_check()

    if in_check:
        # Standing pat while in check would evaluate a position the side to
        # move is not allowed to keep, so every evasion gets searched.
        moves = list(board.legal_moves)
        if not moves:
            return -(MATE_SCORE - ply)
        if qply >= MAX_QUIESCENCE_PLY:
            return _static_eval(board, evaluate)
    else:
        stand_pat = _static_eval(board, evaluate)
        if stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat
        if qply >= MAX_QUIESCENCE_PLY:
            return stand_pat
        moves = order_loud_moves(board)
        if not moves:
            return stand_pat

    best = -float("inf") if in_check else stand_pat

    for move in moves:
        if not in_check:
            # Delta pruning: even winning this piece outright would leave the
            # score short of alpha, so the line cannot matter.
            if stand_pat + _captured_value(board, move) + DELTA_MARGIN < alpha:
                continue

        board.push(move)
        score = -quiescence(board, -beta, -alpha, evaluate, stats, ply + 1, qply + 1)
        board.pop()

        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break

    return best
