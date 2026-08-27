"""TDLeaf(λ) value learning."""

from __future__ import annotations

import chess
import numpy as np
import pytest

from engine.evaluation.pst import RAW_MG, pst_scores
from research.features import PIECE_SQUARE_DIM, piece_square_vector
from research.self_play.value_learner import (
    VALUE_SCALE,
    GameTrace,
    PieceSquareEvaluator,
    TDConfig,
    ValueLearner,
)

POSITIONS = [
    chess.STARTING_FEN,
    "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
]


# --- the evaluator --------------------------------------------------------


@pytest.mark.parametrize("fen", POSITIONS)
def test_the_learnable_evaluator_reproduces_the_engines_tables(fen):
    """Learned weights and hand-written tables live in the same units."""
    board = chess.Board(fen)
    evaluator = PieceSquareEvaluator.from_engine_tables()
    assert evaluator.static_eval(board) == pst_scores(board)[0]


@pytest.mark.parametrize("fen", POSITIONS)
def test_the_fast_path_agrees_with_the_feature_vector(fen):
    """Tables and numpy are two views of one weight vector, not two models."""
    board = chess.Board(fen)
    evaluator = PieceSquareEvaluator.from_engine_tables()
    dot = float(piece_square_vector(board) @ evaluator.weights)
    assert evaluator.static_eval(board) == pytest.approx(dot, abs=1.0)


def test_material_only_start_values_pieces_but_not_squares():
    evaluator = PieceSquareEvaluator.material_only()
    means = evaluator.piece_means()
    assert (means["pawn"], means["knight"], means["rook"], means["queen"]) == (100, 320, 500, 900)

    centre = chess.Board("4k3/8/8/8/4N3/8/8/4K3 w - - 0 1")
    rim = chess.Board("4k3/8/8/8/8/8/8/N3K3 w - - 0 1")
    assert evaluator.static_eval(centre) == evaluator.static_eval(rim) == 320


def test_the_engines_tables_do_prefer_the_centre():
    """The contrast the learner is being asked to rediscover."""
    knight = RAW_MG[chess.KNIGHT]
    assert knight[chess.E4 ^ 56] > knight[chess.A1 ^ 56]


def test_value_is_squashed_and_white_relative():
    evaluator = PieceSquareEvaluator.from_engine_tables()
    white_up = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    black_up = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1")

    assert evaluator.value(chess.Board()) == 0.0
    assert 0 < evaluator.value(white_up) < 1
    assert evaluator.value(white_up) == pytest.approx(-evaluator.value(black_up))
    assert evaluator.value(white_up) == pytest.approx(
        np.tanh(evaluator.static_eval(white_up) / VALUE_SCALE)
    )


def test_setting_weights_rebuilds_the_search_tables():
    evaluator = PieceSquareEvaluator()
    board = chess.Board("4k3/8/8/8/4N3/8/8/4K3 w - - 0 1")
    assert evaluator.static_eval(board) == 0

    weights = np.zeros(PIECE_SQUARE_DIM)
    weights[1 * 64 + chess.E4] = 250.0  # knights are plane 1
    evaluator.set_weights(weights)
    assert evaluator.static_eval(board) == 250


def test_black_reads_the_mirrored_square():
    weights = np.zeros(PIECE_SQUARE_DIM)
    weights[1 * 64 + chess.E4] = 250.0
    evaluator = PieceSquareEvaluator(weights)
    black_mirror = chess.Board("4k3/8/8/4n3/8/8/8/4K3 w - - 0 1")  # e5 mirrors e4
    assert evaluator.static_eval(black_mirror) == -250


# --- the update -----------------------------------------------------------


def trace_of(square_weightings: list[np.ndarray], values: list[float], outcome: float) -> GameTrace:
    return GameTrace(
        features=square_weightings, values=values, outcome=outcome, plies=len(values), reason="test"
    )


def test_an_empty_game_teaches_nothing():
    learner = ValueLearner(PieceSquareEvaluator())
    assert learner.update(trace_of([], [], 1.0)) == 0.0


def test_a_win_raises_the_weights_of_the_features_that_were_present():
    """The core of TD: what was on the board when White won gets worth more."""
    feature = np.zeros(PIECE_SQUARE_DIM)
    feature[1 * 64 + chess.E4] = 1.0  # a white knight on e4
    learner = ValueLearner(PieceSquareEvaluator(), TDConfig(learning_rate=100.0))

    learner.update(trace_of([feature.copy()], [0.0], outcome=1.0))
    assert learner.evaluator.weights[1 * 64 + chess.E4] > 0


