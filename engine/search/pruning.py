"""Forward pruning: null-move and late move reductions.

Alpha-beta is safe — it never changes the answer. Everything here is a
gamble: it skips or shortens searches on the assumption that they will not
matter, and buys depth with a small risk of missing something. Both
techniques below are standard, and both have a well-known failure mode that
the guards guard against.
"""

from __future__ import annotations

import chess

# Null move: how much shallower the verification search runs.
NULL_MOVE_REDUCTION = 2
# The verification search runs at ``depth - 1 - R``, so a minimum of 3 would
# let it bottom out at zero — a cutoff decided by quiescence alone, which is
# a gamble taken for no depth in return. Four keeps at least one real ply
# under it.
NULL_MOVE_MIN_DEPTH = NULL_MOVE_REDUCTION + 2

# Late move reductions: which moves are eligible to be cut short.
LMR_MIN_DEPTH = 3
LMR_MIN_MOVE_INDEX = 3


def has_non_pawn_material(board: chess.Board, color: chess.Color) -> bool:
    """True if ``color`` still owns a piece other than pawns and the king.

    The zugzwang guard for null-move pruning: in a king-and-pawn ending,
    "what if I did nothing?" is not a safe question — often doing nothing is
    the *best* move available, and the null-move assumption inverts.
    """
    return bool(
        board.knights & board.occupied_co[color]
        or board.bishops & board.occupied_co[color]
        or board.rooks & board.occupied_co[color]
        or board.queens & board.occupied_co[color]
    )


def can_try_null_move(board: chess.Board, depth: int, in_check: bool) -> bool:
    """Whether a null move is worth trying at this node."""
    return (
        depth >= NULL_MOVE_MIN_DEPTH and not in_check and has_non_pawn_material(board, board.turn)
    )


def lmr_reduction(depth: int, move_index: int) -> int:
    """How many plies to shave off a late, quiet move.

    Move ordering puts the moves most likely to be best up front. By the time
    the search is on the tenth quiet move of a node, the odds that it beats
    the first one are small — so search it shallow, and only pay for a full
    search if it surprises us.
    """
    if depth < LMR_MIN_DEPTH or move_index < LMR_MIN_MOVE_INDEX:
        return 0
    reduction = 1
    if move_index >= 6:
        reduction += 1
    if depth >= 6:
        reduction += 1
    # Never reduce into (or past) the quiescence boundary.
    return max(0, min(reduction, depth - 2))
