"""Running a single game, and a match between two engines.

Everything above this — round-robin, Swiss, gauntlet, the Elo tracker, the
Streamlit "watch" page — is built out of :func:`play_game`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import chess

from engine.base_engine import BaseEngine, SearchResult
from engine.board import ChessGame
from engine.utils.helpers import result_to_score
from tournament.openings import Opening

# Called after every move with (game, engine, search result). The UI uses it
# to redraw the board; tests and scripts ignore it.
MoveHook = Callable[[ChessGame, BaseEngine, SearchResult], None]

DEFAULT_MAX_PLIES = 300


@dataclass
class GameRecord:
    """One finished game."""

    white: str
    black: str
    result: str
    reason: str
    plies: int
    pgn: str
    opening: str = "Start"
    nodes: int = 0
    time_ms: float = 0.0

    @property
    def white_score(self) -> float:
        return result_to_score(self.result)

    @property
    def decisive(self) -> bool:
        return self.result != "1/2-1/2"


def play_game(
    white: BaseEngine,
    black: BaseEngine,
    start_fen: str | None = None,
    max_plies: int = DEFAULT_MAX_PLIES,
    on_move: MoveHook | None = None,
    event: str = "chess-bot",
    round_: str = "-",
    opening: str = "Start",
) -> GameRecord:
    """Play one game to completion.

    A game that reaches ``max_plies`` is adjudicated a draw — without it two
    material-only engines will shuffle at each other indefinitely.
    """
    game = ChessGame(start_fen)
    white.new_game()
    black.new_game()
    nodes = 0
    time_ms = 0.0

    while not game.is_game_over():
        if game.ply >= max_plies:
            game.adjudicate("1/2-1/2", "move limit")
            break
        engine = white if game.turn == chess.WHITE else black
        result = engine.analyse(game.board)
        if result.move is None:
            raise RuntimeError(f"{engine.name} returned no move in {game.fen}")
        nodes += result.nodes
        time_ms += result.time_ms
        game.push(result.move)
        if on_move is not None:
            on_move(game, engine, result)

    return GameRecord(
        white=white.name,
        black=black.name,
        result=game.result(),
        reason=game.outcome_reason(),
        plies=game.ply,
        pgn=game.to_pgn(white=white.name, black=black.name, event=event, round_=round_),
        opening=opening,
        nodes=nodes,
        time_ms=time_ms,
    )


@dataclass
class MatchResult:
    """The outcome of a multi-game match, from engine A's point of view."""

    engine_a: str
    engine_b: str
    wins: int = 0
    losses: int = 0
    draws: int = 0
    games: list[GameRecord] = field(default_factory=list)

    @property
    def played(self) -> int:
        return self.wins + self.losses + self.draws

    @property
    def score(self) -> float:
        """Points per game for A: 1 per win, 0.5 per draw."""
        return (self.wins + 0.5 * self.draws) / self.played if self.played else 0.0

    def summary(self) -> str:
        return (
            f"{self.engine_a} vs {self.engine_b}: "
            f"+{self.wins} ={self.draws} -{self.losses} ({self.score:.1%})"
        )


def play_match(
    engine_a: BaseEngine,
    engine_b: BaseEngine,
    openings: list[Opening] | None = None,
    games: int | None = None,
    max_plies: int = DEFAULT_MAX_PLIES,
    on_move: MoveHook | None = None,
) -> MatchResult:
    """Play a match, alternating colours.

    Each opening is played twice — once with A as White, once as Black — so
    neither engine gets the first-move advantage more often than the other.
    With no opening book the games all start from the initial position.
    """
    from tournament.openings import STARTING_OPENING

    lines = openings if openings is not None else [STARTING_OPENING]
    total = games if games is not None else len(lines) * 2

    match = MatchResult(engine_a=engine_a.name, engine_b=engine_b.name)
    for i in range(total):
        opening = lines[(i // 2) % len(lines)]
        a_is_white = i % 2 == 0
        white, black = (engine_a, engine_b) if a_is_white else (engine_b, engine_a)

        record = play_game(
            white,
            black,
            start_fen=opening.fen or None,
            max_plies=max_plies,
            on_move=on_move,
            round_=str(i + 1),
            opening=opening.name,
        )
        match.games.append(record)

        a_score = record.white_score if a_is_white else 1 - record.white_score
        if a_score == 1.0:
            match.wins += 1
        elif a_score == 0.0:
            match.losses += 1
        else:
            match.draws += 1
    return match
