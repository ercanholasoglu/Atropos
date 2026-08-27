"""TDLeaf(λ): learning an evaluation from self-play, with no external data.

Temporal-difference learning asks the evaluation to agree with itself one
move later, and anchors the whole chain to the game's actual result. Nothing
but the rules is needed — no engine to imitate, no labelled positions.

Two details separate a version that works from one that does not:

* **TDLeaf, not TD.** The score a search reports belongs to the leaf at the
  end of its principal variation, not to the position at the root. Updating
  the root's features would train the evaluation on positions the search
  never actually evaluated. Walking the PV and updating *there* is what
  Baxter's KnightCap work called TDLeaf(λ), and it is the difference between
  learning and drifting.
* **Exploration.** Self-play between two copies of a deterministic engine
  replays the same handful of games forever. A small chance of a random move
  keeps the trajectories varied enough to learn from.

The value is squashed through ``tanh`` so that it lives on the same scale as
the thing it is anchored to — the game result, which is +1, 0 or −1.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import chess
import numpy as np

from engine.search.alphabeta import search_alphabeta
from engine.search.context import SearchStats
from research.features import PIECE_SQUARE_DIM, PIECE_TYPES, piece_square_vector, pst_weights

# Centipawns per unit of value. 400 is the Elo curve's scale, which puts a
# four-pawn advantage close to a certain win — about right for chess.
VALUE_SCALE = 400.0


def _material_weights() -> np.ndarray:
    """Piece values spread flat over every square, with no placement bonus."""
    return (pst_weights(include_material=True) - pst_weights(include_material=False)).astype(
        np.float64
    )


class PieceSquareEvaluator:
    """A piece-square table held as a learnable vector.

    Keeps two views of the same 384 numbers: a numpy vector for learning, and
    folded per-colour lookup tables for searching. Searching through numpy
    would cost more per leaf than the whole rest of the evaluation.
    """

    def __init__(self, weights: np.ndarray | None = None) -> None:
        self.weights = (
            np.zeros(PIECE_SQUARE_DIM, dtype=np.float64)
            if weights is None
            else np.asarray(weights, dtype=np.float64).copy()
        )
        self._rebuild()

    @classmethod
    def from_engine_tables(cls) -> "PieceSquareEvaluator":
        """Start from the hand-written tables rather than from nothing."""
        return cls(pst_weights().astype(np.float64))

    @classmethod
    def material_only(cls) -> "PieceSquareEvaluator":
        """Piece values, flat placement — the useful starting point.

        Learning from all-zero weights sounds purer and does not work: an
        evaluation that scores every position at zero plays randomly, random
        games almost never finish decisively inside a move limit, and a run of
        draws carries no gradient at all. Seeding the material and leaving
        placement at zero fixes the cold start and sharpens the question to
        one self-play can actually answer — *can it rediscover where the
        pieces belong?*
        """
        return cls(_material_weights())

    def _rebuild(self) -> None:
        """Fold the weight vector into the tables the search reads."""
        self._tables: dict[int, tuple[list[float], list[float]]] = {}
        for index, piece_type in enumerate(PIECE_TYPES):
            base = index * 64
            white = [float(self.weights[base + square]) for square in range(64)]
            # Black's pieces enter the feature vector mirrored and negated.
            black = [float(self.weights[base + (square ^ 56)]) for square in range(64)]
            self._tables[piece_type] = (white, black)

    def set_weights(self, weights: np.ndarray) -> None:
        self.weights = np.asarray(weights, dtype=np.float64).copy()
        self._rebuild()

    def static_eval(self, board: chess.Board) -> int:
        """Centipawns, White-relative — the fast path used inside search."""
        total = 0.0
        scan = chess.scan_forward
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
            white_table, black_table = self._tables[piece_type]
            for square in scan(pieces & white):
                total += white_table[square]
            for square in scan(pieces & black):
                total -= black_table[square]
        return int(total)

    def value(self, board: chess.Board) -> float:
        """The squashed value in [-1, 1], from White's point of view."""
        return float(np.tanh(self.static_eval(board) / VALUE_SCALE))

    def piece_means(self) -> dict[str, float]:
        """Average weight per piece type — the learned "value" of a piece."""
        names = ("pawn", "knight", "bishop", "rook", "queen", "king")
        return {
            name: float(np.mean(self.weights[index * 64 : (index + 1) * 64]))
            for index, name in enumerate(names)
        }


@dataclass
class TDConfig:
    games: int = 20
    depth: int = 3
    lam: float = 0.7
    learning_rate: float = 20.0  # centipawns per unit of TD error
    epsilon: float = 0.12  # chance of a random move, for exploration
    max_plies: int = 120
    time_limit: float | None = 0.2
    weight_clip: float = 2000.0
    seed: int = 0


@dataclass
class GameTrace:
    """One self-play game, reduced to what the learner needs."""

    features: list[np.ndarray]
    values: list[float]
    outcome: float  # +1 White won, 0 draw, -1 Black won
    plies: int
    reason: str


