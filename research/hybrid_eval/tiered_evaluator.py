"""Spending evaluation effort where it changes the answer.

Most positions in a search are not close calls. A rook up in a quiet endgame
needs a material count, not a neural network and certainly not a language
model. A sharp middlegame with three hanging pieces is the opposite. A tiered
evaluator estimates how much a position is worth thinking about and routes it
accordingly, under a latency budget it is not allowed to overspend.

The tiers, in the order they cost:

* **Classical** — the hand-written evaluation, microseconds.
* **Neural** — a learned evaluator, tens of microseconds.
* **LLM** — a language model, seconds, and therefore reserved for the root of
  a search rather than its leaves, cached by position, and skipped entirely
  when the clock says no.

The complexity estimate leans on one signal above the rest: the gap between
the static evaluation and what a quiescence search says. If those two agree
the position is quiet almost by definition, and no amount of extra thinking
will move it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Protocol

import chess

from engine.evaluation.complexity import ComplexitySignals, estimate_complexity

EvalFn = Callable[[chess.Board], int]

# Re-exported: the estimate is engine-level machinery, and the tiering built
# on top of it is what this module adds.
__all__ = [
    "ComplexitySignals",
    "estimate_complexity",
    "LLMEvaluator",
    "LatencyBudget",
    "Tier",
    "TierPolicy",
    "TierStats",
    "TieredEvaluator",
    "TieredResult",
]


class Tier(str, Enum):
    CLASSICAL = "classical"
    NEURAL = "neural"
    LLM = "llm"


class LLMEvaluator(Protocol):
    """Anything that can score a position slowly but well."""

    def evaluate(self, board: chess.Board) -> float: ...


# --- complexity -----------------------------------------------------------


# --- latency --------------------------------------------------------------


@dataclass
class LatencyBudget:
    """A wall-clock allowance for one decision.

    The LLM tier is the only one that can blow a time control, so it is the
    only one that has to ask permission.
    """

    total_ms: float = 3000.0
    reserve_ms: float = 200.0
    max_llm_calls: int = 1
    spent_ms: float = 0.0
    llm_calls: int = 0

    def reset(self) -> None:
        self.spent_ms = 0.0
        self.llm_calls = 0

    def spend(self, milliseconds: float) -> None:
        self.spent_ms += milliseconds

    @property
    def remaining_ms(self) -> float:
        return max(0.0, self.total_ms - self.spent_ms)

    def can_afford(self, estimate_ms: float) -> bool:
        return (
            self.llm_calls < self.max_llm_calls
            and self.remaining_ms - estimate_ms >= self.reserve_ms
        )


@dataclass
class TierPolicy:
    """Where the boundaries between tiers sit."""

    neural_threshold: float = 0.30
    llm_threshold: float = 0.75
    llm_estimate_ms: float = 1500.0

    def tier_for(self, complexity: float, has_neural: bool, has_llm: bool) -> Tier:
        if has_llm and complexity >= self.llm_threshold:
            return Tier.LLM
        if has_neural and complexity >= self.neural_threshold:
            return Tier.NEURAL
        return Tier.CLASSICAL


@dataclass
class TieredResult:
    score: float
    tier: Tier
    complexity: ComplexitySignals
    latency_ms: float
    cached: bool = False
    downgraded_from: Tier | None = None


@dataclass
class TierStats:
    calls: dict[Tier, int] = field(default_factory=lambda: {tier: 0 for tier in Tier})
    latency_ms: dict[Tier, float] = field(default_factory=lambda: {tier: 0.0 for tier in Tier})
    cache_hits: int = 0
    downgrades: int = 0

    def record(self, result: TieredResult) -> None:
        self.calls[result.tier] += 1
        self.latency_ms[result.tier] += result.latency_ms
        if result.cached:
            self.cache_hits += 1
        if result.downgraded_from is not None:
            self.downgrades += 1

    def mean_latency_ms(self, tier: Tier) -> float:
        calls = self.calls[tier]
        return self.latency_ms[tier] / calls if calls else 0.0

    def table(self) -> str:
        header = f"{'tier':<10} {'calls':>7} {'mean ms':>10} {'total ms':>10}"
        lines = [header, "-" * len(header)]
        for tier in Tier:
            lines.append(
                f"{tier.value:<10} {self.calls[tier]:>7} "
                f"{self.mean_latency_ms(tier):>10.3f} {self.latency_ms[tier]:>10.1f}"
            )
        lines.append(f"cache hits: {self.cache_hits}, downgrades: {self.downgrades}")
        return "\n".join(lines)


# --- the evaluator --------------------------------------------------------


class TieredEvaluator:
    """Routes a position to the cheapest tier that can settle it."""

    def __init__(
        self,
        classical: EvalFn,
        neural: EvalFn | None = None,
        llm: LLMEvaluator | None = None,
        policy: TierPolicy | None = None,
        budget: LatencyBudget | None = None,
        tactical_probe: bool = True,
    ) -> None:
        self.classical = classical
        self.neural = neural
        self.llm = llm
        self.policy = policy or TierPolicy()
        self.budget = budget or LatencyBudget()
        self.tactical_probe = tactical_probe
        self.stats = TierStats()
        self._llm_cache: dict[int, float] = {}

    def new_move(self) -> None:
        """Start a fresh latency allowance; call once per move."""
        self.budget.reset()

    def evaluate(self, board: chess.Board) -> TieredResult:
        started = time.perf_counter()
        complexity = estimate_complexity(board, self.classical, self.tactical_probe)
        wanted = self.policy.tier_for(
            complexity.score, self.neural is not None, self.llm is not None
        )
        tier = wanted
        downgraded_from = None
        cached = False

        if tier is Tier.LLM:
            key = hash(board._transposition_key())
            if key in self._llm_cache:
                score = self._llm_cache[key]
                cached = True
            elif self.budget.can_afford(self.policy.llm_estimate_ms):
                call_started = time.perf_counter()
                score = float(self.llm.evaluate(board))  # type: ignore[union-attr]
                self.budget.spend((time.perf_counter() - call_started) * 1000)
                self.budget.llm_calls += 1
                self._llm_cache[key] = score
            else:
                # Out of clock: fall back rather than overspend the move.
                downgraded_from = Tier.LLM
                tier = Tier.NEURAL if self.neural is not None else Tier.CLASSICAL
                score = float((self.neural or self.classical)(board))
        elif tier is Tier.NEURAL:
            score = float(self.neural(board))  # type: ignore[misc]
        else:
            score = float(self.classical(board))

        result = TieredResult(
            score=score,
            tier=tier,
            complexity=complexity,
            latency_ms=(time.perf_counter() - started) * 1000,
            cached=cached,
            downgraded_from=downgraded_from,
        )
        self.stats.record(result)
        return result

    def static_eval(self, board: chess.Board) -> int:
        """The plain evaluation interface a search expects."""
        return int(self.evaluate(board).score)
