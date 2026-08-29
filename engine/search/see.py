"""Static exchange evaluation — what a capture is actually worth.

MVV-LVA orders captures by what they take. It cannot tell the difference
between winning a queen and losing a rook to win a pawn, because it never
looks at what recaptures. SEE plays the whole exchange out on one square,
each side always recapturing with its least valuable attacker, and reports
the material the initiating side ends up with.

The point of having it is not ordering — it is *pruning*. A capture with a
negative SEE is a capture that loses material against best play, and in
quiescence, where 69% of this engine's nodes are spent, searching those is
almost pure waste.

Two deliberate limits:

* **Promotions are not evaluated.** A promotion changes the value of the
  attacking piece midway through the exchange, and getting that wrong in the
  pruning direction loses real lines. They are reported as "not losing" so
  the caller searches them.
* **X-rays are handled, pins are not.** Removing a piece from the occupancy
  exposes the slider behind it, which is the whole reason `attackers_mask`
  takes an occupancy here. A piece that is pinned against its own king will
  still be counted as an attacker, which can make an exchange look worse for
  the defender than it is. That is the standard trade: detecting pins costs
  more than the pruning saves.
"""

from __future__ import annotations

import chess

from engine.utils.constants import PIECE_VALUES

# The king is worth more than any exchange; a real value would let the swap
# loop trade it away.
_KING_VALUE = 100_000

_ORDER = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)


def _value(piece_type: chess.PieceType) -> int:
    return _KING_VALUE if piece_type == chess.KING else PIECE_VALUES[piece_type]


def _least_valuable(board: chess.Board, attackers: int) -> tuple[int, chess.PieceType] | None:
    """The cheapest attacker in the mask, as ``(square, piece type)``."""
    for piece_type in _ORDER:
        subset = attackers & board.pieces_mask(piece_type, chess.WHITE)
        subset |= attackers & board.pieces_mask(piece_type, chess.BLACK)
        if subset:
            return (chess.lsb(subset), piece_type)
    return None


def see(board: chess.Board, move: chess.Move) -> int:
    """Material the mover comes out ahead by, in centipawns.

    Positive is good for the side to move. A quiet move is 0; so is a capture
    that trades evenly.
    """
    if move.promotion:
        # Not evaluated — see the module docstring. Reported as neutral so a
        # caller pruning on `see(...) < 0` leaves promotions alone.
        return 0

    target = move.to_square
    attacker_square = move.from_square
    attacker_type = board.piece_type_at(attacker_square)
    if attacker_type is None:
        return 0

    if board.is_en_passant(move):
        captured_value = PIECE_VALUES[chess.PAWN]
        # The pawn taken en passant is not on the target square.
        captured_square = target + (-8 if board.turn == chess.WHITE else 8)
        occupied = board.occupied & ~chess.BB_SQUARES[captured_square]
    else:
        victim = board.piece_type_at(target)
        if victim is None:
            return 0
        captured_value = _value(victim)
        occupied = board.occupied

    # gains[d] is the score for the side to move at depth d, assuming the
    # exchange stops there.
    gains = [captured_value]
    occupied &= ~chess.BB_SQUARES[attacker_square]
    side = not board.turn
    depth = 0

    while True:
        attackers = board.attackers_mask(side, target, occupied) & occupied
        cheapest = _least_valuable(board, attackers)
        if cheapest is None:
            break
        square, piece_type = cheapest

        if piece_type == chess.KING:
            # A king may not recapture onto a square the other side still
            # attacks. Tested before the level is recorded, not after: a king
            # that cannot capture never gets a turn in the exchange at all.
            rest = occupied & ~chess.BB_SQUARES[square]
            if board.attackers_mask(not side, target, rest) & rest:
                break

        depth += 1
        gains.append(_value(attacker_type) - gains[depth - 1])
        attacker_type = piece_type
        occupied &= ~chess.BB_SQUARES[square]
        side = not side

    # Fold back: at every point a side could have declined the recapture, so
    # it takes the better of standing still and continuing.
    while depth > 0:
        gains[depth - 1] = -max(-gains[depth - 1], gains[depth])
        depth -= 1
    return gains[0]


def is_losing_capture(board: chess.Board, move: chess.Move) -> bool:
    """Whether the exchange on this square comes out behind for the mover."""
    return see(board, move) < 0
