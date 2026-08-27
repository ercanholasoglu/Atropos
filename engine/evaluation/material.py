"""Material evaluation — the shared base of every level from 2 upwards."""

from __future__ import annotations

import chess

from engine.utils.constants import BALANCE_VALUES, MATE_SCORE, PIECE_VALUES


def material_score(board: chess.Board) -> int:
    """Material balance in centipawns, from White's perspective.

    Counted straight off the bitboards: this runs at every leaf of every
    search, so it avoids building the ``SquareSet`` objects that the friendly
    ``board.pieces()`` API allocates.
    """
    white = board.occupied_co[chess.WHITE]
    black = board.occupied_co[chess.BLACK]
    popcount = chess.popcount
    return (
        100 * (popcount(board.pawns & white) - popcount(board.pawns & black))
        + 320 * (popcount(board.knights & white) - popcount(board.knights & black))
        + 330 * (popcount(board.bishops & white) - popcount(board.bishops & black))
        + 500 * (popcount(board.rooks & white) - popcount(board.rooks & black))
        + 900 * (popcount(board.queens & white) - popcount(board.queens & black))
    )


def piece_value(piece_type: chess.PieceType | None) -> int:
    """Centipawn value of a piece type (0 for None)."""
    return PIECE_VALUES.get(piece_type, 0) if piece_type else 0


def terminal_score(board: chess.Board, ply: int = 0) -> int | None:
    """Score for a finished position, or ``None`` if the game goes on.

    Mate scores shrink with distance so a mate in 2 is preferred over a mate
    in 5, and the result is from White's perspective.
    """
    if board.is_checkmate():
        # Side to move is mated.
        mate = -(MATE_SCORE - ply)
        return mate if board.turn == chess.WHITE else -mate
    if (
        board.is_stalemate()
        or board.is_insufficient_material()
        or board.is_seventyfive_moves()
        or board.is_fivefold_repetition()
    ):
        return 0
    return None


def evaluate_material(board: chess.Board, ply: int = 0) -> int:
    """Material evaluation with mate/draw detection, White's perspective."""
    terminal = terminal_score(board, ply)
    if terminal is not None:
        return terminal
    return material_score(board)


def capture_gain(board: chess.Board, move: chess.Move) -> int:
    """Raw material won by a move, ignoring any recapture.

    Positive for captures and promotions. This is deliberately naive — it is
    what makes Level 2 grab hanging pieces *and* walk into recaptures.
    """
    gain = 0
    if board.is_en_passant(move):
        gain += PIECE_VALUES[chess.PAWN]
    else:
        victim = board.piece_type_at(move.to_square)
        gain += piece_value(victim)
    if move.promotion:
        gain += PIECE_VALUES[move.promotion] - PIECE_VALUES[chess.PAWN]
    return gain
