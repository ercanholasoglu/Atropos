"""Position analysis that pairs the engine's numbers with an explanation.

The engine says *what* and how much; the commentator says *why*. This module
runs both and hands back one object, so a page or a notebook does not have to
know that two very different systems produced it.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from engine.base_engine import BaseEngine, SearchResult
from engine.levels import create_engine
from engine.utils.helpers import format_eval
from llm.commentary import ChessCommentator


@dataclass
class PositionAnalysis:
    """One position, seen by both halves of the system."""

    fen: str
    best_move_san: str
    evaluation: float
    depth: int
    nodes: int
    line_san: str
    explanation: str = ""
    plan: str = ""

    @property
    def evaluation_text(self) -> str:
        return format_eval(self.evaluation)

    @property
    def has_commentary(self) -> bool:
        return bool(self.explanation or self.plan)


def analyse_position(
    board: chess.Board,
    engine: BaseEngine | None = None,
    commentator: ChessCommentator | None = None,
    level: int = 6,
    time_limit: float = 2.0,
    want_plan: bool = True,
) -> PositionAnalysis:
    """Search a position, then explain it if a commentator is available."""
    if board.is_game_over():
        raise ValueError("the game is already over — there is nothing to analyse")

    engine = engine or create_engine(level, seed=1, time_limit=time_limit)
    result: SearchResult = engine.analyse(board.copy(stack=False))

    line = ""
    if result.pv:
        replay = board.copy(stack=False)
        try:
            line = replay.variation_san(result.pv)
        except ValueError:
            line = ""

    analysis = PositionAnalysis(
        fen=board.fen(),
        best_move_san=board.san(result.move) if result.move else "—",
        evaluation=result.score,
        depth=result.depth,
        nodes=result.nodes,
        line_san=line,
    )

    if commentator is not None and commentator.available:
        analysis.explanation = commentator.analyze_position(board, result)
        if want_plan:
            analysis.plan = commentator.suggest_plan(board, result)
    return analysis
