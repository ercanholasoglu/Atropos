"""Tiered evaluation: complexity routing and the latency budget."""

from __future__ import annotations

import chess
import pytest

from engine.evaluation.tapered import positional_eval
from research.hybrid_eval.tiered_evaluator import (
    LatencyBudget,
    Tier,
    TieredEvaluator,
    TierPolicy,
    estimate_complexity,
)
from research.self_play.value_learner import PieceSquareEvaluator

QUIET = "8/8/4k3/8/8/4K3/8/4R3 w - - 0 1"
SHARP = "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9"
HANGING_QUEEN = "4k3/8/8/3q4/4P3/8/8/3QK3 w - - 0 1"
CHECKMATE = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"


class SlowLLM:
    """Stands in for a language model: expensive, and it counts its calls."""

    def __init__(self, offset: float = 50.0) -> None:
        self.calls = 0

        self.offset = offset

    def evaluate(self, board: chess.Board) -> float:
        self.calls += 1
        return positional_eval(board) + self.offset


def neural_eval():
    return PieceSquareEvaluator.from_engine_tables().static_eval


# --- complexity -----------------------------------------------------------


def test_a_quiet_position_scores_low_and_a_sharp_one_high():
    quiet = estimate_complexity(chess.Board(QUIET), positional_eval)
    sharp = estimate_complexity(chess.Board(SHARP), positional_eval)
    assert quiet.score < 0.2 < sharp.score


def test_a_finished_game_is_the_simplest_position_there_is():
    """Regression: the quiescence probe used to report a mate-sized gap here."""
    signals = estimate_complexity(chess.Board(CHECKMATE), positional_eval)
    assert signals.legal_moves == 0
    assert signals.score == 0.0
    assert signals.tactical_gap == 0


def test_hanging_material_raises_complexity():
    signals = estimate_complexity(chess.Board(HANGING_QUEEN), positional_eval)
    assert signals.hanging_material == 900
    assert signals.tactical_gap > 300  # the static eval is badly wrong here
    assert signals.score > 0.5


def test_the_tactical_probe_can_be_turned_off():
    """It is the strongest signal and the most expensive; leaves skip it."""
    with_probe = estimate_complexity(chess.Board(HANGING_QUEEN), positional_eval)
    without = estimate_complexity(chess.Board(HANGING_QUEEN), positional_eval, tactical_probe=False)
    assert without.tactical_gap == 0
    assert without.score < with_probe.score


def test_complexity_never_leaves_the_unit_interval():
    for fen in (QUIET, SHARP, HANGING_QUEEN, chess.STARTING_FEN, CHECKMATE):
        assert 0.0 <= estimate_complexity(chess.Board(fen), positional_eval).score <= 1.0


def test_signals_explain_themselves():
    text = estimate_complexity(chess.Board(SHARP), positional_eval).explain()
    assert "complexity" in text and "captures" in text


# --- routing --------------------------------------------------------------


def test_a_quiet_position_stays_on_the_cheap_tier():
    evaluator = TieredEvaluator(positional_eval, neural_eval(), SlowLLM())
    result = evaluator.evaluate(chess.Board(QUIET))
    assert result.tier is Tier.CLASSICAL
    assert result.score == positional_eval(chess.Board(QUIET))


def test_without_the_upper_tiers_everything_is_classical():
    evaluator = TieredEvaluator(positional_eval)
    for fen in (QUIET, SHARP, HANGING_QUEEN):
        assert evaluator.evaluate(chess.Board(fen)).tier is Tier.CLASSICAL


def test_a_sharp_position_climbs_a_tier():
    evaluator = TieredEvaluator(positional_eval, neural_eval())
    assert evaluator.evaluate(chess.Board(SHARP)).tier is Tier.NEURAL


def test_the_llm_tier_is_reachable_when_the_policy_says_so():
    llm = SlowLLM()
    evaluator = TieredEvaluator(
        positional_eval, neural_eval(), llm, policy=TierPolicy(llm_threshold=0.4)
    )
    evaluator.new_move()
    result = evaluator.evaluate(chess.Board(SHARP))
    assert result.tier is Tier.LLM and llm.calls == 1


