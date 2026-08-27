"""Tuning the evaluation by policy gradient.

The policy here is a Gaussian over parameter space: sample a perturbation,
play a match with the perturbed evaluation, and push the mean towards the
perturbations that scored well. That update *is* REINFORCE — the "action" is
a parameter vector and the "reward" is a match score — and it is a close
relative of the SPSA that real engines tune with. Worth naming plainly rather
than implying something more exotic is going on.

Three choices carry most of the weight:

* **Antithetic sampling.** Every perturbation ``ε`` is played alongside
  ``−ε`` on the same openings. Match results are extremely noisy — a 16-game
  match has a standard error of about 12% — so the mirrored pair cancels most
  of the shared luck and turns a difference of a few Elo into something
  measurable within a realistic budget.
* **Relative units.** A queen is 900 and the piece-square scale is 1.0.
  Perturbing both by "0.08" only means the same thing if the parameters are
  normalised by their defaults first, which is what happens here.
* **Starting from the hand-written values.** With a few hundred games to
  spend, learning from noise learns nothing. The question this module can
  actually answer is "are the textbook numbers a local optimum for *this*
  search at *this* depth", and that needs a good starting point.
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from research.params import DEFAULT_PARAMS, EvalParams, TunableEngine
from tournament.match import play_match
from tournament.openings import book


@dataclass
class TuningConfig:
    """Defaults sized for a demonstration, not a tuning run.

    The budget is ``iterations × population × 2 × games`` — the factor of two
    is the antithetic pair. At depth 4 a game takes a few seconds, so the
    defaults below are roughly a ten-minute run; a serious one multiplies
    every number by ten and runs overnight.
    """

    iterations: int = 5
    population: int = 3
    games: int = 6
    sigma: float = 0.08
    learning_rate: float = 0.5
    depth: int = 4
    max_plies: int = 160
    time_limit: float | None = 0.2
    seed: int = 0
    workers: int = 1


@dataclass
class IterationResult:
    iteration: int
    params: EvalParams
    mean_reward: float
    best_reward: float
    gradient_norm: float
    games_played: int
    seconds: float


@dataclass
class TuningResult:
    baseline: EvalParams
    best: EvalParams
    history: list[IterationResult] = field(default_factory=list)

    @property
    def games_played(self) -> int:
        return sum(step.games_played for step in self.history)

    def table(self) -> str:
        header = f"{'iter':>4} {'mean R':>8} {'best R':>8} {'|grad|':>8} {'games':>6} {'time':>7}"
        lines = [header, "-" * len(header)]
        for step in self.history:
            lines.append(
                f"{step.iteration:>4} {step.mean_reward:>8.3f} {step.best_reward:>8.3f} "
                f"{step.gradient_norm:>8.3f} {step.games_played:>6} {step.seconds:>6.1f}s"
            )
        return "\n".join(lines)


def score_against_baseline(
    candidate_vector: np.ndarray,
    baseline_vector: np.ndarray,
    games: int,
    depth: int,
    max_plies: int,
    time_limit: float | None,
    seed: int,
) -> float:
    """Play a match and return the candidate's score, 0 to 1.

    A module-level function on purpose: process pools on macOS spawn fresh
    interpreters, so the work they are handed has to be importable.
    """
    candidate = TunableEngine(
        params=EvalParams.from_vector(candidate_vector),
        name="candidate",
        depth=depth,
        seed=seed,
        time_limit=time_limit,
    )
    baseline = TunableEngine(
        params=EvalParams.from_vector(baseline_vector),
        name="baseline",
        depth=depth,
        seed=seed + 1,
        time_limit=time_limit,
    )
    openings = book(max(1, games // 2))
    match = play_match(candidate, baseline, openings=openings, games=games, max_plies=max_plies)
    return match.score


class ParameterOptimizer:
    """Gaussian policy gradient over :class:`EvalParams`."""

    def __init__(
        self,
        baseline: EvalParams | None = None,
        config: TuningConfig | None = None,
        on_iteration: Callable[[IterationResult], None] | None = None,
    ) -> None:
        self.baseline = baseline or DEFAULT_PARAMS
        self.config = config or TuningConfig()
        self.on_iteration = on_iteration
        self.rng = np.random.default_rng(self.config.seed)

        # Everything is optimised in units of the starting values, so one
        # sigma means the same relative nudge for a queen and for a scale
        # factor. A default of zero would divide by zero, so those stay
        # absolute.
        self.scale = np.where(
            np.abs(self.baseline.to_vector()) > 1e-9, np.abs(self.baseline.to_vector()), 1.0
        )
        self.theta = self.baseline.to_vector() / self.scale

    # --- helpers ----------------------------------------------------------

    def params_from(self, theta: np.ndarray) -> EvalParams:
        return EvalParams.from_vector(theta * self.scale).clipped()

    @property
    def current(self) -> EvalParams:
        return self.params_from(self.theta)

    # --- one policy-gradient step ----------------------------------------

    def step(self, iteration: int) -> IterationResult:
        started = time.perf_counter()
        config = self.config

        perturbations = [
            self.rng.normal(0.0, config.sigma, size=self.theta.shape)
            for _ in range(config.population)
        ]
        # Antithetic pairs: the same perturbation in both directions.
        candidates = []
        for epsilon in perturbations:
            candidates.append(self.theta + epsilon)
            candidates.append(self.theta - epsilon)

        rewards = self._evaluate(candidates, iteration)

        # REINFORCE with a mean baseline: move towards perturbations that beat
        # the average, away from the ones that did not.
        gradient = np.zeros_like(self.theta)
        centre = float(np.mean(rewards))
        for index, epsilon in enumerate(perturbations):
            advantage = rewards[2 * index] - rewards[2 * index + 1]
            gradient += advantage * epsilon
        gradient /= 2 * config.population * config.sigma**2

        self.theta = self.theta + config.learning_rate * config.sigma**2 * gradient

        result = IterationResult(
            iteration=iteration,
            params=self.current,
            mean_reward=centre,
            best_reward=float(np.max(rewards)),
            gradient_norm=float(np.linalg.norm(gradient)),
            games_played=len(candidates) * config.games,
            seconds=time.perf_counter() - started,
        )
        if self.on_iteration is not None:
            self.on_iteration(result)
        return result

    def _evaluate(self, candidates: list[np.ndarray], iteration: int) -> np.ndarray:
        config = self.config
        baseline_vector = self.baseline.to_vector()
        jobs = [
            (
                self.params_from(candidate).to_vector(),
                baseline_vector,
                config.games,
                config.depth,
                config.max_plies,
                config.time_limit,
                config.seed + iteration * 1000 + index,
            )
            for index, candidate in enumerate(candidates)
        ]

        if config.workers > 1:
            with ProcessPoolExecutor(max_workers=config.workers) as pool:
                rewards = list(pool.map(score_against_baseline, *zip(*jobs)))
        else:
            rewards = [score_against_baseline(*job) for job in jobs]
        return np.array(rewards, dtype=np.float64)

    def run(self) -> TuningResult:
        result = TuningResult(baseline=self.baseline, best=self.current)
        best_reward = -1.0
        for iteration in range(1, self.config.iterations + 1):
            step = self.step(iteration)
            result.history.append(step)
            if step.mean_reward > best_reward:
                best_reward = step.mean_reward
                result.best = step.params
        return result
