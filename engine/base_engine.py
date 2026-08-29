"""Abstract base class every engine level inherits from.

Score convention (used everywhere in this project):
    * Scores are centipawns.
    * ``evaluate()`` and ``SearchResult.score`` are always from **White's**
      perspective: positive means White is better.
    * Search internals (negamax) work from the side-to-move's perspective and
      convert at the boundary. Only the boundary is public.
"""

from __future__ import annotations

import random
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

import chess

from engine.utils.constants import INITIAL_ELO, LEVEL_NAMES


@dataclass
class SearchResult:
    """What an engine returns when it thinks about a position."""

    move: chess.Move | None
    score: float = 0.0  # centipawns, White's perspective
    depth: int = 0
    nodes: int = 0
    time_ms: float = 0.0
    pv: list[chess.Move] = field(default_factory=list)

    @property
    def nps(self) -> float:
        """Nodes per second."""
        return self.nodes / (self.time_ms / 1000) if self.time_ms > 0 else 0.0


class BaseEngine(ABC):
    """Abstract base class for all engine levels."""

    level: int = 0
    default_name: str = "Engine"

    def __init__(
        self,
        name: str | None = None,
        level: int | None = None,
        initial_elo: int | None = None,
        seed: int | None = None,
        time_limit: float | None = None,
    ) -> None:
        # Set from outside to interrupt a running search — this is the path a
        # UCI `stop` takes to reach a search already in flight.
        self.stop_event: threading.Event | None = None
        self.node_limit: int | None = None
        # Whether that budget may stop a search mid-iteration. See
        # SearchStats.node_limit_hard.
        self.node_limit_hard: bool = True
        # Called with (RootResult, SearchStats, board) after every completed
        # iteration, so a caller can stream `info` lines while thinking.
        self.on_iteration: Callable[..., None] | None = None
        self.level = level if level is not None else type(self).level
        self.name = name or self.default_name or LEVEL_NAMES.get(self.level, "Engine")
        self.elo = float(
            initial_elo if initial_elo is not None else INITIAL_ELO.get(self.level, 1000)
        )
        self.games_played = 0
        # Seeded RNG so tournaments are reproducible; every level uses this
        # one instead of the global `random` module.
        self.rng = random.Random(seed)
        self.time_limit = time_limit
        self.nodes = 0
        self.last_result: SearchResult | None = None

    # --- required by every level -----------------------------------------

    @abstractmethod
    def get_best_move(self, board: chess.Board) -> chess.Move:
        """Return the best move for the current position."""

    @abstractmethod
    def evaluate(self, board: chess.Board) -> float:
        """Evaluate the position in centipawns, from White's perspective."""

    # --- shared behaviour -------------------------------------------------

    def analyse(self, board: chess.Board) -> SearchResult:
        """Pick a move and report how it was found.

        The default wraps :meth:`get_best_move` with timing and a post-move
        evaluation. Levels that search deeply override this to report their
        real score, depth and principal variation.
        """
        self.nodes = 0
        start = time.perf_counter()
        move = self.get_best_move(board)
        elapsed = (time.perf_counter() - start) * 1000

        score = 0.0
        if move is not None:
            board.push(move)
            score = self.evaluate(board)
            board.pop()

        result = SearchResult(
            move=move,
            score=score,
            depth=1,
            nodes=self.nodes,
            time_ms=elapsed,
            pv=[move] if move else [],
        )
        self.last_result = result
        return result

    def new_game(self) -> None:
        """Reset per-game state. Levels with a TT / killers clear them here."""
        self.nodes = 0
        self.last_result = None

    def get_info(self) -> dict:
        """Engine info (also the shape the UI and UCI bridge consume)."""
        return {
            "name": self.name,
            "level": self.level,
            "elo": round(self.elo, 1),
            "games_played": self.games_played,
        }

    def __repr__(self) -> str:
        return f"<{type(self).__name__} L{self.level} '{self.name}' elo={self.elo:.0f}>"
