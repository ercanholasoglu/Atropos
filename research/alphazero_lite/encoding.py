"""Turning a chess position into tensors, and a policy vector back into moves.

**The board** becomes 19 planes of 8×8: twelve for the pieces, four for
castling rights, one for the side to move, one for an en-passant square and
one holding the halfmove clock. Everything is written from the side to move's
point of view — the board is flipped for Black — so the network never has to
learn the game twice.

**The move** uses AlphaZero's 8×8×73 scheme: for each origin square, 56
"queen moves" (eight directions by seven distances), 8 knight moves and 9
underpromotions (three pieces by three directions). 4,672 outputs in total.

The obvious alternative — one output per ``from × to`` pair, 4,096 of them —
is simpler and much worse, and it is worth saying why. The 73 planes are
produced by a 1×1 convolution over the tower's channels, which costs about
4,700 parameters. A dense layer to 4,096 outputs costs 8.4 *million*, which
in a network this size means the policy head is 96% of the model and the
residual tower it is supposed to read is a rounding error. The plane scheme
also gets underpromotion for free, where the flat one has to pretend every
promotion is a queen.
"""

from __future__ import annotations

import chess
import numpy as np

PLANES = 19
BOARD_SIZE = 8

# 8 directions x 7 distances, then knights, then underpromotions.
QUEEN_DIRECTIONS = (
    (0, 1),  # north
    (1, 1),  # north-east
    (1, 0),  # east
    (1, -1),  # south-east
    (0, -1),  # south
    (-1, -1),  # south-west
    (-1, 0),  # west
    (-1, 1),  # north-west
)
KNIGHT_DELTAS = (
    (1, 2),
    (2, 1),
    (2, -1),
    (1, -2),
    (-1, -2),
    (-2, -1),
    (-2, 1),
    (-1, 2),
)
UNDERPROMOTIONS = (chess.KNIGHT, chess.BISHOP, chess.ROOK)

QUEEN_PLANES = len(QUEEN_DIRECTIONS) * 7  # 56
KNIGHT_PLANES = len(KNIGHT_DELTAS)  # 8
UNDERPROMOTION_PLANES = len(UNDERPROMOTIONS) * 3  # 9
MOVE_PLANES = QUEEN_PLANES + KNIGHT_PLANES + UNDERPROMOTION_PLANES  # 73
POLICY_SIZE = MOVE_PLANES * 64  # 4,672

PIECE_ORDER = (
    chess.PAWN,
    chess.KNIGHT,
    chess.BISHOP,
    chess.ROOK,
    chess.QUEEN,
    chess.KING,
)


def _orient(square: chess.Square, flip: bool) -> chess.Square:
    """Mirror a square when it is Black to move, so 'forward' is always up."""
    return square ^ 56 if flip else square


def encode_board(board: chess.Board) -> np.ndarray:
    """``(19, 8, 8)`` float32 planes, from the side-to-move's perspective."""
    flip = board.turn == chess.BLACK
    planes = np.zeros((PLANES, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)

    us, them = (chess.BLACK, chess.WHITE) if flip else (chess.WHITE, chess.BLACK)
    for index, piece_type in enumerate(PIECE_ORDER):
        for offset, colour in ((0, us), (6, them)):
            for square in chess.scan_forward(board.pieces_mask(piece_type, colour)):
                oriented = _orient(square, flip)
                planes[index + offset, chess.square_rank(oriented), chess.square_file(oriented)] = (
                    1.0
                )

    rights = (
        board.has_kingside_castling_rights(us),
        board.has_queenside_castling_rights(us),
        board.has_kingside_castling_rights(them),
        board.has_queenside_castling_rights(them),
    )
    for index, has_right in enumerate(rights):
        if has_right:
            planes[12 + index] = 1.0

    planes[16] = 1.0 if board.turn == chess.WHITE else 0.0
    if board.ep_square is not None:
        oriented = _orient(board.ep_square, flip)
        planes[17, chess.square_rank(oriented), chess.square_file(oriented)] = 1.0
    planes[18] = min(board.halfmove_clock, 100) / 100.0
    return planes


def move_plane(move: chess.Move, flip: bool) -> int:
    """Which of the 73 planes a move belongs to."""
    origin = _orient(move.from_square, flip)
    target = _orient(move.to_square, flip)
    file_delta = chess.square_file(target) - chess.square_file(origin)
    rank_delta = chess.square_rank(target) - chess.square_rank(origin)

    if move.promotion and move.promotion != chess.QUEEN:
        # Three directions: capture left, straight ahead, capture right.
        direction = {-1: 0, 0: 1, 1: 2}.get(file_delta)
        if direction is None or move.promotion not in UNDERPROMOTIONS:
            raise ValueError(f"cannot encode promotion {move.uci()}")
        return QUEEN_PLANES + KNIGHT_PLANES + UNDERPROMOTIONS.index(move.promotion) * 3 + direction

    if (file_delta, rank_delta) in KNIGHT_DELTAS:
        return QUEEN_PLANES + KNIGHT_DELTAS.index((file_delta, rank_delta))

    distance = max(abs(file_delta), abs(rank_delta))
    step = (
        0 if file_delta == 0 else (1 if file_delta > 0 else -1),
        0 if rank_delta == 0 else (1 if rank_delta > 0 else -1),
    )
    # The move must actually lie on the ray, not merely point that way. Every
    # legal queen, rook, bishop, king and pawn move does; skipping the check
    # would quietly encode a1-c4 as a1-d4 and collide two distinct moves.
    on_ray = step[0] * distance == file_delta and step[1] * distance == rank_delta
    if step not in QUEEN_DIRECTIONS or not on_ray or not 1 <= distance <= 7:
        raise ValueError(f"cannot encode move {move.uci()}")
    return QUEEN_DIRECTIONS.index(step) * 7 + (distance - 1)


def move_index(move: chess.Move, flip: bool = False) -> int:
    """Index of a move in the 4,672-wide policy vector."""
    return move_plane(move, flip) * 64 + _orient(move.from_square, flip)


def index_to_move(index: int, board: chess.Board) -> chess.Move | None:
    """The legal move an index refers to, or ``None``.

    Decoded by searching the legal moves rather than inverting the arithmetic:
    the inverse is ambiguous for promotions (a queen promotion and a plain
    pawn push share a plane), and the legal list is short.
    """
    flip = board.turn == chess.BLACK
    for move in board.legal_moves:
        if move_index(move, flip) == index:
            return move
    return None


def legal_move_mask(board: chess.Board) -> np.ndarray:
    """A policy-width mask with 1.0 wherever a legal move lands."""
    flip = board.turn == chess.BLACK
    mask = np.zeros(POLICY_SIZE, dtype=np.float32)
    for move in board.legal_moves:
        mask[move_index(move, flip)] = 1.0
    return mask


def policy_to_moves(policy: np.ndarray, board: chess.Board) -> dict[chess.Move, float]:
    """Map a policy vector onto the legal moves, renormalised.

    Illegal moves are dropped rather than penalised: masking is what keeps an
    untrained network from proposing nonsense, and renormalising is what keeps
    the remainder a distribution.
    """
    flip = board.turn == chess.BLACK
    priors: dict[chess.Move, float] = {}
    total = 0.0
    for move in board.legal_moves:
        weight = float(policy[move_index(move, flip)])
        priors[move] = weight
        total += weight

    if total <= 0:
        uniform = 1.0 / len(priors) if priors else 0.0
        return {move: uniform for move in priors}
    return {move: weight / total for move, weight in priors.items()}
