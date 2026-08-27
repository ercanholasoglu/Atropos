"""Move ordering.

Alpha-beta only pays off when good moves are tried first: the earlier a
cutoff happens, the smaller the tree. This module grows with the ladder —
Level 4 uses the basic capture-first ordering below, and Level 6 adds
MVV-LVA, killer moves and the transposition-table move on top.
"""

from __future__ import annotations

import chess

from engine.utils.constants import PIECE_VALUES

# Captures and promotions are scored far above quiet moves so they always
# sort first, whatever their material delta.
_CAPTURE_BONUS = 10_000
_PROMOTION_BONUS = 20_000


def basic_move_score(board: chess.Board, move: chess.Move) -> int:
    """Ordering score for Level 4: promotions, then captures by victim value.

    Deliberately simpler than MVV-LVA — it looks at *what* is captured but
    not at what does the capturing. Level 6 refines this.
    """
    score = 0
    if move.promotion:
        score += _PROMOTION_BONUS + PIECE_VALUES.get(move.promotion, 0)
    if board.is_capture(move):
        if board.is_en_passant(move):
            victim = PIECE_VALUES[chess.PAWN]
        else:
            victim_type = board.piece_type_at(move.to_square)
            victim = PIECE_VALUES[victim_type] if victim_type else 0
        score += _CAPTURE_BONUS + victim
    return score


def order_moves_basic(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    """Sort moves best-first using :func:`basic_move_score` (stable)."""
    return sorted(moves, key=lambda m: basic_move_score(board, m), reverse=True)


def captures_first(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    """Partition into captures/promotions then the rest, order untouched.

    The cheapest useful ordering; used where a full sort is not worth it.
    """
    loud: list[chess.Move] = []
    quiet: list[chess.Move] = []
    for move in moves:
        if board.is_capture(move) or move.promotion:
            loud.append(move)
        else:
            quiet.append(move)
    return loud + quiet


# --- Level 6+ ordering ----------------------------------------------------

# Score bands, wide enough that a move never jumps into the band above it.
TT_MOVE_SCORE = 1_000_000
CAPTURE_BASE = 100_000
KILLER_BASE = 90_000
HISTORY_CAP = KILLER_BASE - 1_000


def mvv_lva(board: chess.Board, move: chess.Move) -> int:
    """Most Valuable Victim, Least Valuable Attacker.

    ``PxQ`` is tried before ``QxP``: both win material, but if the queen
    capture is bad it is bad by a lot, and the cheap capture is the one more
    likely to cause a cutoff. This is the refinement Level 4's ordering
    leaves out — it weighs the victim only.
    """
    if board.is_en_passant(move):
        victim = PIECE_VALUES[chess.PAWN]
    else:
        victim_type = board.piece_type_at(move.to_square)
        victim = PIECE_VALUES[victim_type] if victim_type else 0
    attacker_type = board.piece_type_at(move.from_square)
    attacker = PIECE_VALUES[attacker_type] if attacker_type else 0
    return victim * 10 - attacker


class KillerMoves:
    """Quiet moves that caused a beta cutoff at a given ply.

    A move that refuted one line at this depth very often refutes its
    siblings too, so it is worth trying before the rest of the quiet moves.
    Two slots per ply: the newest killer and the one before it.
    """

    def __init__(self, max_ply: int = 64) -> None:
        self.max_ply = max_ply
        self.slots: list[list[chess.Move | None]] = [[None, None] for _ in range(max_ply + 1)]

    def clear(self) -> None:
        for slot in self.slots:
            slot[0] = slot[1] = None

    def store(self, ply: int, move: chess.Move) -> None:
        if ply > self.max_ply:
            return
        slot = self.slots[ply]
        if slot[0] == move:
            return
        slot[1] = slot[0]
        slot[0] = move

    def get(self, ply: int) -> tuple[chess.Move | None, chess.Move | None]:
        if ply > self.max_ply:
            return None, None
        slot = self.slots[ply]
        return slot[0], slot[1]


class HistoryHeuristic:
    """How often a quiet move has caused a cutoff, anywhere in the tree.

    Killers are per-ply and short-lived; history is the long game. Cutoffs
    deeper in the tree count for more, because they were more expensive to
    establish.
    """

    def __init__(self) -> None:
        self.table = [[[0] * 64 for _ in range(64)] for _ in range(2)]

    def clear(self) -> None:
        for color_table in self.table:
            for row in color_table:
                for square in range(64):
                    row[square] = 0

    def record(self, color: chess.Color, move: chess.Move, depth: int) -> None:
        entry = self.table[int(color)][move.from_square]
        entry[move.to_square] += depth * depth
        if entry[move.to_square] > HISTORY_CAP:
            # Halve the whole side rather than let one move saturate the band
            # and freeze the ordering.
            for row in self.table[int(color)]:
                for square in range(64):
                    row[square] >>= 1

    def get(self, color: chess.Color, move: chess.Move) -> int:
        return self.table[int(color)][move.from_square][move.to_square]


def order_moves(
    board: chess.Board,
    moves: list[chess.Move],
    tt_move: chess.Move | None = None,
    killers: KillerMoves | None = None,
    history: HistoryHeuristic | None = None,
    ply: int = 0,
) -> list[chess.Move]:
    """Full ordering: transposition-table move, captures, killers, history."""
    killer_a, killer_b = killers.get(ply) if killers is not None else (None, None)
    color = board.turn

    def score(move: chess.Move) -> int:
        if move == tt_move:
            return TT_MOVE_SCORE
        if board.is_capture(move) or move.promotion:
            bonus = PIECE_VALUES.get(move.promotion, 0) if move.promotion else 0
            return CAPTURE_BASE + mvv_lva(board, move) + bonus
        if move == killer_a:
            return KILLER_BASE
        if move == killer_b:
            return KILLER_BASE - 1
        if history is not None:
            return min(history.get(color, move), HISTORY_CAP)
        return 0

    return sorted(moves, key=score, reverse=True)


def generate_loud_moves(board: chess.Board) -> list[chess.Move]:
    """Captures and promotions, generated directly rather than filtered.

    Quiescence only ever wants the forcing moves, and building the full legal
    list to throw most of it away is the most expensive thing it does — 46µs
    against 8µs in a middlegame position, and quiescence is the majority of
    all nodes searched.

    ``generate_legal_captures`` covers en passant but not a promotion that
    captures nothing, so those are added separately: a pawn stepping onto the
    last rank is as forcing as anything on the board.
    """
    moves = list(board.generate_legal_captures())

    rank = chess.BB_RANK_7 if board.turn == chess.WHITE else chess.BB_RANK_2
    promoting = board.pawns & board.occupied_co[board.turn] & rank
    if promoting:
        moves += [
            move
            for move in board.generate_legal_moves(promoting, ~board.occupied)
            if move.promotion
        ]
    return moves


def order_loud_moves(board: chess.Board) -> list[chess.Move]:
    """The quiescence move list, generated and ordered in one step."""
    moves = generate_loud_moves(board)
    if len(moves) > 1:
        moves.sort(key=lambda move: mvv_lva(board, move), reverse=True)
    return moves


def order_captures(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    """Filter an existing list down to the loud moves, best first."""
    loud = [m for m in moves if board.is_capture(m) or m.promotion]
    return sorted(loud, key=lambda m: mvv_lva(board, m), reverse=True)
