"""Thin wrapper around ``chess.Board``.

python-chess already does the hard work; this adds the bits every layer of
the project needs — game termination in one place, PGN export with engine
names, and a move log the UI can render.
"""

from __future__ import annotations

import datetime as _dt
import io

import chess
import chess.pgn

from engine.utils.constants import BALANCE_VALUES

STARTING_FEN = chess.STARTING_FEN


class ChessGame:
    """A game in progress: board + history + result bookkeeping."""

    def __init__(self, fen: str | None = None) -> None:
        self.board = chess.Board(fen) if fen else chess.Board()
        self.start_fen = self.board.fen()
        self.moves: list[chess.Move] = []
        # Set when the game ends for a reason the board itself cannot know,
        # e.g. a resignation or a time forfeit in the tournament runner.
        self.adjudicated: str | None = None
        self.termination: str | None = None

    # --- moves ------------------------------------------------------------

    @property
    def legal_moves(self) -> list[chess.Move]:
        return list(self.board.legal_moves)

    @property
    def turn(self) -> chess.Color:
        return self.board.turn

    @property
    def ply(self) -> int:
        return len(self.moves)

    def san(self, move: chess.Move) -> str:
        """SAN for a move in the *current* position (call before pushing)."""
        return self.board.san(move)

    def push(self, move: chess.Move) -> str:
        """Play a move, returning its SAN."""
        if move not in self.board.legal_moves:
            raise ValueError(f"illegal move {move.uci()} in {self.board.fen()}")
        san = self.board.san(move)
        self.board.push(move)
        self.moves.append(move)
        return san

    def push_uci(self, uci: str) -> str:
        return self.push(chess.Move.from_uci(uci))

    def push_san(self, san: str) -> str:
        return self.push(self.board.parse_san(san))

    def pop(self) -> chess.Move | None:
        """Undo the last move."""
        if not self.moves:
            return None
        self.adjudicated = None
        self.termination = None
        self.moves.pop()
        return self.board.pop()

    def reset(self, fen: str | None = None) -> None:
        self.board = chess.Board(fen or self.start_fen)
        self.start_fen = self.board.fen()
        self.moves.clear()
        self.adjudicated = None
        self.termination = None

    # --- state ------------------------------------------------------------

    @property
    def fen(self) -> str:
        return self.board.fen()

    def is_game_over(self) -> bool:
        return self.adjudicated is not None or self.board.is_game_over(claim_draw=True)

    def result(self) -> str:
        """'1-0', '0-1', '1/2-1/2', or '*' while the game is still running."""
        if self.adjudicated is not None:
            return self.adjudicated
        return self.board.result(claim_draw=True)

    def adjudicate(self, result: str, reason: str) -> None:
        """End the game externally (resignation, forfeit, move-limit draw)."""
        if result not in ("1-0", "0-1", "1/2-1/2"):
            raise ValueError(f"invalid result {result!r}")
        self.adjudicated = result
        self.termination = reason

    def outcome_reason(self) -> str:
        """Why the game ended, in plain words."""
        if self.termination:
            return self.termination
        outcome = self.board.outcome(claim_draw=True)
        if outcome is None:
            return "in progress"
        return outcome.termination.name.lower().replace("_", " ")

    def material_balance(self) -> int:
        """Material difference in centipawns, positive = White ahead."""
        score = 0
        for piece_type, value in BALANCE_VALUES.items():
            if not value:
                continue
            score += value * len(self.board.pieces(piece_type, chess.WHITE))
            score -= value * len(self.board.pieces(piece_type, chess.BLACK))
        return score

    def move_history_san(self) -> list[str]:
        """The whole game in SAN, replayed from the start position."""
        replay = chess.Board(self.start_fen)
        out = []
        for move in self.moves:
            out.append(replay.san(move))
            replay.push(move)
        return out

    # --- PGN --------------------------------------------------------------

    def to_pgn(
        self,
        white: str = "White",
        black: str = "Black",
        event: str = "chess-bot",
        round_: str = "-",
        extra_headers: dict[str, str] | None = None,
    ) -> str:
        game = chess.pgn.Game()
        game.headers["Event"] = event
        game.headers["Site"] = "local"
        game.headers["Date"] = _dt.date.today().strftime("%Y.%m.%d")
        game.headers["Round"] = round_
        game.headers["White"] = white
        game.headers["Black"] = black
        game.headers["Result"] = self.result()
        if self.start_fen != chess.STARTING_FEN:
            game.headers["FEN"] = self.start_fen
            game.headers["SetUp"] = "1"
        if self.termination:
            game.headers["Termination"] = self.termination
        for key, value in (extra_headers or {}).items():
            game.headers[key] = value

        node: chess.pgn.GameNode = game
        for move in self.moves:
            node = node.add_variation(move)
        return str(game)

    @classmethod
    def from_pgn(cls, pgn_text: str) -> "ChessGame":
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if game is None:
            raise ValueError("could not parse PGN")
        instance = cls(game.headers.get("FEN") or None)
        for move in game.mainline_moves():
            instance.push(move)
        return instance

    def __repr__(self) -> str:
        return f"<ChessGame ply={self.ply} result={self.result()}>"