@dataclass
class TrainingResult:
    evaluator: PieceSquareEvaluator
    td_errors: list[float] = field(default_factory=list)
    outcomes: list[float] = field(default_factory=list)
    piece_means: list[dict[str, float]] = field(default_factory=list)
    seconds: float = 0.0

    def table(self) -> str:
        header = f"{'game':>5} {'|TD|':>8} {'result':>7}   piece means (P/N/B/R/Q)"
        lines = [header, "-" * (len(header) + 6)]
        for index, (error, outcome, means) in enumerate(
            zip(self.td_errors, self.outcomes, self.piece_means), start=1
        ):
            values = "/".join(
                f"{means[name]:.0f}" for name in ("pawn", "knight", "bishop", "rook", "queen")
            )
            lines.append(f"{index:>5} {error:>8.4f} {outcome:>7.1f}   {values}")
        return "\n".join(lines)


class ValueLearner:
    """Plays itself and updates the evaluation from what happens."""

    def __init__(
        self,
        evaluator: PieceSquareEvaluator | None = None,
        config: TDConfig | None = None,
    ) -> None:
        self.evaluator = evaluator or PieceSquareEvaluator()
        self.config = config or TDConfig()
        self.rng = np.random.default_rng(self.config.seed)

    # --- playing ----------------------------------------------------------

    def _pv_leaf(self, board: chess.Board) -> tuple[chess.Move | None, chess.Board]:
        """Search, then return the move and the board at the end of the PV.

        The leaf is the position the score actually describes, so it is the
        one the update belongs to.
        """
        stats = SearchStats(time_limit=self.config.time_limit)
        result = search_alphabeta(board, self.config.depth, self.evaluator.static_eval, stats=stats)
        leaf = board.copy(stack=False)
        for move in result.pv:
            if move in leaf.legal_moves:
                leaf.push(move)
        return result.move, leaf

    def play_game(self) -> GameTrace:
        board = chess.Board()
        features: list[np.ndarray] = []
        values: list[float] = []
        reason = "in progress"

        while (
            not board.is_game_over(claim_draw=True)
            and len(board.move_stack) < self.config.max_plies
        ):
            move, leaf = self._pv_leaf(board)
            if move is None:
                break
            features.append(piece_square_vector(leaf).astype(np.float64))
            values.append(self.evaluator.value(leaf))

            if self.rng.random() < self.config.epsilon:
                legal = list(board.legal_moves)
                move = legal[int(self.rng.integers(len(legal)))]
            board.push(move)

        if board.is_game_over(claim_draw=True):
            result = board.result(claim_draw=True)
            outcome = {"1-0": 1.0, "0-1": -1.0, "1/2-1/2": 0.0}[result]
            outcome_obj = board.outcome(claim_draw=True)
            reason = (
                outcome_obj.termination.name.lower().replace("_", " ") if outcome_obj else result
            )
        else:
            outcome = 0.0
            reason = "move limit"

        return GameTrace(
            features=features,
            values=values,
            outcome=outcome,
            plies=len(board.move_stack),
            reason=reason,
        )

    # --- learning ---------------------------------------------------------

    def update(self, trace: GameTrace) -> float:
        """One TDLeaf(λ) sweep over a finished game. Returns the mean |δ|.

        The trace is walked backwards so each position's eligibility is the
        λ-discounted sum of every temporal difference that follows it — the
        same quantity as forward eligibility traces, without carrying a
        384-wide accumulator through the game.
        """
        if not trace.features:
            return 0.0

        config = self.config
        values = trace.values
        deltas = [values[index + 1] - values[index] for index in range(len(values) - 1)]
        # The last position is anchored to what actually happened.
        deltas.append(trace.outcome - values[-1])

        gradient = np.zeros_like(self.evaluator.weights)
        eligibility = 0.0
        for index in range(len(values) - 1, -1, -1):
            eligibility = deltas[index] + config.lam * eligibility
            # d/dw tanh(w·φ / S) = (1 - v²)/S · φ; the 1/S is folded into the
            # learning rate, which is therefore quoted in centipawns.
            gradient += eligibility * (1.0 - values[index] ** 2) * trace.features[index]

        weights = self.evaluator.weights + config.learning_rate * gradient / len(values)
        np.clip(weights, -config.weight_clip, config.weight_clip, out=weights)
        self.evaluator.set_weights(weights)
        return float(np.mean(np.abs(deltas)))

    def train(self, on_game=None) -> TrainingResult:
        started = time.perf_counter()
        result = TrainingResult(evaluator=self.evaluator)
        for game_index in range(self.config.games):
            trace = self.play_game()
            error = self.update(trace)
            result.td_errors.append(error)
            result.outcomes.append(trace.outcome)
            result.piece_means.append(self.evaluator.piece_means())
            if on_game is not None:
                on_game(game_index + 1, trace, error)
        result.seconds = time.perf_counter() - started
        return result
