"""Piece-square tables.

Each table is written the way a board looks from White's side: index 0 is
a8, index 63 is h1. python-chess numbers squares the other way up (0 = a1),
so lookups go through a vertical mirror — White reads ``table[square ^ 56]``
and Black reads ``table[square]``.

Middlegame tables are the classic Simplified Evaluation Function set. Only
the pawn and king tables get a separate endgame version, because they are
where the phase actually changes the answer: a king that must hide behind
its pawns in the middlegame must march to the centre in the endgame, and a
pawn on the sixth rank is worth far more once the queens are gone. The
minor and major pieces reuse their middlegame tables, which already reward
centralisation in both phases.

Tables are folded together with the piece values at import time, so one
lookup per piece covers both material and placement.
"""

from __future__ import annotations

import chess

from engine.utils.constants import PIECE_VALUES

# fmt: off
PAWN_MG = [
      0,   0,   0,   0,   0,   0,   0,   0,
     50,  50,  50,  50,  50,  50,  50,  50,
     10,  10,  20,  30,  30,  20,  10,  10,
      5,   5,  10,  25,  25,  10,   5,   5,
      0,   0,   0,  20,  20,   0,   0,   0,
      5,  -5, -10,   0,   0, -10,  -5,   5,
      5,  10,  10, -20, -20,  10,  10,   5,
      0,   0,   0,   0,   0,   0,   0,   0,
]

PAWN_EG = [
      0,   0,   0,   0,   0,   0,   0,   0,
     80,  80,  80,  80,  80,  80,  80,  80,
     50,  50,  50,  50,  50,  50,  50,  50,
     30,  30,  30,  30,  30,  30,  30,  30,
     20,  20,  20,  20,  20,  20,  20,  20,
     10,  10,  10,  10,  10,  10,  10,  10,
     10,  10,  10,  10,  10,  10,  10,  10,
      0,   0,   0,   0,   0,   0,   0,   0,
]

KNIGHT_MG = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20,   0,   0,   0,   0, -20, -40,
    -30,   0,  10,  15,  15,  10,   0, -30,
    -30,   5,  15,  20,  20,  15,   5, -30,
    -30,   0,  15,  20,  20,  15,   0, -30,
    -30,   5,  10,  15,  15,  10,   5, -30,
    -40, -20,   0,   5,   5,   0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]

BISHOP_MG = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]

ROOK_MG = [
      0,   0,   0,   0,   0,   0,   0,   0,
      5,  10,  10,  10,  10,  10,  10,   5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
      0,   0,   0,   5,   5,   0,   0,   0,
]

# The widely-copied version of this table is very slightly lopsided — three
# of its rows do not mirror left to right, which is a transcription wart in
# the original rather than a chess idea. Symmetrised here, because a queen on
# c3 and a queen on f3 are worth the same and a test says so.
QUEEN_MG = [
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
     -5,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   5, -10,
    -10,   0,   5,   0,   0,   5,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20,
]

KING_MG = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20,
]

KING_EG = [
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10,   0,   0, -10, -20, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -30,   0,   0,   0,   0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
]
# fmt: on

RAW_MG: dict[chess.PieceType, list[int]] = {
    chess.PAWN: PAWN_MG,
    chess.KNIGHT: KNIGHT_MG,
    chess.BISHOP: BISHOP_MG,
    chess.ROOK: ROOK_MG,
    chess.QUEEN: QUEEN_MG,
    chess.KING: KING_MG,
}

RAW_EG: dict[chess.PieceType, list[int]] = {
    **RAW_MG,
    chess.PAWN: PAWN_EG,
    chess.KING: KING_EG,
}

# The king's nominal 20000 would swamp everything; it is on both sides of
# every position, so only its placement matters here.
_TABLE_VALUES = {**PIECE_VALUES, chess.KING: 0}


def _fold(table: list[int], piece_type: chess.PieceType, color: chess.Color) -> list[int]:
    """Piece value + placement bonus, indexed by python-chess square."""
    value = _TABLE_VALUES[piece_type]
    if color == chess.WHITE:
        return [value + table[square ^ 56] for square in range(64)]
    return [value + table[square] for square in range(64)]


MG_TABLES: dict[chess.Color, dict[chess.PieceType, list[int]]] = {
    color: {pt: _fold(table, pt, color) for pt, table in RAW_MG.items()}
    for color in (chess.WHITE, chess.BLACK)
}

EG_TABLES: dict[chess.Color, dict[chess.PieceType, list[int]]] = {
    color: {pt: _fold(table, pt, color) for pt, table in RAW_EG.items()}
    for color in (chess.WHITE, chess.BLACK)
}


def _piece_bitboards(board: chess.Board) -> tuple[tuple[chess.PieceType, int], ...]:
    """The board's six piece bitboards, read straight off the attributes."""
    return (
        (chess.PAWN, board.pawns),
        (chess.KNIGHT, board.knights),
        (chess.BISHOP, board.bishops),
        (chess.ROOK, board.rooks),
        (chess.QUEEN, board.queens),
        (chess.KING, board.kings),
    )


def pst_scores(board: chess.Board) -> tuple[int, int]:
    """Material + placement as a ``(middlegame, endgame)`` pair.

    Both numbers are White-relative. They are collected in one pass so the
    tapered evaluation can blend them without walking the board twice.
    """
    mg = 0
    eg = 0
    scan = chess.scan_forward
    mg_white, mg_black = MG_TABLES[chess.WHITE], MG_TABLES[chess.BLACK]
    eg_white, eg_black = EG_TABLES[chess.WHITE], EG_TABLES[chess.BLACK]
    white_pieces = board.occupied_co[chess.WHITE]
    black_pieces = board.occupied_co[chess.BLACK]

    for piece_type, pieces in _piece_bitboards(board):
        if not pieces:
            continue
        mg_table = mg_white[piece_type]
        eg_table = eg_white[piece_type]
        for square in scan(pieces & white_pieces):
            mg += mg_table[square]
            eg += eg_table[square]
        mg_table = mg_black[piece_type]
        eg_table = eg_black[piece_type]
        for square in scan(pieces & black_pieces):
            mg -= mg_table[square]
            eg -= eg_table[square]
    return mg, eg


def pst_value(piece: chess.Piece, square: chess.Square, endgame: bool = False) -> int:
    """Placement bonus for one piece, without its material value."""
    table = RAW_EG[piece.piece_type] if endgame else RAW_MG[piece.piece_type]
    return table[square ^ 56] if piece.color == chess.WHITE else table[square]
