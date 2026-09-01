"""A parameterised version of the engine's evaluation.

The hand-written evaluation has numbers baked into it — a knight is 320, a
doubled pawn costs 15. This module pulls those out into a vector that can be
optimised, while keeping the evaluation itself fast enough to search with.

The decomposition is exact rather than approximate:

    evaluation = material + placement + structure

Tapering is linear and the material term does not depend on the phase, so
material can be lifted straight out of the piece-square tables without
changing any score. With the default parameters this reproduces
``positional_eval`` exactly, which is what makes "did tuning help?" a
question with a clean answer.
"""

from __future__ import annotations

from typing import ClassVar

from dataclasses import astuple, dataclass, fields, replace

import chess
import numpy as np

from engine.evaluation.positional import count_doubled_pawns, count_isolated_pawns
from engine.evaluation.pst import RAW_EG, RAW_MG
from engine.evaluation.tapered import taper
from engine.levels.search_engine import SearchEngine
from engine.search.alphabeta import search_alphabeta
from engine.search.context import RootResult, SearchStats
from engine.utils.helpers import game_phase

PIECE_TYPES = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING)


@dataclass(frozen=True)
class EvalParams:
    """Every number the evaluation is willing to have argued with.

    Defaults are the engine's own values, so an optimiser starts from a
    known-good point rather than from noise — with a self-play budget in the
    hundreds of games, starting from noise would learn nothing.
    """

    pawn: float = 100.0
    knight: float = 320.0
    bishop: float = 330.0
    rook: float = 500.0
    queen: float = 900.0
    doubled_penalty: float = 15.0
    isolated_penalty: float = 12.0
    bishop_pair_bonus: float = 30.0
    # Adopted after a sequential test found it worth +44 Elo on its own; a
    # newly measured term is exactly the kind that has never been tuned.
    # Zero since the instrument-v2 cut: the rook-on-open-file term was taken
    # out of the engine's evaluation when a 600-game fixed-length re-run
    # measured -2 [-26, +22] against the +44 it shipped on. The parameters stay
    # because they are tunable, and a tuner that puts them back would be
    # measuring the term rather than assuming it. `DEFAULT_PARAMS` has to
    # reproduce the engine exactly, and a test asserts it does.
    rook_open_file: float = 0.0
    rook_semi_open_file: float = 0.0
    pst_scale: float = 1.0

    #: The magnitude each parameter is measured in, used to normalise a search
    #: over them. It is normally the default itself, but a parameter whose
    #: default is **zero** has no scale of its own — and two of them are zero
    #: since the instrument-v2 cut took the rook term out. Their nominal values
    #: are the ones the term carried while it was in the engine, so a tuner
    #: exploring from zero is asking "is any of this worth having?" in units
    #: that mean something.
    NOMINAL_SCALE: ClassVar[dict[str, float]] = {
        "rook_open_file": 25.0,
        "rook_semi_open_file": 12.0,
    }

    def scale_vector(self) -> list[float]:
        """One positive scale per field, in ``to_vector`` order."""
        values = self.to_vector()
        names = [f.name for f in fields(self)]
        out = []
        for name, value in zip(names, values):
            magnitude = abs(float(value))
            if magnitude < 1e-9:
                magnitude = self.NOMINAL_SCALE.get(name, 1.0)
            out.append(magnitude)
        return out

    @classmethod
    def names(cls) -> tuple[str, ...]:
        return tuple(field.name for field in fields(cls))

    def to_vector(self) -> np.ndarray:
        return np.array(astuple(self), dtype=np.float64)

    @classmethod
    def from_vector(cls, vector: np.ndarray) -> "EvalParams":
        return cls(**dict(zip(cls.names(), (float(value) for value in vector))))

    def clipped(self) -> "EvalParams":
        """Keep a proposal inside the range where chess still makes sense.

        An optimiser exploring freely will eventually try a negative rook or
        a pawn worth more than a queen; those games are wasted samples, so the
        bounds are enforced before the parameters ever reach a search.
        """
        return replace(
            self,
            pawn=float(np.clip(self.pawn, 40, 200)),
            knight=float(np.clip(self.knight, 150, 600)),
            bishop=float(np.clip(self.bishop, 150, 600)),
            rook=float(np.clip(self.rook, 250, 900)),
            queen=float(np.clip(self.queen, 500, 1800)),
            doubled_penalty=float(np.clip(self.doubled_penalty, 0, 80)),
            isolated_penalty=float(np.clip(self.isolated_penalty, 0, 80)),
            bishop_pair_bonus=float(np.clip(self.bishop_pair_bonus, 0, 120)),
            rook_open_file=float(np.clip(self.rook_open_file, 0, 120)),
            rook_semi_open_file=float(np.clip(self.rook_semi_open_file, 0, 120)),
            pst_scale=float(np.clip(self.pst_scale, 0.0, 3.0)),
        )

    def piece_value(self, piece_type: chess.PieceType) -> float:
        return {
            chess.PAWN: self.pawn,
            chess.KNIGHT: self.knight,
            chess.BISHOP: self.bishop,
            chess.ROOK: self.rook,
            chess.QUEEN: self.queen,
            chess.KING: 0.0,
        }[piece_type]


