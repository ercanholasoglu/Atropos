"""Evaluation terms that need to look at more than one square at a time.

A piece-square table judges a piece by where it stands. These terms judge it
by what surrounds it — a pawn is passed only relative to the enemy pawns, a
rook's file is open only if nobody's pawns are on it, and a king is safe only
in relation to the shelter it still has.

All of it is precomputed into bitboard masks at import. These run at every
evaluated leaf, so anything that walks squares in a loop would cost more than
the knowledge is worth.
"""

from __future__ import annotations

import chess

from engine.utils.constants import TOTAL_PHASE

# --- masks ----------------------------------------------------------------

FILE_MASKS: list[int] = list(chess.BB_FILES)

ADJACENT_FILE_MASKS: list[int] = [
    (chess.BB_FILES[f - 1] if f > 0 else 0) | (chess.BB_FILES[f + 1] if f < 7 else 0)
    for f in range(8)
]


def _forward_mask(square: chess.Square, color: chess.Color) -> int:
    """Every square ahead of ``square`` on its own and adjacent files."""
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    files = FILE_MASKS[file_index] | ADJACENT_FILE_MASKS[file_index]

    ranks = 0
    span = range(rank_index + 1, 8) if color == chess.WHITE else range(0, rank_index)
    for rank in span:
        ranks |= chess.BB_RANKS[rank]
    return files & ranks


# Indexed [colour][square]: the region an enemy pawn must occupy to stop this
# pawn from being passed.
PASSED_PAWN_MASKS: dict[chess.Color, list[int]] = {
    color: [_forward_mask(square, color) for square in range(64)]
    for color in (chess.WHITE, chess.BLACK)
}


def _king_zone(square: chess.Square) -> int:
    """The king's square and its neighbours — where an attack has to land."""
    zone = chess.BB_SQUARES[square] | chess.BB_KING_ATTACKS[square]
    return zone


KING_ZONES: list[int] = [_king_zone(square) for square in range(64)]


# --- weights --------------------------------------------------------------

# A passed pawn is worth almost nothing on the second rank and decides games
# on the seventh, so it is scored by how far it has come rather than flat.
PASSED_PAWN_BONUS_MG: tuple[int, ...] = (0, 5, 10, 20, 35, 60, 100, 0)
PASSED_PAWN_BONUS_EG: tuple[int, ...] = (0, 10, 20, 40, 70, 120, 200, 0)

# A protected passer is much harder to stop than a lone one.
PROTECTED_PASSER_BONUS = 15

ROOK_OPEN_FILE = 25
ROOK_SEMI_OPEN_FILE = 12

# King safety is a middlegame concern. With the queens gone the king wants to
# walk into the open, so these are tapered away entirely.
KING_SHIELD_BONUS = 8
KING_OPEN_FILE_PENALTY = 18
KING_ATTACKER_PENALTY = (0, 4, 12, 24, 40, 60, 80, 80, 80)


def passed_pawn_scores(board: chess.Board, color: chess.Color) -> tuple[int, int]:
    """Passed-pawn bonus as ``(middlegame, endgame)`` from a single scan.

    Both phases come out of one walk over the pawns: finding a passer is the
    expensive part and the two bonuses are only a table lookup apart, so
    scanning twice would double the cost of the term for nothing.
    """
    own_pawns = board.pieces_mask(chess.PAWN, color)
    if not own_pawns:
        return 0, 0
    enemy_pawns = board.pieces_mask(chess.PAWN, not color)

    masks = PASSED_PAWN_MASKS[color]
    white = color == chess.WHITE
    middlegame = endgame = 0
    for square in chess.scan_forward(own_pawns):
        if enemy_pawns & masks[square]:
            continue
        rank = chess.square_rank(square)
        advanced = rank if white else 7 - rank
        middlegame += PASSED_PAWN_BONUS_MG[advanced]
        endgame += PASSED_PAWN_BONUS_EG[advanced]
        # Defended by another pawn: the enemy king alone cannot deal with it.
        if chess.BB_PAWN_ATTACKS[not color][square] & own_pawns:
            middlegame += PROTECTED_PASSER_BONUS
            endgame += PROTECTED_PASSER_BONUS
    return middlegame, endgame


