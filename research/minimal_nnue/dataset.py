"""Building a training set out of self-play.

Two ways to label a position, and the choice matters more than the network:

* **Distillation** — label with what the engine's own evaluation says, once
  the position has been settled by a quiescence search. The question becomes
  "how small a network can reproduce this evaluation", which is answerable
  from a few thousand positions and is how real engines bootstrapped their
  first nets.
* **Outcomes** — label with how the game actually ended. A purer signal and a
  far noisier one: a single position carries one bit of information about a
  game it may have had nothing to do with, so it needs orders of magnitude
  more data.

Distillation is the default because the budget here is minutes, not weeks.
What it cannot do is exceed its teacher — a net trained this way is trying to
*be* the hand-written evaluation, cheaply, not to beat it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import chess
import numpy as np

from engine.evaluation.tapered import positional_eval
from engine.search.context import SearchStats
from engine.search.quiescence import quiescence
from research.features import (
    FULL_PLANE_DIM,
    HANDCRAFTED_DIM,
    PIECE_SQUARE_DIM,
    full_plane_vector,
    handcrafted_vector,
    phase_scalar,
    piece_square_vector,
)
from research.params import TunableEngine

VALUE_SCALE = 400.0

# Evaluations are clamped before squashing. Self-play with random exploration
# produces plenty of positions where one side is a queen and a rook up, and a
# mated position scores in the tens of thousands. Left alone those saturate
# tanh completely: every extreme position becomes the same label, the network
# spends its capacity on cases that are already decided, and the error metric
# stops meaning anything. Past about fifteen pawns the exact number has no
# bearing on how the game goes.
LABEL_CLIP_CP = 1500.0

# The four input encodings the ablation compares.
ENCODINGS: dict[str, int] = {
    "folded": PIECE_SQUARE_DIM,  # 384 — colour folded by mirroring
    "planes": FULL_PLANE_DIM,  # 768 — the classic NNUE input
    "planes+phase": FULL_PLANE_DIM + 1,
    "planes+handcrafted": FULL_PLANE_DIM + HANDCRAFTED_DIM,
}


def encode(board: chess.Board, encoding: str) -> np.ndarray:
    if encoding == "folded":
        return piece_square_vector(board)
    planes = full_plane_vector(board)
    if encoding == "planes":
        return planes
    if encoding == "planes+phase":
        return np.concatenate([planes, [np.float32(phase_scalar(board))]])
    if encoding == "planes+handcrafted":
        return np.concatenate([planes, handcrafted_vector(board) / 8.0])
    raise ValueError(f"unknown encoding {encoding!r}; expected one of {list(ENCODINGS)}")


@dataclass
class Dataset:
    """Positions and their labels, held as FENs so any encoding can be built."""

    fens: list[str]
    values: np.ndarray  # tanh-squashed, White-relative, in [-1, 1]
    centipawns: np.ndarray
    seconds: float = 0.0

    def __len__(self) -> int:
        return len(self.fens)

    def encoded(self, encoding: str) -> np.ndarray:
        """Materialise the inputs for one encoding.

        Labels are stored once and features rebuilt per encoding on purpose:
        the ablation compares encodings on *identical* positions, which a
        pre-encoded dataset could not guarantee.
        """
        return np.stack([encode(chess.Board(fen), encoding) for fen in self.fens])

    def split(self, validation: float = 0.2, seed: int = 0) -> tuple["Dataset", "Dataset"]:
        rng = np.random.default_rng(seed)
        order = rng.permutation(len(self))
        cut = int(len(self) * (1 - validation))
        train_index, validation_index = order[:cut], order[cut:]

        def take(index: np.ndarray) -> "Dataset":
            return Dataset(
                fens=[self.fens[i] for i in index],
                values=self.values[index],
                centipawns=self.centipawns[index],
            )

        return take(train_index), take(validation_index)


def settled_score(board: chess.Board) -> int:
    """The evaluation after captures are resolved, from White's point of view.

    Labelling the raw static score would teach the network to reproduce the
    engine's blind spots mid-exchange; the quiescence-settled score is what
    the search actually acts on.
    """
    score = quiescence(board, -1e9, 1e9, positional_eval, SearchStats(), ply=0)
    return int(score if board.turn == chess.WHITE else -score)


def build_dataset(
    games: int = 40,
    depth: int = 2,
    max_plies: int = 120,
    epsilon: float = 0.15,
    skip_opening_plies: int = 6,
    time_limit: float | None = 0.05,
    seed: int = 0,
    label: str = "quiescence",
    clip_cp: float = LABEL_CLIP_CP,
    on_game=None,
) -> Dataset:
    """Play games and record labelled positions from them."""
    if label not in ("quiescence", "outcome"):
        raise ValueError(f"unknown label {label!r}")

    rng = np.random.default_rng(seed)
    started = time.perf_counter()
    engine = TunableEngine(name="collector", depth=depth, seed=seed, time_limit=time_limit)

    fens: list[str] = []
    centipawns: list[float] = []
    game_starts: list[int] = []
    outcomes: list[float] = []

    for game_index in range(games):
        board = chess.Board()
        engine.new_game()
        game_starts.append(len(fens))

        while not board.is_game_over(claim_draw=True) and len(board.move_stack) < max_plies:
            result = engine.analyse(board)
            if result.move is None:
                break
            if len(board.move_stack) >= skip_opening_plies:
                # Opening positions are near-identical across games and would
                # dominate a small set with information it already has.
                fens.append(board.fen())
                centipawns.append(float(settled_score(board)))
            move = result.move
            if rng.random() < epsilon:
                legal = list(board.legal_moves)
                move = legal[int(rng.integers(len(legal)))]
            board.push(move)

        if board.is_game_over(claim_draw=True):
            outcome = {"1-0": 1.0, "0-1": -1.0, "1/2-1/2": 0.0}[board.result(claim_draw=True)]
        else:
            outcome = 0.0
        outcomes.append(outcome)
        if on_game is not None:
            on_game(game_index + 1, len(fens))

    centipawn_array = np.clip(np.array(centipawns, dtype=np.float32), -clip_cp, clip_cp).astype(
        np.float32
    )
    if label == "outcome":
        values = np.zeros(len(fens), dtype=np.float32)
        for index, start in enumerate(game_starts):
            end = game_starts[index + 1] if index + 1 < len(game_starts) else len(fens)
            values[start:end] = outcomes[index]
    else:
        values = np.tanh(centipawn_array / VALUE_SCALE).astype(np.float32)

    return Dataset(
        fens=fens,
        values=values,
        centipawns=centipawn_array,
        seconds=time.perf_counter() - started,
    )
