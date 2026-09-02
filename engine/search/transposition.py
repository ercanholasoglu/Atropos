"""Transposition table.

The same position turns up again and again through different move orders. A
transposition table remembers what a search already learned about it, so the
second visit is a dictionary lookup instead of a subtree.

**On Zobrist hashing.** The textbook answer is an incrementally-updated
Zobrist key. In Python it is the wrong answer: ``chess.polyglot.zobrist_hash``
recomputes from scratch and measures at ~10µs per call — more than twice the
cost of the entire evaluation it is meant to save, so a table keyed on it
loses time on every node. Maintaining the key incrementally instead would
mean shadowing python-chess's own make/unmake logic (castling rooks, en
passant squares, promotion, castling-right changes) and a single missed XOR
would silently return the wrong move.

python-chess already maintains exactly such a key for its own repetition
detection, assembled straight from the piece bitboards, and reading it costs
~0.4µs. That is what this module uses.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from engine.utils.constants import MATE_THRESHOLD

# Bound types: how a stored score relates to the true one.
EXACT = 0  # the score is the true value of the position
LOWER = 1  # a beta cutoff: the true score is at least this
UPPER = 2  # nothing beat alpha: the true score is at most this

DEFAULT_SIZE = 1 << 20  # entries, must be a power of two


def position_key(board: chess.Board) -> int:
    """A hashable key identifying a position, castling and en passant rights
    included. See the module docstring for why this is not a Zobrist hash."""
    return hash(board._transposition_key())


@dataclass(slots=True)
class TTEntry:
    key: int
    depth: int
    score: float
    flag: int
    move: chess.Move | None


def score_to_tt(score: float, ply: int) -> float:
    """Make a mate score independent of where in the tree it was found.

    Stored scores are reused at other depths, and "mate in 3 from here" only
    means anything relative to the node that found it.
    """
    if score >= MATE_THRESHOLD:
        return score + ply
    if score <= -MATE_THRESHOLD:
        return score - ply
    return score


def score_from_tt(score: float, ply: int) -> float:
    """Undo :func:`score_to_tt` for the node doing the lookup."""
    if score >= MATE_THRESHOLD:
        return score - ply
    if score <= -MATE_THRESHOLD:
        return score + ply
    return score


class TranspositionTable:
    """Fixed-size, direct-mapped table with depth-preferred replacement.

    Fixed size rather than a growing dict: a long game would otherwise let
    the table swallow memory without bound. Two positions can land on the
    same slot, so each entry carries its own key and a mismatch is treated
    as a miss.
    """

    def __init__(self, size: int = DEFAULT_SIZE, key_bits: int | None = None) -> None:
        if size & (size - 1):
            raise ValueError("size must be a power of two")
        if key_bits is not None and not 1 <= key_bits <= 64:
            raise ValueError("key_bits must be between 1 and 64")
        self.size = size
        self.mask = size - 1
        # A narrower key is an experiment, not an option worth having: see
        # `docs/ZOBRIST_PREREG.md`. `None` keeps the full key. The truncation
        # happens before the index is taken, because that is what a genuinely
        # narrow key would do — a 16-bit key cannot address more than 2**16
        # slots however large the table is.
        self.key_bits = key_bits
        self.key_mask = -1 if key_bits is None else (1 << key_bits) - 1
        self.entries: list[TTEntry | None] = [None] * size
        self.hits = 0
        self.misses = 0
        self.stores = 0
        self.collisions = 0

    def clear(self) -> None:
        self.entries = [None] * self.size
        self.hits = self.misses = self.stores = self.collisions = 0

    def lookup(self, key: int) -> TTEntry | None:
        """The entry for ``key``, or None. Does not touch hit/miss counters."""
        key &= self.key_mask
        entry = self.entries[key & self.mask]
        return entry if entry is not None and entry.key == key else None

    def probe(
        self, key: int, depth: int, alpha: float, beta: float, ply: int
    ) -> tuple[float | None, chess.Move | None]:
        """Look up a position.

        Returns ``(score, move)``. The score is only usable when the stored
        search was at least as deep as the one being run *and* its bound is
        tight enough for the current window; otherwise it is ``None`` and only
        the move comes back — still worth having, as the first move to try.
        """
        key &= self.key_mask
        entry = self.entries[key & self.mask]
        if entry is None or entry.key != key:
            self.misses += 1
            return None, None

        self.hits += 1
        if entry.depth < depth:
            return None, entry.move

        score = score_from_tt(entry.score, ply)
        if entry.flag == EXACT:
            return score, entry.move
        if entry.flag == LOWER and score >= beta:
            return score, entry.move
        if entry.flag == UPPER and score <= alpha:
            return score, entry.move
        return None, entry.move

    def store(
        self,
        key: int,
        depth: int,
        score: float,
        flag: int,
        move: chess.Move | None,
        ply: int,
    ) -> None:
        """Record a result, keeping the deeper of two entries in a slot."""
        key &= self.key_mask
        index = key & self.mask
        existing = self.entries[index]
        if existing is not None and existing.key != key:
            self.collisions += 1
        elif existing is not None and existing.depth > depth and existing.flag == EXACT:
            # A deeper exact result is worth more than a shallow new one.
            return

        self.entries[index] = TTEntry(
            key=key, depth=depth, score=score_to_tt(score, ply), flag=flag, move=move
        )
        self.stores += 1

    @property
    def occupancy(self) -> float:
        return sum(1 for entry in self.entries if entry is not None) / self.size

    def __len__(self) -> int:
        return sum(1 for entry in self.entries if entry is not None)
