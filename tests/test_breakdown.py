"""The evaluation breakdown, and the one property that makes it usable."""

from __future__ import annotations

import random

import chess
import pytest

from engine.evaluation.breakdown import breakdown
from engine.evaluation.tapered import positional_eval
from tournament.openings import OPENING_BOOK


def positions(seed: int = 1, per_opening: int = 40):
    rng = random.Random(seed)
    for opening in OPENING_BOOK:
        board = chess.Board(opening.fen)
        for _ in range(per_opening):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
            yield board.copy()


def test_the_parts_sum_to_what_the_engine_computed():
    """The whole contract. A breakdown that drifts looks like evidence.

    Checked over hundreds of positions rather than a handful, because the
    failure mode is a term that is only non-zero occasionally -- which is
    exactly what happened on the first version: the rook term was added into
    the sum while the shipped evaluation no longer contained it, and 131 of
    480 positions disagreed.
    """
    checked = 0
    for board in positions():
        parts = breakdown(board)
        assert parts.residual == 0, (board.fen(), parts)
        assert parts.total == positional_eval(board)
        checked += 1
    assert checked > 300


def test_terms_the_engine_does_not_use_are_reported_but_not_summed():
    """Both are candidates the measurements sent away; neither is in the total.

    The rook term measured -2 [-26, +22] against the +44 it shipped on and came
    out at the instrument-v2 cut. King shelter measured -53 [-84, -24] and
    never went in. They are logged so a later question has data, and kept out
    of the sum so the sum stays exact.
    """
    seen_rooks = seen_shelter = False
    for board in positions(seed=3):
        parts = breakdown(board)
        seen_rooks |= parts.rook_files_unused != 0
        seen_shelter |= parts.king_shelter_unused != 0
        assert parts.residual == 0
    assert seen_rooks, "no position exercised the rook term"
    assert seen_shelter, "no position exercised king shelter"


def test_material_is_piece_values_only():
    """Two knights against two knights is level, wherever they stand."""
    board = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert breakdown(board).material == 0

    board = chess.Board("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert breakdown(board).material == 900


def test_placement_is_what_the_tables_add_beyond_material():
    """A piece on a good square scores more than the same piece on a bad one."""
    centre = chess.Board("4k3/8/8/3N4/8/8/8/4K3 w - - 0 1")
    corner = chess.Board("4k3/8/8/8/8/8/8/N3K3 w - - 0 1")
    assert breakdown(centre).material == breakdown(corner).material
    assert breakdown(centre).placement > breakdown(corner).placement


@pytest.mark.parametrize("fen", [o.fen for o in OPENING_BOOK])
def test_a_book_position_breaks_down_cleanly(fen: str):
    parts = breakdown(chess.Board(fen))
    assert parts.residual == 0
    assert 0 <= parts.phase <= 24
