"""The policy-value network: a small residual tower with two heads.

Four residual blocks at 64 channels — about a fiftieth of AlphaZero's twenty
blocks at 256. That ratio is not an apology; it follows from the budget.
AlphaZero trained on forty million self-play games; an M2 Pro generating a
game every twenty seconds produces a few thousand in a day. A network large
enough to absorb forty million games would simply memorise a few thousand.

The two heads answer the two questions MCTS asks of a position: *which moves
are worth looking at* (policy) and *how does this end* (value).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from research.alphazero_lite.encoding import MOVE_PLANES, PLANES, POLICY_SIZE


@dataclass(frozen=True)
class NetworkConfig:
    blocks: int = 4
    channels: int = 64
    value_hidden: int = 64

    def describe(self) -> str:
        return f"{self.blocks} blocks x {self.channels} channels"


def torch_available() -> bool:
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def build_network(config: NetworkConfig | None = None):
    """A residual tower with a policy head and a value head."""
    import torch
    import torch.nn as nn

    settings = config or NetworkConfig()

    class ResidualBlock(nn.Module):
        def __init__(self, channels: int) -> None:
            super().__init__()
            self.conv1 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
            self.norm1 = nn.BatchNorm2d(channels)
            self.conv2 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
            self.norm2 = nn.BatchNorm2d(channels)

        def forward(self, x):
            residual = x
            x = torch.relu(self.norm1(self.conv1(x)))
            x = self.norm2(self.conv2(x))
            # The skip connection is what lets a tower this deep train at all
            # from a cold start — without it the early blocks get no gradient.
            return torch.relu(x + residual)

    class PolicyValueNetwork(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.stem = nn.Sequential(
                nn.Conv2d(PLANES, settings.channels, 3, padding=1, bias=False),
                nn.BatchNorm2d(settings.channels),
                nn.ReLU(),
            )
            self.tower = nn.Sequential(
                *[ResidualBlock(settings.channels) for _ in range(settings.blocks)]
            )
            # A 1x1 convolution straight to the 73 move planes. Flattened
            # row-major this lands at plane * 64 + square, which is exactly
            # how `move_index` numbers them — no dense layer, ~4,700 weights.
            self.policy_head = nn.Sequential(
                nn.Conv2d(settings.channels, MOVE_PLANES, 1),
                nn.Flatten(),
            )
            self.value_head = nn.Sequential(
                nn.Conv2d(settings.channels, 8, 1, bias=False),
                nn.BatchNorm2d(8),
                nn.ReLU(),
                nn.Flatten(),
                nn.Linear(8 * 64, settings.value_hidden),
                nn.ReLU(),
                nn.Linear(settings.value_hidden, 1),
                nn.Tanh(),
            )

        def forward(self, x):
            features = self.tower(self.stem(x))
            # Policy comes back as logits: MCTS wants to soften or sharpen it,
            # and a softmax baked in here would throw that away.
            return self.policy_head(features), self.value_head(features)

    return PolicyValueNetwork()


def parameter_count(model) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


class Evaluator:
    """What MCTS actually calls: a position in, priors and a value out.

    Wraps the network so the search never sees a tensor, and so the whole
    thing can be swapped for something cheaper in a test.
    """

    def __init__(self, model=None, device: str = "cpu", config: NetworkConfig | None = None):
        import torch

        self.torch = torch
        self.device = device
        self.model = (model or build_network(config)).to(device).eval()
        self.calls = 0

    def evaluate(self, planes: np.ndarray) -> tuple[np.ndarray, float]:
        """One position. Returns ``(policy probabilities, value)``."""
        policies, values = self.evaluate_batch(planes[None, ...])
        return policies[0], float(values[0])

    def evaluate_batch(self, planes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """A batch of positions — the only shape that is efficient.

        Single-position inference on a residual tower is dominated by call
        overhead, so the search is written to collect leaves and ask for them
        together wherever it can.
        """
        torch = self.torch
        self.calls += planes.shape[0]
        with torch.no_grad():
            tensor = torch.from_numpy(np.ascontiguousarray(planes)).to(self.device)
            logits, values = self.model(tensor)
            policies = torch.softmax(logits, dim=1).cpu().numpy()
        return policies, values.cpu().numpy().reshape(-1)


class UniformEvaluator:
    """A stand-in that knows nothing: flat priors and a drawn verdict.

    MCTS with this is still a legal, if weak, player — which makes it the
    right control for measuring what the network is contributing.
    """

    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, planes: np.ndarray) -> tuple[np.ndarray, float]:
        self.calls += 1
        return np.full(POLICY_SIZE, 1.0 / POLICY_SIZE, dtype=np.float32), 0.0

    def evaluate_batch(self, planes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        count = planes.shape[0]
        self.calls += count
        return (
            np.full((count, POLICY_SIZE), 1.0 / POLICY_SIZE, dtype=np.float32),
            np.zeros(count, dtype=np.float32),
        )