def test_the_llm_answer_is_cached_by_position():
    """Seconds per call is too expensive to pay twice for one position."""
    llm = SlowLLM()
    evaluator = TieredEvaluator(
        positional_eval,
        neural_eval(),
        llm,
        policy=TierPolicy(llm_threshold=0.4),
        budget=LatencyBudget(max_llm_calls=1),
    )
    evaluator.new_move()
    board = chess.Board(SHARP)
    first = evaluator.evaluate(board)
    second = evaluator.evaluate(board)

    assert llm.calls == 1
    assert second.cached and not first.cached
    assert second.score == first.score
    assert evaluator.stats.cache_hits == 1


def test_a_spent_budget_downgrades_instead_of_overspending():
    """The clock wins. A slow tier that would lose on time is not used."""
    llm = SlowLLM()
    evaluator = TieredEvaluator(
        positional_eval,
        neural_eval(),
        llm,
        policy=TierPolicy(llm_threshold=0.4, llm_estimate_ms=1500),
        budget=LatencyBudget(total_ms=100, reserve_ms=50),
    )
    evaluator.new_move()
    result = evaluator.evaluate(chess.Board(SHARP))

    assert result.tier is Tier.NEURAL
    assert result.downgraded_from is Tier.LLM
    assert llm.calls == 0
    assert evaluator.stats.downgrades == 1


def test_the_call_allowance_is_per_move():
    llm = SlowLLM()
    evaluator = TieredEvaluator(
        positional_eval,
        neural_eval(),
        llm,
        policy=TierPolicy(llm_threshold=0.4),
        budget=LatencyBudget(max_llm_calls=1),
    )
    evaluator.new_move()
    evaluator.evaluate(chess.Board(SHARP))
    evaluator.evaluate(chess.Board(HANGING_QUEEN))  # second call, same move
    assert llm.calls == 1

    evaluator.new_move()
    evaluator.evaluate(chess.Board(HANGING_QUEEN))
    assert llm.calls == 2


def test_budget_arithmetic():
    budget = LatencyBudget(total_ms=1000, reserve_ms=100, max_llm_calls=2)
    assert budget.can_afford(500)
    budget.spend(600)
    assert budget.remaining_ms == 400
    assert not budget.can_afford(500)
    budget.reset()
    assert budget.remaining_ms == 1000 and budget.llm_calls == 0


def test_policy_boundaries():
    policy = TierPolicy(neural_threshold=0.3, llm_threshold=0.8)
    assert policy.tier_for(0.1, True, True) is Tier.CLASSICAL
    assert policy.tier_for(0.5, True, True) is Tier.NEURAL
    assert policy.tier_for(0.9, True, True) is Tier.LLM
    # Tiers that do not exist are never chosen.
    assert policy.tier_for(0.9, False, False) is Tier.CLASSICAL
    assert policy.tier_for(0.9, True, False) is Tier.NEURAL


# --- bookkeeping ----------------------------------------------------------


def test_stats_count_calls_and_latency_per_tier():
    evaluator = TieredEvaluator(positional_eval, neural_eval())
    evaluator.evaluate(chess.Board(QUIET))
    evaluator.evaluate(chess.Board(SHARP))

    assert evaluator.stats.calls[Tier.CLASSICAL] == 1
    assert evaluator.stats.calls[Tier.NEURAL] == 1
    assert evaluator.stats.mean_latency_ms(Tier.NEURAL) > 0
    assert evaluator.stats.mean_latency_ms(Tier.LLM) == 0
    assert "classical" in evaluator.stats.table()


def test_it_can_stand_in_for_a_plain_evaluation():
    """A search only wants an int; the routing has to be invisible to it."""
    evaluator = TieredEvaluator(positional_eval, neural_eval())
    board = chess.Board(SHARP)
    assert isinstance(evaluator.static_eval(board), int)