def passed_pawn_score(board: chess.Board, color: chess.Color, endgame: bool) -> int:
    """One phase's passed-pawn bonus. Kept for tests and analysis."""
    middlegame, endgame_score = passed_pawn_scores(board, color)
    return endgame_score if endgame else middlegame


def rook_file_score(board: chess.Board, color: chess.Color) -> int:
    """Rooks are worth more on files that pawns have left."""
    rooks = board.pieces_mask(chess.ROOK, color)
    if not rooks:
        return 0
    own_pawns = board.pieces_mask(chess.PAWN, color)
    enemy_pawns = board.pieces_mask(chess.PAWN, not color)

    score = 0
    for square in chess.scan_forward(rooks):
        file_mask = FILE_MASKS[chess.square_file(square)]
        if own_pawns & file_mask:
            continue  # blocked by its own pawn: neither open nor semi-open
        score += ROOK_OPEN_FILE if not (enemy_pawns & file_mask) else ROOK_SEMI_OPEN_FILE
    return score


def king_shelter_score(board: chess.Board, color: chess.Color) -> int:
    """What the king still has around it: pawns in front, files not open.

    The cheap half of king safety — bitboard masks and popcounts, no move
    generation. Costs about a microsecond.
    """
    king_square = board.king(color)
    if king_square is None:
        return 0

    own_pawns = board.pieces_mask(chess.PAWN, color)
    enemy_pawns = board.pieces_mask(chess.PAWN, not color)
    score = KING_SHIELD_BONUS * chess.popcount(own_pawns & KING_ZONES[king_square])

    # A file with no friendly pawn is a road to the king; one with no pawns at
    # all is a motorway.
    file_index = chess.square_file(king_square)
    for adjacent in range(max(0, file_index - 1), min(7, file_index + 1) + 1):
        file_mask = FILE_MASKS[adjacent]
        if not (own_pawns & file_mask):
            score -= (
                KING_OPEN_FILE_PENALTY
                if not (enemy_pawns & file_mask)
                else KING_OPEN_FILE_PENALTY // 2
            )
    return score


def king_attacker_score(board: chess.Board, color: chess.Color) -> int:
    """How much enemy material is aimed at the king's neighbourhood.

    The expensive half: it needs an attack map per enemy piece, which is most
    of what this whole module costs. Whether the knowledge pays for the depth
    it takes away is a question for a match, not an opinion — see
    ``scripts/eval_ab.py``.
    """
    king_square = board.king(color)
    if king_square is None:
        return 0
    zone = KING_ZONES[king_square]

    attackers = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        for square in chess.scan_forward(board.pieces_mask(piece_type, not color)):
            if board.attacks_mask(square) & zone:
                attackers += 1
    return -KING_ATTACKER_PENALTY[min(attackers, len(KING_ATTACKER_PENALTY) - 1)]


def king_safety_score(board: chess.Board, color: chess.Color) -> int:
    """Both halves of king safety, before tapering."""
    return king_shelter_score(board, color) + king_attacker_score(board, color)


# Below this phase, king safety is scaled so far down that computing it is
# paying full price for a rounding error.
KING_SAFETY_MIN_PHASE = 8


def structure_score(board: chess.Board, phase: int, king_attackers: bool = True) -> int:
    """Every term here, White-relative and already tapered.

    Passed pawns are worth more as the board empties and king safety worth
    less, so the two are blended in opposite directions by the same phase —
    and once the phase is low enough, king safety is skipped rather than
    computed and multiplied by nearly zero.
    """
    endgame_weight = (TOTAL_PHASE - phase) / TOTAL_PHASE
    middlegame_weight = phase / TOTAL_PHASE
    safety_matters = phase >= KING_SAFETY_MIN_PHASE

    score = 0.0
    for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
        middlegame_passers, endgame_passers = passed_pawn_scores(board, color)
        score += sign * (middlegame_passers * middlegame_weight + endgame_passers * endgame_weight)
        score += sign * rook_file_score(board, color)
        if safety_matters:
            safety = king_shelter_score(board, color)
            if king_attackers:
                safety += king_attacker_score(board, color)
            score += sign * safety * middlegame_weight
    return int(score)
