"""How small can a network be and still evaluate chess?

Six architectures spanning three orders of magnitude, from a 385-parameter
linear model to a ~270K-parameter NNUE, each trained on the same positions
and judged on three axes:

* **accuracy** — mean error in centipawns against the teacher,
* **size** — parameters,
* **latency** — microseconds per position, which is the axis that usually
  decides the argument.

The latency column is the point. A search evaluates hundreds of thousands of
leaves per move, and the hand-written evaluation costs about six microseconds.
A network that is more accurate but takes fifty is not an improvement — it is
a smaller search wearing a better evaluation, and the smaller search usually
wins the game. The linear models are special here: a linear model over
piece-square features *is* a piece-square table, so it folds into the same
lookup the engine already does and costs nothing extra at all.

Hidden layers use clipped ReLU, as real NNUE does — it is the activation that
survives quantisation to integers, which is how those networks reach the
speed they need.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from research.minimal_nnue.dataset import ENCODINGS, VALUE_SCALE, Dataset


@dataclass(frozen=True)
class Architecture:
    """A network shape and the input it reads."""

    name: str
    encoding: str
    hidden: tuple[int, ...] = ()

    @property
    def input_dim(self) -> int:
        return ENCODINGS[self.encoding]

    @property
    def parameters(self) -> int:
        """Weights plus biases, counted the way a paper would count them."""
        total = 0
        previous = self.input_dim
        for width in self.hidden:
            total += previous * width + width
            previous = width
        return total + previous + 1  # output layer

    @property
    def is_linear(self) -> bool:
        return not self.hidden

    def describe(self) -> str:
        shape = " → ".join(str(width) for width in (self.input_dim, *self.hidden, 1))
        return f"{shape} ({self.parameters:,} params)"


# Six architectures, roughly a factor of three or four apart each time.
ARCHITECTURES: list[Architecture] = [
    Architecture("linear-folded", "folded"),  # 385
    Architecture("linear-planes", "planes"),  # 769
    Architecture("mlp-16", "planes", (16,)),  # 12,321
    Architecture("mlp-32x32", "planes", (32, 32)),  # 25,697
    Architecture("mlp-128", "planes", (128,)),  # 98,561
    Architecture("nnue-336x32", "planes", (336, 32)),  # 269,201
]

# The input-feature ablation runs one architecture across every encoding.
ABLATION_ARCHITECTURE = "mlp-32x32"


def torch_available() -> bool:
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def build_model(architecture: Architecture):
    """A torch module for this shape.

    Clipped ReLU rather than plain ReLU: it is what NNUE uses, because a
    bounded activation is what makes int8 quantisation possible later.
    """
    import torch.nn as nn

    layers: list = []
    previous = architecture.input_dim
    for width in architecture.hidden:
        layers.append(nn.Linear(previous, width))
        layers.append(nn.Hardtanh(0.0, 1.0))  # clipped ReLU
        previous = width
    layers.append(nn.Linear(previous, 1))
    layers.append(nn.Tanh())  # predictions live in the same [-1, 1] as the labels
    return nn.Sequential(*layers)


@dataclass
class TrainingReport:
    """What one architecture achieved."""

    architecture: Architecture
    train_loss: float
    val_loss: float
    val_mae_cp: float
    baseline_mae_cp: float
    latency_us: float
    batch_us_per_position: float
    epochs: int
    seconds: float
    history: list[float] = field(default_factory=list)

    @property
    def parameters(self) -> int:
        return self.architecture.parameters

    @property
    def beats_predicting_zero(self) -> bool:
        """Did it learn anything at all beyond the mean?"""
        return self.val_mae_cp < self.baseline_mae_cp


def _to_tensor(array: np.ndarray, device: str):
    import torch

    return torch.from_numpy(np.ascontiguousarray(array, dtype=np.float32)).to(device)


def train_model(
    architecture: Architecture,
    dataset: Dataset,
    epochs: int = 60,
    batch_size: int = 256,
    learning_rate: float = 1e-3,
    validation: float = 0.2,
    device: str = "cpu",
    seed: int = 0,
) -> TrainingReport:
    """Fit one architecture and measure what it costs to use.

    ``device`` defaults to CPU on purpose: these networks are small enough
    that moving a batch to the GPU costs more than the matrix multiply saves,
    and single-position latency — the number that decides whether a net can
    live inside a search — is a CPU number anyway.
    """
    import torch

    torch.manual_seed(seed)
    started = time.perf_counter()

    train_set, val_set = dataset.split(validation, seed=seed)
    train_x = _to_tensor(train_set.encoded(architecture.encoding), device)
    train_y = _to_tensor(train_set.values.reshape(-1, 1), device)
    val_x = _to_tensor(val_set.encoded(architecture.encoding), device)
    val_y = _to_tensor(val_set.values.reshape(-1, 1), device)

    model = build_model(architecture).to(device)
    optimiser = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = torch.nn.MSELoss()

    history: list[float] = []
    train_loss = float("nan")
    for _ in range(epochs):
        model.train()
        permutation = torch.randperm(train_x.shape[0], device=device)
        for start in range(0, train_x.shape[0], batch_size):
            index = permutation[start : start + batch_size]
            optimiser.zero_grad()
            loss = loss_fn(model(train_x[index]), train_y[index])
            loss.backward()
            optimiser.step()
            train_loss = float(loss.item())

        model.eval()
        with torch.no_grad():
            history.append(float(loss_fn(model(val_x), val_y).item()))

    model.eval()
    with torch.no_grad():
        predictions = model(val_x).cpu().numpy().reshape(-1)
    val_loss = history[-1] if history else float("nan")

    # Errors are reported in centipawns, because "0.031 MSE in tanh space" is
    # not a number anyone can judge a chess evaluation by. Labels are already
    # clamped when the dataset is built, so the stored centipawns are used
    # directly rather than inverted back through a saturating tanh.
    predicted_cp = np.arctanh(np.clip(predictions, -0.9999, 0.9999)) * VALUE_SCALE
    actual_cp = val_set.centipawns
    val_mae_cp = float(np.mean(np.abs(predicted_cp - actual_cp)))
    baseline_mae_cp = float(np.mean(np.abs(actual_cp - np.mean(actual_cp))))

    latency_us, batch_us = benchmark_latency(model, val_x, device)

    return TrainingReport(
        architecture=architecture,
        train_loss=train_loss,
        val_loss=val_loss,
        val_mae_cp=val_mae_cp,
        baseline_mae_cp=baseline_mae_cp,
        latency_us=latency_us,
        batch_us_per_position=batch_us,
        epochs=epochs,
        seconds=time.perf_counter() - started,
        history=history,
    )


def benchmark_latency(
    model, inputs, device: str = "cpu", repeats: int = 200
) -> tuple[float, float]:
    """Microseconds for one position, and per position in a batch.

    Both numbers matter and they are wildly different. A search needs the
    first; a training or analysis pipeline can use the second.
    """
    import torch

    single = inputs[:1]
    with torch.no_grad():
        for _ in range(10):  # warm up
            model(single)
        started = time.perf_counter()
        for _ in range(repeats):
            model(single)
        single_us = (time.perf_counter() - started) / repeats * 1e6

        started = time.perf_counter()
        for _ in range(10):
            model(inputs)
        batch_us = (time.perf_counter() - started) / (10 * inputs.shape[0]) * 1e6

    return single_us, batch_us


def export_linear_weights(model, architecture: Architecture) -> np.ndarray:
    """Pull a linear model's weights out as a plain vector.

    Only defined for the linear architectures, and that is the whole point:
    a linear model over piece-square features folds into the lookup table the
    engine already walks, so using it costs nothing per leaf. Anything with a
    hidden layer has to be run.
    """
    if not architecture.is_linear:
        raise ValueError(f"{architecture.name} has hidden layers; there is nothing to fold")
    import torch

    with torch.no_grad():
        weight = model[0].weight.detach().cpu().numpy().reshape(-1)
    # The network predicts tanh(cp / SCALE); folding the scale back in gives
    # weights in centipawns, the same units as the engine's tables.
    return weight * VALUE_SCALE


@dataclass
class SearchReport:
    reports: list[TrainingReport] = field(default_factory=list)

    def table(self) -> str:
        header = (
            f"{'architecture':<16} {'params':>9} {'val MSE':>9} {'MAE cp':>8} "
            f"{'vs mean':>8} {'1-pos µs':>9} {'batch µs':>9}"
        )
        lines = [header, "-" * len(header)]
        for report in self.reports:
            lines.append(
                f"{report.architecture.name:<16} {report.parameters:>9,} "
                f"{report.val_loss:>9.4f} {report.val_mae_cp:>8.1f} "
                f"{report.baseline_mae_cp:>8.1f} {report.latency_us:>9.1f} "
                f"{report.batch_us_per_position:>9.2f}"
            )
        return "\n".join(lines)

    def smallest_within(self, tolerance_cp: float) -> TrainingReport | None:
        """The cheapest architecture whose error stays under ``tolerance_cp``."""
        candidates = [r for r in self.reports if r.val_mae_cp <= tolerance_cp]
        return min(candidates, key=lambda r: r.parameters) if candidates else None


def run_architecture_search(
    dataset: Dataset,
    architectures: list[Architecture] | None = None,
    on_result=None,
    **train_kwargs,
) -> SearchReport:
    """Train every architecture on the same positions and collect the results."""
    report = SearchReport()
    for architecture in architectures or ARCHITECTURES:
        trained = train_model(architecture, dataset, **train_kwargs)
        report.reports.append(trained)
        if on_result is not None:
            on_result(trained)
    return report


def run_feature_ablation(
    dataset: Dataset,
    base: str = ABLATION_ARCHITECTURE,
    on_result=None,
    **train_kwargs,
) -> SearchReport:
    """Hold the network fixed and vary only what it is shown."""
    template = next(a for a in ARCHITECTURES if a.name == base)
    variants = [Architecture(f"{encoding}", encoding, template.hidden) for encoding in ENCODINGS]
    return run_architecture_search(dataset, variants, on_result=on_result, **train_kwargs)
