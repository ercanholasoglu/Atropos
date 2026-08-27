"""Position features shared by every research module.

Three modules want to *learn* an evaluation rather than hand-write one, and
they all need the same thing first: a position turned into numbers. Building
that once means TD(λ), the parameter tuner and the NNUE search all optimise
over the same representation, and their results can be compared directly.

Two encodings live here:

* **Piece-square features** (384) — one entry per piece type and square,
  counting White's pieces there minus Black's on the mirrored square. A
  linear model over this vector *is* a piece-square table, which makes it the
  natural thing for TD(λ) to learn and the natural input to a small NNUE.
* **Handcrafted features** (8) — the interpretable terms the engine's own
  evaluation already uses. Small enough that a parameter search can cover it
  within a realistic self-play budget.

The 768-wide "one plane per piece and colour" encoding is also here, since
that is the classic NNUE input and the ablation baseline.
"""

from __future__ import annotations

import chess
import numpy as np

from engine.evaluation.positional import (
    count_doubled_pawns,
    count_isolated_pawns,
    has_bishop_pair,
)
from engine.utils.constants import TOTAL_PHASE
from engine.utils.helpers import game_phase

PIECE_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)

# 6 piece types x 64 squares, colour folded in by mirroring.
PIECE_SQUARE_DIM = len(PIECE_TYPES) * 64  # 384
# 12 planes x 64 squares, colours kept apart — the classic NNUE input.
FULL_PLANE_DIM = 2 * PIECE_SQUARE_DIM  # 768

HANDCRAFTED_NAMES = (
    "pawns",
    "knights",
    "bishops",
    "rooks",
    "queens",
    "doubled_pawns",
    "isolated_pawns",
    "bishop_pair",
)
HANDCRAFTED_DIM = len(HANDCRAFTED_NAMES)


def piece_square_vector(board: chess.Board) -> np.ndarray:
    """384 features, White-relative.

    Entry ``(piece_type, square)`` is +1 for each White piece of that type on
    that square and −1 for each Black one on the vertically mirrored square.
    A weight vector over this is exactly a piece-square table read from
    White's side, so the engine's own tables can be dropped in as a starting
    point — or checked against something learned from scratch.
    """
    vector = np.zeros(PIECE_SQUARE_DIM, dtype=np.float32)
    scan = chess.scan_forward
    white = board.occupied_co[chess.WHITE]
    black = board.occupied_co[chess.BLACK]

    for index, piece_type in enumerate(PIECE_TYPES):
        base = index * 64
        pieces = board.pieces_mask(piece_type, chess.WHITE) & white
        for square in scan(pieces):
            vector[base + square] += 1.0
        pieces = board.pieces_mask(piece_type, chess.BLACK) & black
        for square in scan(pieces):
            vector[base + (square ^ 56)] -= 1.0
    return vector


def full_plane_vector(board: chess.Board) -> np.ndarray:
    """768 features: a plane per piece type and colour, no folding.

    Strictly more expressive than the folded version — it can learn that a
    White knight on e4 is worth something different from a Black knight on
    e5 — and strictly more parameters to fit. The ablation in
    ``minimal_nnue`` is largely about whether that freedom is worth paying
    for at this scale.
    """
    vector = np.zeros(FULL_PLANE_DIM, dtype=np.float32)
    scan = chess.scan_forward
    for index, piece_type in enumerate(PIECE_TYPES):
        for colour_offset, colour in ((0, chess.WHITE), (PIECE_SQUARE_DIM, chess.BLACK)):
            base = colour_offset + index * 64
            for square in scan(board.pieces_mask(piece_type, colour)):
                vector[base + square] = 1.0
    return vector


def handcrafted_vector(board: chess.Board) -> np.ndarray:
    """8 interpretable features, White-relative and unweighted.

    Multiplying by a parameter vector reproduces the engine's own evaluation
    terms, which is what lets the tuner start from the hand-written values
    rather than from noise.
    """
    popcount = chess.popcount
    white = board.occupied_co[chess.WHITE]
    black = board.occupied_co[chess.BLACK]

    def difference(mask: int) -> float:
        return float(popcount(mask & white) - popcount(mask & black))

    return np.array(
        [
            difference(board.pawns),
            difference(board.knights),
            difference(board.bishops),
            difference(board.rooks),
            difference(board.queens),
            # Penalties are counted positive here; their weights carry the sign.
            float(
                count_doubled_pawns(board, chess.WHITE) - count_doubled_pawns(board, chess.BLACK)
            ),
            float(
                count_isolated_pawns(board, chess.WHITE) - count_isolated_pawns(board, chess.BLACK)
            ),
            float(has_bishop_pair(board, chess.WHITE)) - float(has_bishop_pair(board, chess.BLACK)),
        ],
        dtype=np.float32,
    )


def phase_scalar(board: chess.Board) -> float:
    """Game phase as 1.0 (opening) down to 0.0 (bare kings)."""
    return game_phase(board) / TOTAL_PHASE


def pst_weights(endgame: bool = False, include_material: bool = True) -> np.ndarray:
    """The engine's own tables as a 384-vector, for use as a starting point.

    ``piece_square_vector(board) @ pst_weights()`` reproduces the middlegame
    half of ``pst_scores`` exactly — a test asserts it. Anything learned can
    therefore be compared against a known-good baseline in the same units.
    """
    from engine.evaluation.pst import RAW_EG, RAW_MG
    from engine.utils.constants import PIECE_VALUES

    tables = RAW_EG if endgame else RAW_MG
    weights = np.zeros(PIECE_SQUARE_DIM, dtype=np.float32)
    for index, piece_type in enumerate(PIECE_TYPES):
        value = 0 if piece_type == chess.KING or not include_material else PIECE_VALUES[piece_type]
        table = tables[piece_type]
        for square in range(64):
            weights[index * 64 + square] = value + table[square ^ 56]
    return weights
