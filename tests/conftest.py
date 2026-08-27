"""Shared test fixtures and position sets.

The match runner used to live here; it is now :mod:`tournament.match`, which
both the tests and ``scripts/ladder.py`` use.
"""

from __future__ import annotations

import chess

# Positions with a mate in one for White. Several of them have more than one
# mating move, so tests assert that the move *mates* rather than pinning down
# one particular SAN.
MATE_IN_ONE_FENS = [
    "6k1/5ppp/8/8/8/8/5PPP/4Q1K1 w - - 0 1",
    "7k/6pp/8/8/8/8/8/R6K w - - 0 1",
    "k7/8/1K6/8/8/8/8/7Q w - - 0 1",
    "6k1/pp3ppp/8/8/8/8/8/R3R1K1 w - - 0 1",
]


def delivers_mate(board: chess.Board, move: chess.Move) -> bool:
    """True if ``move`` is checkmate in ``board`` (board is left unchanged)."""
    board.push(move)
    mate = board.is_checkmate()
    board.pop()
    return mate
