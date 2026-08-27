"""Parsing the UCI protocol.

UCI is a line protocol with no framing and no error replies — a GUI sends a
line, and an engine that does not understand it is expected to ignore it and
carry on. That shapes everything here: parsing never raises, unknown tokens
are skipped rather than rejected, and a malformed number leaves its field
unset instead of failing the command. A crash on a stray token is a lost
game; a skipped token is usually nothing at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import chess


@dataclass(frozen=True)
class Command:
    """One protocol line, split into a name and the rest."""

    name: str
    args: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        return " ".join((self.name, *self.args)).strip()


def parse_command(line: str) -> Command | None:
    """Split a line, or ``None`` if it holds nothing."""
    tokens = line.strip().split()
    return Command(tokens[0], tuple(tokens[1:])) if tokens else None


@dataclass
class GoParams:
    """Everything ``go`` can ask for.

    All optional, and mutually contradictory combinations are possible —
    ``go infinite depth 8`` is legal and means "search depth 8 but do not stop
    until told". The engine decides what to honour; parsing just records.
    """

    depth: int | None = None
    nodes: int | None = None
    movetime: float | None = None  # seconds
    wtime: float | None = None
    btime: float | None = None
    winc: float = 0.0
    binc: float = 0.0
    movestogo: int | None = None
    mate: int | None = None
    infinite: bool = False
    ponder: bool = False
    searchmoves: list[chess.Move] = field(default_factory=list)

    @property
    def has_clock(self) -> bool:
        return self.wtime is not None or self.btime is not None


_INT_FIELDS = {"depth", "nodes", "movestogo", "mate"}
_MS_FIELDS = {"movetime", "wtime", "btime", "winc", "binc"}


def parse_go(args: tuple[str, ...] | list[str]) -> GoParams:
    """Read a ``go`` argument list.

    ``searchmoves`` swallows everything after it until the next keyword,
    which is why it is handled by lookahead rather than by position.
    """
    params = GoParams()
    tokens = list(args)
    index = 0
    keywords = _INT_FIELDS | _MS_FIELDS | {"infinite", "ponder", "searchmoves"}

    while index < len(tokens):
        token = tokens[index].lower()
        if token == "infinite":
            params.infinite = True
            index += 1
        elif token == "ponder":
            params.ponder = True
            index += 1
        elif token == "searchmoves":
            index += 1
            while index < len(tokens) and tokens[index].lower() not in keywords:
                try:
                    params.searchmoves.append(chess.Move.from_uci(tokens[index]))
                except ValueError:
                    pass  # a GUI typo is not worth failing the search over
                index += 1
        elif token in keywords and index + 1 < len(tokens):
            value = _to_int(tokens[index + 1])
            if value is not None:
                if token in _MS_FIELDS:
                    setattr(params, token, value / 1000.0)
                else:
                    setattr(params, token, value)
            index += 2
        else:
            index += 1  # unknown token: skip it, as the protocol expects
    return params


@dataclass
class PositionCommand:
    """The board a ``position`` line describes."""

    fen: str
    moves: list[chess.Move] = field(default_factory=list)

    def board(self) -> chess.Board:
        """Build the position, stopping at the first move that is not legal.

        A GUI should never send an illegal move, but taking one on faith
        corrupts the board for the rest of the game; stopping leaves a legal
        position the engine can still play from.
        """
        board = chess.Board(self.fen)
        for move in self.moves:
            if move not in board.legal_moves:
                break
            board.push(move)
        return board


def parse_position(args: tuple[str, ...] | list[str]) -> PositionCommand | None:
    """Read a ``position`` line: ``startpos`` or ``fen ...``, then ``moves``."""
    tokens = list(args)
    if not tokens:
        return None

    moves_index = next((i for i, token in enumerate(tokens) if token.lower() == "moves"), None)
    head = tokens[:moves_index] if moves_index is not None else tokens
    tail = tokens[moves_index + 1 :] if moves_index is not None else []

    if head and head[0].lower() == "startpos":
        fen = chess.STARTING_FEN
    elif head and head[0].lower() == "fen":
        # A FEN is six fields, but GUIs truncate the last two often enough
        # that rebuilding from whatever arrived is the practical choice.
        fen = " ".join(head[1:])
        if not fen:
            return None
    else:
        return None

    try:
        chess.Board(fen)
    except ValueError:
        return None

    moves = []
    for token in tail:
        try:
            moves.append(chess.Move.from_uci(token))
        except ValueError:
            break
    return PositionCommand(fen=fen, moves=moves)


def format_score(score: float, mate_threshold: int) -> str:
    """A score in the two forms UCI accepts: centipawns or mate distance."""
    if abs(score) >= mate_threshold:
        from engine.utils.constants import MATE_SCORE

        plies = MATE_SCORE - abs(score)
        moves = int((plies + 1) // 2)
        return f"mate {moves if score > 0 else -moves}"
    return f"cp {int(score)}"


def _to_int(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None
