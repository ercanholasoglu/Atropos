"""Tapered evaluation: blending the middlegame and endgame scores.

A single evaluation cannot be right in both phases — the king wants shelter
with queens on and activity with them off, and a passed pawn is a detail in
the opening and the whole game in a rook ending. Rather than switching
tables at some arbitrary moment (which makes the score jump the instant a
piece is traded), both scores are computed and mixed in proportion to the
material still on the board.
"""

from __future__ import annotations

import chess

from engine.evaluation.positional import positional_score
from engine.evaluation.pst import pst_scores
from engine.utils.constants import TOTAL_PHASE
from engine.utils.helpers import game_phase


def taper(middlegame: int, endgame: int, phase: int) -> int:
    """Blend two scores; ``phase`` runs from TOTAL_PHASE (opening) to 0."""
    phase = max(0, min(phase, TOTAL_PHASE))
    return (middlegame * phase + endgame * (TOTAL_PHASE - phase)) // TOTAL_PHASE


def tapered_pst(board: chess.Board) -> int:
    """Material and placement, phase-blended, White-relative."""
    middlegame, endgame = pst_scores(board)
    return taper(middlegame, endgame, game_phase(board))


def positional_eval(board: chess.Board) -> int:
    """The evaluation Levels 5 through 8 share.

    Tapered material and placement, plus the structural terms a piece-square
    table cannot see. Levels above 5 differ from it in how they *search*, not
    in what they think a quiet position is worth.
    """
    return tapered_pst(board) + positional_score(board)


def positional_eval_v2(board: chess.Board) -> int:
    """The evaluation as it stood before the rook term was adopted."""
    from engine.evaluation.positional import positional_score_v2

    return tapered_pst(board) + positional_score_v2(board)


def positional_eval_v3(board: chess.Board, king_attackers: bool = True) -> int:
    """Version 2 plus the terms that need to look around the board.

    Passed pawns, rook files and king safety. It knows more than
    :func:`positional_eval` and costs two to three times as much per leaf,
    which in a search is depth traded for knowledge. Whether that trade is
    worth making is decided by ``scripts/eval_ab.py``, not by argument.
    """
    from engine.evaluation.positional import positional_score_v2
    from engine.evaluation.structure import structure_score

    return (
        tapered_pst(board)
        + positional_score_v2(board)
        + structure_score(board, game_phase(board), king_attackers)
    )


def positional_eval_passers(board: chess.Board) -> int:
    """Version 2 plus passed pawns, and nothing else.

    Evaluation v3 was tested as a bundle of three terms and rejected as one.
    That leaves an obvious gap: passed pawns are the cheapest of the three
    (~1.6µs) and the one with the strongest classical claim, and a bundle
    failing says nothing about its parts.
    """
    from engine.evaluation.positional import positional_score_v2
    from engine.evaluation.structure import passed_pawn_scores

    phase = game_phase(board)
    endgame_weight = (TOTAL_PHASE - phase) / TOTAL_PHASE
    middlegame_weight = phase / TOTAL_PHASE

    passers = 0.0
    for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
        middlegame, endgame = passed_pawn_scores(board, color)
        passers += sign * (middlegame * middlegame_weight + endgame * endgame_weight)

    return tapered_pst(board) + positional_score_v2(board) + int(passers)


def positional_eval_shelter(board: chess.Board) -> int:
    """Version 2 plus king shelter, and nothing else.

    This variant was missing, and its absence caused a wrong reading: the
    variant named ``v3-shelter`` is ``positional_eval_v3`` with only the
    *attacker* half of king safety switched off, so it carries passed pawns
    and rook files as well. Measuring shelter on its own needs this.
    """
    from engine.evaluation.positional import positional_score_v2
    from engine.evaluation.structure import KING_SAFETY_MIN_PHASE, king_shelter_score

    phase = game_phase(board)
    score = float(tapered_pst(board) + positional_score_v2(board))
    if phase >= KING_SAFETY_MIN_PHASE:
        middlegame_weight = phase / TOTAL_PHASE
        for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            score += sign * king_shelter_score(board, color) * middlegame_weight
    return int(score)


def positional_eval_rooks(board: chess.Board) -> int:
    """Version 2 plus rooks on open files, and nothing else.

    The one term in Evaluation v3 that a piece-square table genuinely cannot
    know. A table scores a rook by where it stands; whether the file under it
    is open depends on the pawns, which the table cannot see. Passed pawns and
    king shelter both turned out to restate what the tables already encode —
    this one does not, which makes it the term worth testing on its own.
    """
    from engine.evaluation.positional import positional_score_v2
    from engine.evaluation.structure import rook_file_score

    rooks = rook_file_score(board, chess.WHITE) - rook_file_score(board, chess.BLACK)
    return tapered_pst(board) + positional_score_v2(board) + rooks
