"""Small helpers shared across evaluation, search and the UI."""

import chess

from engine.utils.constants import MATE_SCORE, MATE_THRESHOLD, TOTAL_PHASE


def flip_square(square: chess.Square) -> chess.Square:
    """Mirror a square vertically (a1 <-> a8).

    Piece-square tables are written from White's point of view; Black looks
    them up through this mirror.
    """
    return square ^ 56


def game_phase(board: chess.Board) -> int:
    """Remaining non-pawn material as a 0..TOTAL_PHASE counter.

    24 = full opening material, 0 = bare kings and pawns. Level 5+ uses this
    to blend middlegame and endgame evaluations. Read off the bitboards
    because it runs once per evaluated leaf.

    Promotions can push the count above 24, so it is clamped: a position with
    three queens is simply "as much of an opening as material gets".
    """
    popcount = chess.popcount
    phase = (
        popcount(board.knights)
        + popcount(board.bishops)
        + 2 * popcount(board.rooks)
        + 4 * popcount(board.queens)
    )
    return min(phase, TOTAL_PHASE)


def is_endgame(board: chess.Board) -> bool:
    """True once roughly half of the non-pawn material is gone."""
    return game_phase(board) <= TOTAL_PHASE // 2


def is_mate_score(score: float) -> bool:
    return abs(score) >= MATE_THRESHOLD


def mate_in(score: float) -> int | None:
    """Number of *moves* (not plies) until mate, signed like the score."""
    if not is_mate_score(score):
        return None
    plies = MATE_SCORE - abs(score)
    moves = (int(plies) + 1) // 2
    return moves if score > 0 else -moves


def format_eval(score: float) -> str:
    """Human-readable evaluation: '+1.25', '-0.40', 'M3', '-M2'."""
    m = mate_in(score)
    if m is not None:
        return f"M{m}" if m > 0 else f"-M{abs(m)}"
    return f"{score / 100:+.2f}"


def result_to_score(result: str) -> float:
    """PGN result string -> White's score (1.0 / 0.5 / 0.0)."""
    return {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}[result]
