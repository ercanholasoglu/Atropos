"""Shared constants: piece values, score bounds, level metadata.

All scores in this project are **centipawns** (1 pawn = 100).
"""

import chess

# --- Material -------------------------------------------------------------

PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

# Value used when scoring material *balance* — the king is always on the
# board, so counting it would only add noise.
BALANCE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# --- Score bounds ---------------------------------------------------------

# Mate is worth more than any reachable material score but stays far away
# from int overflow / infinity so `MATE_SCORE - ply` arithmetic is safe.
MATE_SCORE: int = 100_000
MATE_THRESHOLD: int = MATE_SCORE - 1_000  # scores above this are forced mates
INFINITY: int = 1_000_000

# --- Levels ---------------------------------------------------------------

INITIAL_ELO: dict[int, int] = {
    1: 200,
    2: 600,
    3: 900,
    4: 1200,
    5: 1500,
    6: 1800,
    7: 2100,
    8: 2400,
}

LEVEL_NAMES: dict[int, str] = {
    1: "Random",
    2: "Material",
    3: "Minimax",
    4: "AlphaBeta",
    5: "Positional",
    6: "Tactical",
    7: "Advanced",
    8: "Neural",
}

# Game-phase weights for tapered evaluation (used from Level 5 on).
PHASE_WEIGHTS: dict[chess.PieceType, int] = {
    chess.PAWN: 0,
    chess.KNIGHT: 1,
    chess.BISHOP: 1,
    chess.ROOK: 2,
    chess.QUEEN: 4,
    chess.KING: 0,
}
# 4 knights + 4 bishops + 4 rooks + 2 queens = 24
TOTAL_PHASE: int = 24
