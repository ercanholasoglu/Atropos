"""Monte Carlo tree search, guided by the network's priors.

Nothing here is Monte Carlo in the old sense — there are no random playouts.
The network replaces them: it says which moves are worth looking at and what
the position is worth, and the tree spends its simulations resolving the
disagreement between those two opinions.

The selection rule is PUCT:

    score = Q(s, a) + c · P(s, a) · √N(s) / (1 + N(s, a))

The first term is what the tree has learned about a move, the second is what
the network guessed before looking. Early on the prior dominates and the
search follows the network; as visits accumulate the tree's own numbers take
over. That crossover is the whole algorithm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import chess
import numpy as np

from research.alphazero_lite.encoding import encode_board, policy_to_moves


@dataclass
class MCTSConfig:
    simulations: int = 400
    c_puct: float = 1.5
    # Dirichlet noise at the root is what stops self-play from playing the
    # same game every time. Without it the network's opinion is never
    # challenged and training data collapses to one line.
    dirichlet_alpha: float = 0.3
    dirichlet_weight: float = 0.25
    # Sample proportionally to visits for the opening, then play the most
    # visited move: exploration where it is cheap, strength where it counts.
    temperature: float = 1.0
    temperature_plies: int = 20
    max_depth: int = 80


@dataclass
class Node:
    """One position in the tree."""

    prior: float = 0.0
    visits: int = 0
    value_sum: float = 0.0
    children: dict[chess.Move, "Node"] = field(default_factory=dict)

    @property
    def expanded(self) -> bool:
        return bool(self.children)

    @property
    def value(self) -> float:
        """Mean value from the point of view of the player to move here."""
        return self.value_sum / self.visits if self.visits else 0.0

    def puct(self, child: "Node", c_puct: float) -> float:
        exploration = c_puct * child.prior * math.sqrt(self.visits) / (1 + child.visits)
        # A child's value is from *its* mover's perspective, so it is negated
        # to become this node's opinion of the move.
        return -child.value + exploration


@dataclass
class SearchStatistics:
    simulations: int = 0
    evaluations: int = 0
    terminal_hits: int = 0
    max_depth_reached: int = 0


def terminal_value(board: chess.Board) -> float | None:
    """Value of a finished position for the side to move, or ``None``."""
    if board.is_checkmate():
        return -1.0  # the side to move has been mated
    if board.is_game_over(claim_draw=True):
        return 0.0
    return None


class MCTS:
    """Search a position and report how the visits fell."""

    def __init__(self, evaluator, config: MCTSConfig | None = None, seed: int = 0) -> None:
        self.evaluator = evaluator
        self.config = config or MCTSConfig()
        self.rng = np.random.default_rng(seed)
        self.stats = SearchStatistics()

    # --- one simulation ---------------------------------------------------

    def _expand(self, node: Node, board: chess.Board) -> float:
        """Ask the network about a leaf and hang its children off it."""
        self.stats.evaluations += 1
        policy, value = self.evaluator.evaluate(encode_board(board))
        for move, prior in policy_to_moves(policy, board).items():
            node.children[move] = Node(prior=prior)
        return float(value)

    def _simulate(self, root: Node, board: chess.Board) -> None:
        path: list[Node] = [root]
        depth = 0

        node = root
        while node.expanded:
            if depth >= self.config.max_depth:
                break
            move = max(
                node.children,
                key=lambda candidate: node.puct(node.children[candidate], self.config.c_puct),
            )
            board.push(move)
            node = node.children[move]
            path.append(node)
            depth += 1

        self.stats.max_depth_reached = max(self.stats.max_depth_reached, depth)

        value = terminal_value(board)
        if value is None:
            value = self._expand(node, board) if depth < self.config.max_depth else 0.0
        else:
            self.stats.terminal_hits += 1

        # Walk back up, flipping the sign at every ply: a position that is
        # good for me is exactly that bad for the player before me.
        for ancestor in reversed(path):
            ancestor.visits += 1
            ancestor.value_sum += value
            value = -value

        for _ in range(depth):
            board.pop()

    # --- a full search ----------------------------------------------------

    def search(self, board: chess.Board) -> tuple[Node, dict[chess.Move, int]]:
        """Run the configured number of simulations from ``board``."""
        if board.is_game_over(claim_draw=True):
            raise ValueError("the game is already over — there is nothing to search")

        self.stats = SearchStatistics()
        root = Node()
        working = board.copy()
        self._expand(root, working)
        self._add_root_noise(root)

        for _ in range(self.config.simulations):
            self._simulate(root, working)
            self.stats.simulations += 1

        return root, {move: child.visits for move, child in root.children.items()}

    def _add_root_noise(self, root: Node) -> None:
        weight = self.config.dirichlet_weight
        if weight <= 0 or not root.children:
            return
        noise = self.rng.dirichlet([self.config.dirichlet_alpha] * len(root.children))
        for (move, child), sample in zip(root.children.items(), noise):
            child.prior = (1 - weight) * child.prior + weight * float(sample)

    # --- turning visits into a move --------------------------------------

    def visit_distribution(self, visits: dict[chess.Move, int]) -> dict[chess.Move, float]:
        """Visit counts as a probability distribution — the training target.

        The policy the network learns from is not the one it proposed; it is
        the one the search arrived at after looking. That gap is the whole
        source of improvement.
        """
        total = sum(visits.values())
        if total == 0:
            uniform = 1.0 / len(visits) if visits else 0.0
            return {move: uniform for move in visits}
        return {move: count / total for move, count in visits.items()}

    def select_move(self, visits: dict[chess.Move, int], ply: int) -> chess.Move:
        moves = list(visits)
        counts = np.array([visits[move] for move in moves], dtype=np.float64)

        if ply >= self.config.temperature_plies or self.config.temperature <= 0:
            return moves[int(np.argmax(counts))]

        weights = counts ** (1.0 / self.config.temperature)
        total = weights.sum()
        if total <= 0:
            return moves[int(self.rng.integers(len(moves)))]
        return moves[int(self.rng.choice(len(moves), p=weights / total))]
