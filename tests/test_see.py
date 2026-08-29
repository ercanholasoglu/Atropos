"""Static exchange evaluation, checked against exchanges worked out by hand."""

from __future__ import annotations

import chess
import pytest

from engine.search.see import is_losing_capture, see
from engine.utils.constants import PIECE_VALUES

# (fen, uci, expected centipawns, why)
EXCHANGES = [
    ("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1", "e4d5", 100, "undefended pawn"),
    ("4k3/2n5/8/3p4/4P3/8/8/4K3 w - - 0 1", "e4d5", 0, "pawn takes pawn, knight recaptures"),
    (
        "4k3/2n5/8/3p4/8/5N2/8/4K3 w - - 0 1",
        "f3d5",
        PIECE_VALUES[chess.PAWN] - PIECE_VALUES[chess.KNIGHT],
        "knight takes a defended pawn and is lost",
    ),
    (
        "4k3/2n5/8/3p4/4P3/8/8/3RK3 w - - 0 1",
        "e4d5",
        100,
        "pawn takes, knight recaptures, rook retakes: a pawn up",
    ),
    ("4k3/8/8/8/8/8/8/4K2R w K - 0 1", "e1e2", 0, "a quiet move is not an exchange"),
]


@pytest.mark.parametrize("fen,uci,expected,why", EXCHANGES)
def test_exchange_value(fen: str, uci: str, expected: int, why: str) -> None:
    board = chess.Board(fen)
    assert see(board, chess.Move.from_uci(uci)) == expected, why


def test_xray_changes_the_verdict() -> None:
    """A second rook behind the first joins the exchange once the first leaves.

    This is the case the occupancy parameter exists for: with the back rook
    the capture wins a pawn, without it the same capture drops a rook.
    """
    with_xray = chess.Board("3r3k/8/8/3p4/8/8/3R4/3RK3 w - - 0 1")
    without = chess.Board("3r3k/8/8/3p4/8/8/3R4/4K3 w - - 0 1")
    move = chess.Move.from_uci("d2d5")

    assert see(with_xray, move) > 0
    assert see(without, move) < 0


def test_promotions_are_not_judged() -> None:
    """Promotions report neutral so a caller pruning on ``< 0`` keeps them.

    The attacker's value changes midway through the exchange and this
    implementation does not model that; reporting 0 makes the omission fail
    safe rather than prune a real line.
    """
    board = chess.Board("4k3/6P1/8/8/8/8/8/4K3 w - - 0 1")
    move = chess.Move.from_uci("g7g8q")
    assert see(board, move) == 0
    assert not is_losing_capture(board, move)


def test_king_cannot_recapture_into_check() -> None:
    """A king may not be the recapturing piece on a square still defended.

    Without the guard the swap loop trades the king off and reports a
    six-figure score. Both positions below are the same exchange; the only
    difference is whether a bishop covers the square the king would land on.
    """
    move = chess.Move.from_uci("d1d7")
    # Ba4 covers d7, so Kxd7 is unavailable and White simply wins the pawn.
    covered = chess.Board("4k3/3p4/8/8/B7/8/8/3RK3 w - - 0 1")
    assert see(covered, move) == PIECE_VALUES[chess.PAWN]

    # The same position without the bishop: the king recaptures, winning a rook.
    open_square = chess.Board("4k3/3p4/8/8/8/8/8/3RK3 w - - 0 1")
    assert see(open_square, move) == PIECE_VALUES[chess.PAWN] - PIECE_VALUES[chess.ROOK]


def test_en_passant_removes_the_right_pawn() -> None:
    """The pawn taken en passant is not on the destination square."""
    board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2")
    move = chess.Move.from_uci("e5d6")
    assert board.is_en_passant(move)
    assert see(board, move) == PIECE_VALUES[chess.PAWN]


def test_see_does_not_mutate_the_board() -> None:
    """It reads the position; it must not leave a trace on it."""
    board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    before, stack = board.fen(), list(board.move_stack)
    for move in board.legal_moves:
        see(board, move)
    assert board.fen() == before
    assert board.move_stack == stack
