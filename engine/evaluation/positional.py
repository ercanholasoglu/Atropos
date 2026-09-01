"""Positional terms that piece-square tables cannot express.

A PST judges a piece by where it stands; these terms judge it by what
surrounds it. Level 5 uses pawn structure and the bishop pair — the two
cheapest terms with the largest payoff. Mobility and king safety live here
too, ready for the levels that can afford them.
"""

from __future__ import annotations

import chess

# Penalties are positive numbers; they are subtracted from the owning side.
DOUBLED_PAWN_PENALTY = 15
ISOLATED_PAWN_PENALTY = 12
BISHOP_PAIR_BONUS = 30

# Files adjacent to each file, precomputed as bitboards: a pawn with no
# friendly pawn on either neighbour is isolated.
_ADJACENT_FILES: list[int] = [
    (chess.BB_FILES[f - 1] if f > 0 else 0) | (chess.BB_FILES[f + 1] if f < 7 else 0)
    for f in range(8)
]

_ALL = 0xFFFF_FFFF_FFFF_FFFF
_NOT_FILE_A = _ALL ^ chess.BB_FILE_A
_NOT_FILE_H = _ALL ^ chess.BB_FILE_H


def _north_fill(pawns: int) -> int:
    """Every square at or above a pawn, on its own file."""
    pawns |= (pawns << 8) & _ALL
    pawns |= (pawns << 16) & _ALL
    pawns |= (pawns << 32) & _ALL
    return pawns


def _file_fill(pawns: int) -> int:
    """Smear every pawn over its whole file, both directions.

    Three shifts up and three down turn a set of pawns into a set of *occupied
    files*, which replaces a loop over eight files with about ten integer
    operations — and this runs twice at every evaluated leaf.

    Only the isolated test wants this one. Using it for doubled pawns marks
    every pawn as doubled, since a full file is trivially above itself.
    """
    pawns = _north_fill(pawns)
    pawns |= pawns >> 8
    pawns |= pawns >> 16
    pawns |= pawns >> 32
    return pawns


def count_doubled_pawns(board: chess.Board, color: chess.Color) -> int:
    """Pawns standing behind a friendly pawn on the same file."""
    pawns = board.pieces_mask(chess.PAWN, color)
    doubled = 0
    for file_mask in chess.BB_FILES:
        count = chess.popcount(pawns & file_mask)
        if count > 1:
            doubled += count - 1
    return doubled


def count_isolated_pawns(board: chess.Board, color: chess.Color) -> int:
    """Pawns with no friendly pawn on either adjacent file."""
    pawns = board.pieces_mask(chess.PAWN, color)
    isolated = 0
    for file_index, file_mask in enumerate(chess.BB_FILES):
        on_file = chess.popcount(pawns & file_mask)
        if on_file and not pawns & _ADJACENT_FILES[file_index]:
            isolated += on_file
    return isolated


def has_bishop_pair(board: chess.Board, color: chess.Color) -> bool:
    return chess.popcount(board.pieces_mask(chess.BISHOP, color)) >= 2


def pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    """Structural penalty for one side (zero or negative).

    Both terms are counted in a single walk over the files — the split
    ``count_*`` helpers above exist for tests and analysis, not for the hot
    path, which runs at every evaluated leaf.
    """
    pawns = board.pieces_mask(chess.PAWN, color)
    if not pawns:
        return 0

    # A pawn with another pawn strictly below it on its file is a doubled one,
    # which comes to exactly (count - 1) per stacked file.
    doubled = chess.popcount(pawns & ((_north_fill(pawns) << 8) & _ALL))
    fill = _file_fill(pawns)
    # Neighbouring files, smeared: a pawn outside them has no friend beside it.
    neighbours = ((fill & _NOT_FILE_H) << 1) | ((fill & _NOT_FILE_A) >> 1)
    isolated = chess.popcount(pawns & ~neighbours)

    return -(DOUBLED_PAWN_PENALTY * doubled + ISOLATED_PAWN_PENALTY * isolated)


def positional_score_v2(board: chess.Board) -> int:
    """Pawn structure and bishop pair, White-relative.

    The evaluation as it stood before rooks on open files were adopted. Kept
    so the A/B record stays reproducible: every measurement in the README that
    names "v2" was taken against this.
    """
    score = pawn_structure_score(board, chess.WHITE) - pawn_structure_score(board, chess.BLACK)
    if has_bishop_pair(board, chess.WHITE):
        score += BISHOP_PAIR_BONUS
    if has_bishop_pair(board, chess.BLACK):
        score -= BISHOP_PAIR_BONUS
    return score


def positional_score(board: chess.Board) -> int:
    """Pawn structure and bishop pair.

    **The rook-on-open-file term was here and was taken out.** It went in on a
    sequential result — 318 games, +44 Elo, accepted — and a fixed-length
    re-run of 600 games measured **−2 [−26, +22]**, an interval that excludes
    the +44 the decision rested on. It does not say the term hurts; it says the
    number that justified shipping it is not supported, and the term also cost
    6.9% of throughput, worth about −18 Elo at the measured conversion.

    ``positional_score_rooks`` keeps the version with it, so every measurement
    taken under "instrument v1" stays reproducible.
    """
    return positional_score_v2(board)


def positional_score_rooks(board: chess.Board) -> int:
    """Pawn structure, bishop pair, and rooks on open files.

    The evaluation as it stood under **instrument v1**. Kept because every
    number this project recorded before the v2 cut was measured against it,
    and those numbers stay valid for the engine they measured.
    """
    from engine.evaluation.structure import rook_file_score

    return (
        positional_score_v2(board)
        + rook_file_score(board, chess.WHITE)
        - rook_file_score(board, chess.BLACK)
    )


def mobility(board: chess.Board, color: chess.Color) -> int:
    """Number of legal moves ``color`` would have if it were to move.

    Not used below Level 7: it costs a full move generation, which at a
    search leaf is more expensive than everything else in the evaluation put
    together.
    """
    if board.turn == color:
        return board.legal_moves.count()
    mirrored = board.copy(stack=False)
    mirrored.turn = color
    return mirrored.legal_moves.count()


def king_shield(board: chess.Board, color: chess.Color) -> int:
    """Friendly pawns directly in front of the king (0-3)."""
    king_square = board.king(color)
    if king_square is None:
        return 0
    pawns = board.pieces_mask(chess.PAWN, color)
    file_index = chess.square_file(king_square)
    rank_index = chess.square_rank(king_square)
    shield_rank = rank_index + 1 if color == chess.WHITE else rank_index - 1
    if not 0 <= shield_rank <= 7:
        return 0

    mask = 0
    for f in range(max(0, file_index - 1), min(7, file_index + 1) + 1):
        mask |= chess.BB_SQUARES[chess.square(f, shield_rank)]
    return chess.popcount(pawns & mask)
