"""Level 2 — Material (~600 Elo).

One ply of lookahead over a pure material count. It sees mate in one and
takes free material, but because it never looks at the *reply* it will just
as happily take a defended pawn with its queen. That blind spot is the point:
it is what separates this level from Level 3's real search.
"""

from __future__ import annotations

import math
import time

import chess

from engine.base_engine import BaseEngine, SearchResult
from engine.evaluation.material import evaluate_material


class Level2Material(BaseEngine):
    level = 2
    default_name = "L2-Material"

    def get_best_move(self, board: chess.Board) -> chess.Move:
        move, _ = self._best(board)
        return move

    def evaluate(self, board: chess.Board) -> float:
        return float(evaluate_material(board))

    def analyse(self, board: chess.Board) -> SearchResult:
        start = time.perf_counter()
        move, score = self._best(board)
        result = SearchResult(
            move=move,
            score=score,
            depth=1,
            nodes=self.nodes,
            time_ms=(time.perf_counter() - start) * 1000,
            pv=[move],
        )
        self.last_result = result
        return result

    def _best(self, board: chess.Board) -> tuple[chess.Move, float]:
        """Best move and its score, from one ply of material lookahead."""
        moves = list(board.legal_moves)
        if not moves:
            raise ValueError("no legal moves — the game is already over")

        white_to_move = board.turn == chess.WHITE
        best_score = -math.inf if white_to_move else math.inf
        best_moves: list[chess.Move] = []

        for move in moves:
            board.push(move)
            # ply=1: this position is one move deeper than the root, so a mate
            # found here scores slightly below a mate found at the root.
            score = float(evaluate_material(board, ply=1))
            board.pop()

            if score == best_score:
                best_moves.append(move)
            elif (score > best_score) if white_to_move else (score < best_score):
                best_score, best_moves = score, [move]

        self.nodes = len(moves)
        # Equal-scoring moves are genuinely equal to this engine. Breaking the
        # tie randomly keeps it from shuffling the same two pieces forever.
        return self.rng.choice(best_moves), best_score