def test_a_loss_lowers_them():
    feature = np.zeros(PIECE_SQUARE_DIM)
    feature[1 * 64 + chess.E4] = 1.0
    learner = ValueLearner(PieceSquareEvaluator(), TDConfig(learning_rate=100.0))

    learner.update(trace_of([feature.copy()], [0.0], outcome=-1.0))
    assert learner.evaluator.weights[1 * 64 + chess.E4] < 0


def test_an_evaluation_that_already_called_it_right_barely_moves():
    """No surprise, no learning — the point of a temporal *difference*."""
    feature = np.zeros(PIECE_SQUARE_DIM)
    feature[1 * 64 + chess.E4] = 1.0
    learner = ValueLearner(PieceSquareEvaluator(), TDConfig(learning_rate=100.0))

    learner.update(trace_of([feature.copy()], [0.99], outcome=1.0))
    surprised = ValueLearner(PieceSquareEvaluator(), TDConfig(learning_rate=100.0))
    surprised.update(trace_of([feature.copy()], [-0.9], outcome=1.0))

    index = 1 * 64 + chess.E4
    assert 0 < learner.evaluator.weights[index] < surprised.evaluator.weights[index]


def test_lambda_carries_credit_back_through_the_game():
    """A later surprise should still reach the positions that led to it."""
    early = np.zeros(PIECE_SQUARE_DIM)
    early[1 * 64 + chess.E4] = 1.0
    late = np.zeros(PIECE_SQUARE_DIM)
    late[1 * 64 + chess.D4] = 1.0

    def run(lam: float) -> float:
        learner = ValueLearner(PieceSquareEvaluator(), TDConfig(lam=lam, learning_rate=100.0))
        learner.update(trace_of([early.copy(), late.copy()], [0.0, 0.0], outcome=1.0))
        return float(learner.evaluator.weights[1 * 64 + chess.E4])

    # With lambda = 0 only the final position is credited for the result.
    assert run(0.0) == pytest.approx(0.0, abs=1e-9)
    assert run(0.9) > 0


def test_weights_are_clipped():
    feature = np.ones(PIECE_SQUARE_DIM)
    learner = ValueLearner(
        PieceSquareEvaluator(), TDConfig(learning_rate=10_000.0, weight_clip=50.0)
    )
    learner.update(trace_of([feature], [0.0], outcome=1.0))
    assert np.all(np.abs(learner.evaluator.weights) <= 50.0)


# --- self-play ------------------------------------------------------------


def test_a_self_play_game_produces_a_usable_trace():
    learner = ValueLearner(
        PieceSquareEvaluator.material_only(),
        TDConfig(depth=1, max_plies=20, time_limit=0.05, seed=1),
    )
    trace = learner.play_game()
    assert len(trace.features) == len(trace.values) > 0
    assert trace.outcome in (-1.0, 0.0, 1.0)
    assert trace.features[0].shape == (PIECE_SQUARE_DIM,)
    assert trace.reason


def test_training_records_one_row_per_game():
    learner = ValueLearner(
        PieceSquareEvaluator.material_only(),
        TDConfig(games=3, depth=1, max_plies=20, time_limit=0.05, seed=2),
    )
    seen: list[int] = []
    result = learner.train(on_game=lambda index, trace, error: seen.append(index))

    assert seen == [1, 2, 3]
    assert len(result.td_errors) == len(result.outcomes) == len(result.piece_means) == 3
    assert "piece means" in result.table()
    assert result.seconds > 0


def test_exploration_makes_self_play_games_differ():
    """Two deterministic copies would otherwise replay one game forever."""

    def first_moves(epsilon: float) -> set[str]:
        learner = ValueLearner(
            PieceSquareEvaluator.material_only(),
            TDConfig(games=4, depth=1, max_plies=6, time_limit=0.05, epsilon=epsilon, seed=5),
        )
        return {str(learner.play_game().plies) + str(learner.play_game().reason) for _ in range(2)}

    assert first_moves(0.9)  # simply has to run; the assertion below is the point
    learner = ValueLearner(
        PieceSquareEvaluator.material_only(),
        TDConfig(depth=1, max_plies=8, time_limit=0.05, epsilon=1.0, seed=11),
    )
    traces = [learner.play_game() for _ in range(4)]
    assert len({tuple(np.round(t.values, 4)) for t in traces}) > 1