DEFAULT_PARAMS = EvalParams()


def build_tables(params: EvalParams) -> tuple[list, list]:
    """Fold parameters into per-colour lookup tables, as the engine does.

    Learning code is happy with numpy vectors; a search is not — allocating a
    384-wide array at every leaf would cost more than the search saves. The
    tables here are plain lists of ints, indexed the same way
    ``engine.evaluation.pst`` indexes its own.
    """
    mg_tables: list = [None] * 7
    eg_tables: list = [None] * 7
    for piece_type in PIECE_TYPES:
        value = params.piece_value(piece_type)
        shape_mg = RAW_MG[piece_type]
        shape_eg = RAW_EG[piece_type]
        white_mg = [value + params.pst_scale * shape_mg[square ^ 56] for square in range(64)]
        black_mg = [value + params.pst_scale * shape_mg[square] for square in range(64)]
        white_eg = [value + params.pst_scale * shape_eg[square ^ 56] for square in range(64)]
        black_eg = [value + params.pst_scale * shape_eg[square] for square in range(64)]
        mg_tables[piece_type] = (white_mg, black_mg)
        eg_tables[piece_type] = (white_eg, black_eg)
    return mg_tables, eg_tables


def make_static_eval(params: EvalParams):
    """A White-relative evaluation function for these parameters."""
    mg_tables, eg_tables = build_tables(params)
    doubled = params.doubled_penalty
    isolated = params.isolated_penalty
    pair_bonus = params.bishop_pair_bonus
    open_file = params.rook_open_file
    semi_open_file = params.rook_semi_open_file
    scan = chess.scan_forward
    popcount = chess.popcount

    def static_eval(board: chess.Board) -> int:
        middlegame = 0.0
        endgame = 0.0
        white = board.occupied_co[chess.WHITE]
        black = board.occupied_co[chess.BLACK]

        for piece_type, pieces in (
            (chess.PAWN, board.pawns),
            (chess.KNIGHT, board.knights),
            (chess.BISHOP, board.bishops),
            (chess.ROOK, board.rooks),
            (chess.QUEEN, board.queens),
            (chess.KING, board.kings),
        ):
            if not pieces:
                continue
            white_mg, black_mg = mg_tables[piece_type]
            white_eg, black_eg = eg_tables[piece_type]
            for square in scan(pieces & white):
                middlegame += white_mg[square]
                endgame += white_eg[square]
            for square in scan(pieces & black):
                middlegame -= black_mg[square]
                endgame -= black_eg[square]

        score = float(taper(int(middlegame), int(endgame), game_phase(board)))

        # Pawn structure, rebuilt with these penalties rather than the
        # engine's baked-in constants.
        for colour, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            pawns = board.pieces_mask(chess.PAWN, colour)
            if pawns:
                score -= sign * (
                    doubled * count_doubled_pawns(board, colour)
                    + isolated * count_isolated_pawns(board, colour)
                )
            if popcount(board.pieces_mask(chess.BISHOP, colour)) >= 2:
                score += sign * pair_bonus

            # Rooks on files the pawns have left.
            rooks = board.pieces_mask(chess.ROOK, colour)
            if rooks:
                own_pawns = board.pieces_mask(chess.PAWN, colour)
                enemy_pawns = board.pieces_mask(chess.PAWN, not colour)
                for square in scan(rooks):
                    file_mask = chess.BB_FILES[chess.square_file(square)]
                    if own_pawns & file_mask:
                        continue
                    score += sign * (open_file if not (enemy_pawns & file_mask) else semi_open_file)
        return int(score)

    return static_eval


class TunableEngine(SearchEngine):
    """Alpha-beta with an evaluation supplied from outside.

    Depth 4 by default: deep enough that the evaluation actually decides
    games, shallow enough that a few hundred self-play games fit in an
    afternoon. Every research module plays its candidates through this.
    """

    level = 5
    default_name = "Tunable"
    depth = 4

    def __init__(self, params: EvalParams | None = None, *args, **kwargs) -> None:
        kwargs.setdefault("time_limit", 5.0)
        super().__init__(*args, **kwargs)
        self.params = params or DEFAULT_PARAMS
        self._static_eval = make_static_eval(self.params)

    def static_eval(self, board: chess.Board) -> int:
        return self._static_eval(board)

    def _root_search(
        self, board: chess.Board, stats: SearchStats, root_moves: list[chess.Move]
    ) -> RootResult:
        return search_alphabeta(
            board,
            max_depth=self.depth,
            evaluate=self.static_eval,
            stats=stats,
            root_moves=root_moves,
        )
