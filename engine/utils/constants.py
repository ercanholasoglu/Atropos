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

# What each level was *aiming at*, assigned at construction. These are a
# specification, not a measurement, and nothing ever verified them — see
# MEASURED_ELO below and docs/RATING_FIT.md. They stay because every rating
# this project computed before the ladder was measured used them, and changing
# them would silently rewrite those records.
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

# What the levels actually are, from a joint maximum-likelihood fit over every
# game recorded at 0.1s per move (`scripts/rating_fit.py`, 4,704 games at
# the time of writing, all from fixed-length matches). Each entry is
# ``(rating, standard error)``.
#
# **The scale has no absolute zero.** Level 7 is held at its nominal 2100 as a
# gauge so the column is readable; only the *differences* between entries are
# measured. Placing the whole scale against an outside reference needs a rated
# engine at a rated time control — see docs/ANCHOR.md.
#
# The gaps these imply are 423, 682, 407, 178, 637, 18 and -32,
# against the 400-then-six-300s the names above assert. Re-run
# `scripts/rating_fit.py` after adding games and update this table; a test
# asserts the two still agree.
MEASURED_ELO: dict[int, tuple[int, int]] = {
    1: (-245, 78),
    2: (178, 75),
    3: (860, 66),
    4: (1267, 59),
    5: (1445, 55),
    6: (2082, 18),
    7: (2100, 0),  # the gauge; its error is zero by construction, not by measurement
    8: (2068, 22),
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
