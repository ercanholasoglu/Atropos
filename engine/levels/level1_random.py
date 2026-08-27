"""Level 1 — Random (~200 Elo).

Picks a uniformly random legal move. No evaluation, no lookahead. This is the
floor of the ladder and the sanity check for everything else: any level that
cannot beat it convincingly is broken.
"""

from __future__ import annotations

import chess

from engine.base_engine import BaseEngine


class Level1Random(BaseEngine):
    level = 1
    default_name = "L1-Random"

    def get_best_move(self, board: chess.Board) -> chess.Move:
        moves = list(board.legal_moves)
        if not moves:
            raise ValueError("no legal moves — the game is already over")
        self.nodes = len(moves)
        return self.rng.choice(moves)

    def evaluate(self, board: chess.Board) -> float:
        """Level 1 has no notion of good or bad; every position is equal."""
        return 0.0
