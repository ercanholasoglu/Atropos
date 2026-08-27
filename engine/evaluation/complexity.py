"""How much is this position worth thinking about?

Not every position deserves the same effort. A rook up in a locked endgame
is decided; a middlegame with three hanging pieces is not. Estimating that
cheaply lets the levels above spend their clock where it changes the answer
— Level 8 uses it to stretch or shrink its time budget, and the tiered
evaluator in ``research/hybrid_eval`` uses it to route between evaluators.

The strongest of the signals below is the gap between the static evaluation
and what a quiescence search says. If those two agree the position is quiet
almost by definition, and no amount of extra thinking will move it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import chess

from engine.evaluation.material import capture_gain
from engine.search.context import SearchStats
from engine.search.quiescence import quiescence
from engine.utils.constants import TOTAL_PHASE
from engine.utils.helpers import game_phase

EvalFn = Callable[[chess.Board], int]


@dataclass
class ComplexitySignals:
    """Why a position was judged hard, not just how hard."""

    legal_moves: int
    captures: int
    in_check: bool
    hanging_material: int
    phase: float
    tactical_gap: int
    score: float

    def explain(self) -> str:
        return (
            f"complexity {self.score:.2f} — {self.legal_moves} moves, "
            f"{self.captures} captures, {self.hanging_material}cp hanging, "
            f"tactical gap {self.tactical_gap}cp" + (", in check" if self.in_check else "")
        )


def estimate_complexity(
    board: chess.Board, evaluate: EvalFn, tactical_probe: bool = True
) -> ComplexitySignals:
    """Score a position 0 (trivial) to 1 (sharp).

    ``tactical_probe`` runs a quiescence search, which is the strongest of
    these signals and also the most expensive. It is worth its cost at the
    root of a search and not at a leaf, so it can be turned off.
    """
    moves = list(board.legal_moves)
    if not moves:
        # Checkmate or stalemate: the least complex position there is. Without
        # this the quiescence probe reports a mate-sized "tactical gap" and
        # routes a finished game to the most expensive tier there is.
        return ComplexitySignals(
            legal_moves=0,
            captures=0,
            in_check=board.is_check(),
            hanging_material=0,
            phase=game_phase(board) / TOTAL_PHASE,
            tactical_gap=0,
            score=0.0,
        )

    captures = [move for move in moves if board.is_capture(move) or move.promotion]
    hanging = max((capture_gain(board, move) for move in captures), default=0)
    phase = game_phase(board) / TOTAL_PHASE
    in_check = board.is_check()

    tactical_gap = 0
    if tactical_probe and (captures or in_check):
        static = evaluate(board)
        stats = SearchStats()
        settled = quiescence(board, -1e9, 1e9, evaluate, stats, ply=0)
        # quiescence works from the side to move; bring it back to White's view.
        settled_white = settled if board.turn == chess.WHITE else -settled
        tactical_gap = int(abs(settled_white - static))

    # Each term saturates: past a point, more of it does not make a position
    # meaningfully harder, and a raw sum would let one signal dominate.
    branching = min(len(moves) / 40.0, 1.0)
    capture_pressure = min(len(captures) / 8.0, 1.0)
    hanging_pressure = min(hanging / 500.0, 1.0)
    gap_pressure = min(tactical_gap / 300.0, 1.0)

    score = (
        0.15 * branching
        + 0.15 * capture_pressure
        + 0.20 * hanging_pressure
        + 0.35 * gap_pressure
        + 0.10 * phase
        + 0.05 * float(in_check)
    )
    return ComplexitySignals(
        legal_moves=len(moves),
        captures=len(captures),
        in_check=in_check,
        hanging_material=hanging,
        phase=phase,
        tactical_gap=tactical_gap,
        score=min(score, 1.0),
    )
