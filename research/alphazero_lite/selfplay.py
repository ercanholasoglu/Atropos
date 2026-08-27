"""Self-play and training: the loop that makes the network better than itself.

Each iteration does two things. It plays games in which every move is chosen
by a tree search *guided* by the current network — and a search of 400
simulations plays better than the network's raw opinion. Then it trains the
network to predict what that search decided, and what the games came to. The
network chases its own search; the search, being built on a better network,
pulls further ahead. That is the entire idea.

Two targets per position:

* **policy** — the visit distribution the search arrived at, not the priors
  the network proposed. The gap between them is the improvement.
* **value** — how the game actually ended, from that position's point of view.

The budget is the honest constraint here. At roughly half a second per move
this machine produces a game every forty seconds on one core. AlphaZero used
forty million games; a day here is a few thousand. The network is sized for
that, and the module is written to make the experiment runnable rather than
to reproduce the paper.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import chess
import numpy as np

from research.alphazero_lite.encoding import POLICY_SIZE, encode_board, move_index
from research.alphazero_lite.mcts import MCTS, MCTSConfig
from research.alphazero_lite.network import Evaluator, NetworkConfig, build_network


@dataclass
class SelfPlayConfig:
    games: int = 10
    max_plies: int = 120
    simulations: int = 100
    seed: int = 0


@dataclass
class TrainConfig:
    iterations: int = 3
    epochs: int = 4
    batch_size: int = 64
    learning_rate: float = 2e-3
    value_weight: float = 1.0
    buffer_size: int = 20_000
    device: str = "cpu"


@dataclass
class Example:
    """One training position."""

    planes: np.ndarray
    policy: np.ndarray
    value: float


@dataclass
class GameSummary:
    plies: int
    result: str
    reason: str
    seconds: float
    evaluations: int


@dataclass
class IterationReport:
    iteration: int
    games: list[GameSummary] = field(default_factory=list)
    examples: int = 0
    policy_loss: float = 0.0
    value_loss: float = 0.0
    seconds: float = 0.0

    @property
    def decisive_rate(self) -> float:
        if not self.games:
            return 0.0
        return sum(1 for game in self.games if game.result != "1/2-1/2") / len(self.games)


@dataclass
class TrainingReport:
    iterations: list[IterationReport] = field(default_factory=list)

    def table(self) -> str:
        header = f"{'iter':>5} {'games':>6} {'examples':>9} {'policy':>9} {'value':>8} {'decisive':>9} {'time':>8}"
        lines = [header, "-" * len(header)]
        for report in self.iterations:
            lines.append(
                f"{report.iteration:>5} {len(report.games):>6} {report.examples:>9} "
                f"{report.policy_loss:>9.4f} {report.value_loss:>8.4f} "
                f"{report.decisive_rate:>8.0%} {report.seconds:>7.1f}s"
            )
        return "\n".join(lines)


def policy_target(visits: dict[chess.Move, int], board: chess.Board) -> np.ndarray:
    """The search's visit distribution as a policy-width vector."""
    target = np.zeros(POLICY_SIZE, dtype=np.float32)
    total = sum(visits.values())
    if total == 0:
        return target
    flip = board.turn == chess.BLACK
    for move, count in visits.items():
        target[move_index(move, flip)] = count / total
    return target


def play_self_play_game(mcts: MCTS, max_plies: int = 120) -> tuple[list[Example], GameSummary]:
    """One game, recording what the search decided at every move."""
    started = time.perf_counter()
    board = chess.Board()
    pending: list[tuple[np.ndarray, np.ndarray, chess.Color]] = []
    evaluations = 0

    while not board.is_game_over(claim_draw=True) and len(board.move_stack) < max_plies:
        _, visits = mcts.search(board)
        evaluations += mcts.stats.evaluations
        pending.append((encode_board(board), policy_target(visits, board), board.turn))
        board.push(mcts.select_move(visits, ply=len(board.move_stack)))

    if board.is_game_over(claim_draw=True):
        result = board.result(claim_draw=True)
        outcome = board.outcome(claim_draw=True)
        reason = outcome.termination.name.lower().replace("_", " ") if outcome else result
    else:
        result, reason = "1/2-1/2", "move limit"

    white_score = {"1-0": 1.0, "0-1": -1.0, "1/2-1/2": 0.0}[result]
    examples = [
        # The value target is the outcome seen by whoever was to move.
        Example(planes, policy, white_score if colour == chess.WHITE else -white_score)
        for planes, policy, colour in pending
    ]
    return examples, GameSummary(
        plies=len(board.move_stack),
        result=result,
        reason=reason,
        seconds=time.perf_counter() - started,
        evaluations=evaluations,
    )


