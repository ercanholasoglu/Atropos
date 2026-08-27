"""A small opening book for engine testing.

Engines that start every game from the initial position play near-identical
games, and material-only levels in particular tend to shuffle into move-limit
draws. Testing from a fixed set of openings — each played once with each
colour — is what real engine gauntlets do: it cuts variance and produces
decisive games sooner.

Lines are stored as SAN and converted to FEN at import time, so a typo is a
loud failure rather than a silently illegal position.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess


@dataclass(frozen=True)
class Opening:
    name: str
    moves: tuple[str, ...]
    fen: str

    @property
    def ply(self) -> int:
        return len(self.moves)


_LINES: list[tuple[str, list[str]]] = [
    ("Open Game", ["e4", "e5", "Nf3", "Nc6", "Bc4"]),
    ("Ruy Lopez", ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"]),
    ("Sicilian", ["e4", "c5", "Nf3", "d6", "d4", "cxd4"]),
    ("French", ["e4", "e6", "d4", "d5", "Nc3"]),
    ("Caro-Kann", ["e4", "c6", "d4", "d5", "Nc3"]),
    ("Queen's Gambit", ["d4", "d5", "c4", "e6", "Nc3"]),
    ("King's Indian", ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7"]),
    ("English", ["c4", "e5", "Nc3", "Nf6", "g3"]),
]


def _build(name: str, moves: list[str]) -> Opening:
    board = chess.Board()
    for san in moves:
        board.push_san(san)
    return Opening(name=name, moves=tuple(moves), fen=board.fen())


OPENING_BOOK: list[Opening] = [_build(name, moves) for name, moves in _LINES]

STARTING_OPENING = Opening(name="Start", moves=(), fen=chess.STARTING_FEN)


def book(count: int | None = None) -> list[Opening]:
    """The first ``count`` openings (all of them by default)."""
    return OPENING_BOOK[:count] if count else list(OPENING_BOOK)
