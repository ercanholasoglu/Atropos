"""What the evaluation is made of, for one position.

A match tells you which engine won. It does not tell you *what the winner
thought*, and that cannot be reconstructed afterwards — the search is gone the
moment the game ends. Logging the evaluation term by term while the games are
played is the only way to answer "where did this change actually help?", which
is the question every result in this project raises and none of them can
currently answer.

**The components sum to the engine's evaluation exactly.** That is the whole
contract, and a test asserts it over hundreds of positions: a breakdown that
drifts from what the engine actually computed is worse than no breakdown,
because it looks like evidence.

The split follows the code rather than the textbook. `material` and `placement`
are separated out of the piece-square tables — the tables have piece values
baked in, so material is the value-only part and placement is what the table
adds on top — and both are tapered together, which is why they are reported
after the blend rather than as raw middlegame and endgame numbers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import chess

from engine.evaluation.pst import pst_scores
from engine.evaluation.positional import pawn_structure_score
from engine.evaluation.structure import king_shelter_score, rook_file_score
from engine.evaluation.tapered import game_phase, taper
from engine.utils.constants import PIECE_VALUES


@dataclass(frozen=True)
class EvalBreakdown:
    """One position's evaluation, White-relative, in centipawns.

    ``total`` is what the engine computed. The named parts sum to it, and
    ``residual`` is the difference — zero by construction, kept so that a
    future term added to the evaluation and forgotten here shows up as a
    non-zero number rather than silently unbalancing the split.
    """

    total: int
    material: int
    placement: int
    pawn_structure: int
    bishop_pair: int
    phase: int
    # Neither of these is in the sum. Both are terms the engine *could* carry
    # and does not: the rook term was taken out at the instrument-v2 cut when
    # 600 fixed games measured -2 [-26, +22] against the +44 it shipped on, and
    # king shelter was never in, measuring -53 [-84, -24] on its own. They are
    # logged because "what would that term have said here?" is answerable only
    # while the game is being played, and both are candidates that could come
    # back if a future measurement says so.
    rook_files_unused: int
    king_shelter_unused: int
    residual: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _material(board: chess.Board) -> int:
    """Piece values only, White-relative."""
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        if piece_type == chess.KING:
            continue
        total += value * (
            len(board.pieces(piece_type, chess.WHITE)) - len(board.pieces(piece_type, chess.BLACK))
        )
    return total


def _pawn_structure(board: chess.Board) -> int:
    """Doubled and isolated pawns, using the engine's own helper.

    Reusing ``pawn_structure_score`` rather than recomputing from the penalty
    constants: a breakdown that re-derives what the engine computes is a second
    implementation that can drift from the first.
    """
    return pawn_structure_score(board, chess.WHITE) - pawn_structure_score(board, chess.BLACK)


def _bishop_pair(board: chess.Board) -> int:
    from engine.evaluation.positional import BISHOP_PAIR_BONUS, has_bishop_pair

    score = 0
    if has_bishop_pair(board, chess.WHITE):
        score += BISHOP_PAIR_BONUS
    if has_bishop_pair(board, chess.BLACK):
        score -= BISHOP_PAIR_BONUS
    return score


def breakdown(board: chess.Board) -> EvalBreakdown:
    """Decompose the evaluation the shipped levels use."""
    from engine.evaluation.tapered import positional_eval

    total = positional_eval(board)
    phase = game_phase(board)

    middlegame, endgame = pst_scores(board)
    tapered = taper(middlegame, endgame, phase)
    material = _material(board)
    placement = tapered - material  # what the tables add beyond piece values

    structure = _pawn_structure(board)
    pair = _bishop_pair(board)
    # Not in the sum under instrument v2 -- the term is out of the evaluation.
    # Computed anyway, so a later question about it has data to answer from.
    rooks = rook_file_score(board, chess.WHITE) - rook_file_score(board, chess.BLACK)

    shelter = king_shelter_score(board, chess.WHITE) - king_shelter_score(board, chess.BLACK)

    parts = material + placement + structure + pair
    return EvalBreakdown(
        total=total,
        material=material,
        placement=placement,
        pawn_structure=structure,
        bishop_pair=pair,
        phase=phase,
        rook_files_unused=rooks,
        king_shelter_unused=shelter,
        residual=total - parts,
    )