class AlphaZeroLite:
    """The self-play / train loop, small enough to run on a laptop."""

    def __init__(
        self,
        network=None,
        network_config: NetworkConfig | None = None,
        mcts_config: MCTSConfig | None = None,
        selfplay_config: SelfPlayConfig | None = None,
        train_config: TrainConfig | None = None,
    ) -> None:
        self.train_config = train_config or TrainConfig()
        self.selfplay_config = selfplay_config or SelfPlayConfig()
        self.mcts_config = mcts_config or MCTSConfig(simulations=self.selfplay_config.simulations)
        self.network = network or build_network(network_config)
        self.evaluator = Evaluator(self.network, device=self.train_config.device)
        self.buffer: list[Example] = []

    # --- self play --------------------------------------------------------

    def generate(self, iteration: int) -> tuple[list[Example], list[GameSummary]]:
        examples: list[Example] = []
        summaries: list[GameSummary] = []
        for game_index in range(self.selfplay_config.games):
            mcts = MCTS(
                self.evaluator,
                self.mcts_config,
                seed=self.selfplay_config.seed + iteration * 1000 + game_index,
            )
            game_examples, summary = play_self_play_game(mcts, self.selfplay_config.max_plies)
            examples.extend(game_examples)
            summaries.append(summary)
        return examples, summaries

    # --- training ---------------------------------------------------------

    def train_on_buffer(self) -> tuple[float, float]:
        """Fit the network to the search's decisions. Returns the two losses."""
        import torch

        config = self.train_config
        if not self.buffer:
            return 0.0, 0.0

        device = config.device
        planes = torch.from_numpy(np.stack([e.planes for e in self.buffer])).to(device)
        policies = torch.from_numpy(np.stack([e.policy for e in self.buffer])).to(device)
        values = torch.from_numpy(
            np.array([e.value for e in self.buffer], dtype=np.float32).reshape(-1, 1)
        ).to(device)

        self.network.to(device).train()
        optimiser = torch.optim.Adam(self.network.parameters(), lr=config.learning_rate)

        policy_loss = value_loss = 0.0
        for _ in range(config.epochs):
            order = torch.randperm(planes.shape[0], device=device)
            for start in range(0, planes.shape[0], config.batch_size):
                index = order[start : start + config.batch_size]
                optimiser.zero_grad()
                logits, predicted = self.network(planes[index])

                # Cross-entropy against a full distribution, not a label: the
                # search's uncertainty is part of what is being taught.
                log_probabilities = torch.log_softmax(logits, dim=1)
                p_loss = -(policies[index] * log_probabilities).sum(dim=1).mean()
                v_loss = torch.nn.functional.mse_loss(predicted, values[index])
                (p_loss + config.value_weight * v_loss).backward()
                optimiser.step()
                policy_loss, value_loss = float(p_loss.item()), float(v_loss.item())

        self.network.eval()
        self.evaluator = Evaluator(self.network, device=device)
        return policy_loss, value_loss

    def run(self, on_iteration=None) -> TrainingReport:
        report = TrainingReport()
        for iteration in range(1, self.train_config.iterations + 1):
            started = time.perf_counter()
            examples, summaries = self.generate(iteration)

            self.buffer.extend(examples)
            # A window, not a full history: positions generated by a network
            # three iterations ago describe a player that no longer exists.
            if len(self.buffer) > self.train_config.buffer_size:
                self.buffer = self.buffer[-self.train_config.buffer_size :]

            policy_loss, value_loss = self.train_on_buffer()
            iteration_report = IterationReport(
                iteration=iteration,
                games=summaries,
                examples=len(examples),
                policy_loss=policy_loss,
                value_loss=value_loss,
                seconds=time.perf_counter() - started,
            )
            report.iterations.append(iteration_report)
            if on_iteration is not None:
                on_iteration(iteration_report)
        return report
