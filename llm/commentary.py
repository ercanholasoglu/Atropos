"""Natural-language commentary on moves and positions.

The division of labour matters more than the prompt. A language model is a
weak chess player and a good explainer, so it is never asked what the best
move is — the engine already knows, to a depth no amount of prose will beat.
What it is given is the engine's verdict, its principal variation and the
concrete facts of the position, and what it is asked for is the *why*.

Everything degrades to an empty string when no key is configured, so a
caller can render commentary unconditionally and simply get nothing.
"""

from __future__ import annotations

import chess

from engine.base_engine import SearchResult
from engine.evaluation.material import material_score
from engine.utils.helpers import format_eval, game_phase
from llm.client import ClaudeClient, LLMConfig, LLMUnavailable

SYSTEM_PROMPT = """You are a chess coach writing for an intermediate club player.

You are given an engine's evaluation of a position. Trust it completely — it \
calculates far better than you do. Your job is to explain what the engine \
sees in plain language, never to second-guess its move or its score.

Write two or three sentences. Be concrete: name squares, pieces and threats \
rather than talking about "activity" or "pressure" in the abstract. No \
preamble, no headings, no restating the move notation you were given."""


def describe_position(board: chess.Board) -> str:
    """The facts worth putting in a prompt, in a compact block."""
    material = material_score(board)
    phase = game_phase(board)
    stage = "opening" if phase >= 20 else "middlegame" if phase >= 10 else "endgame"
    lines = [
        f"FEN: {board.fen()}",
        f"To move: {'White' if board.turn == chess.WHITE else 'Black'}",
        f"Stage: {stage} (phase {phase}/24)",
        f"Material balance: {material / 100:+.1f} pawns (positive favours White)",
        f"Legal moves: {board.legal_moves.count()}",
    ]
    if board.is_check():
        lines.append("The side to move is in check.")
    return "\n".join(lines)


def describe_line(board: chess.Board, moves: list[chess.Move]) -> str:
    """A principal variation in readable SAN."""
    if not moves:
        return ""
    replay = board.copy(stack=False)
    try:
        return replay.variation_san(moves)
    except ValueError:
        return ""


class ChessCommentator:
    """Explains what the engine found, in words."""

    def __init__(
        self,
        client: ClaudeClient | None = None,
        api_key: str | None = None,
        config: LLMConfig | None = None,
    ) -> None:
        self.client = client or ClaudeClient(api_key, config)
        # Commentary is requested per move and pages rerun freely; without a
        # cache a Streamlit rerun would pay for the same sentence twice.
        self._cache: dict[tuple, str] = {}

    @property
    def available(self) -> bool:
        return self.client.available

    def _ask(self, key: tuple, prompt: str) -> str:
        if not self.available:
            return ""
        if key in self._cache:
            return self._cache[key]
        try:
            answer = self.client.complete(prompt, system=SYSTEM_PROMPT)
        except LLMUnavailable:
            return ""
        self._cache[key] = answer
        return answer

    # --- the three things it is asked for ---------------------------------

    def explain_move(
        self,
        board: chess.Board,
        move: chess.Move,
        evaluation_before: float,
        evaluation_after: float,
        search: SearchResult | None = None,
    ) -> str:
        """Explain a move that has *not* yet been played on ``board``."""
        if move not in board.legal_moves:
            raise ValueError(f"{move.uci()} is not legal in {board.fen()}")

        san = board.san(move)
        swing = evaluation_after - evaluation_before
        after = board.copy(stack=False)
        after.push(move)

        details = [
            describe_position(board),
            f"Move played: {san}",
            f"Evaluation before: {format_eval(evaluation_before)}",
            f"Evaluation after: {format_eval(evaluation_after)}",
            f"Change: {swing / 100:+.2f} pawns from White's point of view",
        ]
        if search is not None and search.pv:
            line = describe_line(board, search.pv)
            if line:
                details.append(f"Engine's main line: {line} (depth {search.depth})")
        if after.is_checkmate():
            details.append("This move is checkmate.")
        elif after.is_check():
            details.append("This move gives check.")
        if board.is_capture(move):
            details.append("This move is a capture.")

        prompt = (
            "\n".join(details)
            + "\n\nExplain this move: what it threatens or prevents, and why the "
            "evaluation moved the way it did."
        )
        return self._ask(("move", board.fen(), move.uci()), prompt)

    def analyze_position(self, board: chess.Board, search: SearchResult | None = None) -> str:
        """Describe who stands better and why."""
        details = [describe_position(board)]
        if search is not None:
            details.append(
                f"Engine evaluation: {format_eval(search.score)} at depth {search.depth}"
            )
            line = describe_line(board, search.pv)
            if line:
                details.append(f"Engine's main line: {line}")

        prompt = (
            "\n".join(details) + "\n\nDescribe this position: who is better, by how much, and what "
            "the concrete reason is."
        )
        return self._ask(("position", board.fen()), prompt)

    def suggest_plan(self, board: chess.Board, search: SearchResult | None = None) -> str:
        """Suggest what the side to move should be trying to do."""
        details = [describe_position(board)]
        if search is not None:
            line = describe_line(board, search.pv)
            if line:
                details.append(f"Engine's main line: {line}")

        side = "White" if board.turn == chess.WHITE else "Black"
        prompt = (
            "\n".join(details) + f"\n\nWhat is {side}'s plan here? Name the squares and pieces "
            "involved, and what to do about the opponent's best answer."
        )
        return self._ask(("plan", board.fen()), prompt)
