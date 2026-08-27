"""Features, parameterised evaluation and the policy-gradient tuner."""

from __future__ import annotations

import chess
import numpy as np
import pytest

from engine.evaluation.pst import pst_scores
from engine.evaluation.tapered import positional_eval
from research.features import (
    FULL_PLANE_DIM,
    HANDCRAFTED_DIM,
    PIECE_SQUARE_DIM,
    full_plane_vector,
    handcrafted_vector,
    phase_scalar,
    piece_square_vector,
    pst_weights,
)
from research.params import (
    DEFAULT_PARAMS,
    EvalParams,
    TunableEngine,
    build_tables,
    make_static_eval,
)
from research.rl_tuning.parameter_optimizer import (
    ParameterOptimizer,
    TuningConfig,
    score_against_baseline,
)

POSITIONS = [
    chess.STARTING_FEN,
    "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "4k3/8/2p5/3p4/8/8/Q7/4K3 w - - 0 1",
    "4k3/8/8/8/8/2P5/2P5/4K3 w - - 0 1",
    "2b1k3/8/8/8/8/8/8/2B1KB2 w - - 0 1",
]


# --- features -------------------------------------------------------------


@pytest.mark.parametrize("fen", POSITIONS)
def test_piece_square_features_reproduce_the_engines_tables(fen):
    """A linear model over the folded features *is* a piece-square table.

    This is the anchor for every learned evaluation: whatever TD(λ) or an
    NNUE comes up with can be read in the same units as the hand-written
    tables, and compared against them directly.
    """
    board = chess.Board(fen)
    features = piece_square_vector(board)
    middlegame, endgame = pst_scores(board)
    assert float(features @ pst_weights()) == pytest.approx(middlegame)
    assert float(features @ pst_weights(endgame=True)) == pytest.approx(endgame)


def test_feature_dimensions():
    board = chess.Board()
    assert piece_square_vector(board).shape == (PIECE_SQUARE_DIM,) == (384,)
    assert full_plane_vector(board).shape == (FULL_PLANE_DIM,) == (768,)
    assert handcrafted_vector(board).shape == (HANDCRAFTED_DIM,) == (8,)


def test_the_start_position_is_featureless_by_symmetry():
    """Folded features cancel exactly when the position is mirror-symmetric."""
    assert not piece_square_vector(chess.Board()).any()


def test_features_flip_sign_with_colour():
    white = chess.Board("4k3/8/8/8/4N3/8/8/4K3 w - - 0 1")
    black = chess.Board("4k3/8/8/4n3/8/8/8/4K3 w - - 0 1")
    assert np.allclose(piece_square_vector(white), -piece_square_vector(black))


def test_full_planes_keep_the_colours_apart():
    """Unlike the folded encoding, this one does not cancel at the start."""
    vector = full_plane_vector(chess.Board())
    assert vector.sum() == 32
    assert vector[:PIECE_SQUARE_DIM].sum() == 16  # White's half


def test_handcrafted_features_read_the_position():
    doubled = chess.Board("4k3/8/8/8/8/2P5/2P5/4K3 w - - 0 1")
    features = handcrafted_vector(doubled)
    assert features[0] == 2  # two white pawns, no black ones
    assert features[5] == 1  # one doubled pawn
    assert features[6] == 2  # both of them isolated

    pair = chess.Board("4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1")
    assert handcrafted_vector(pair)[7] == 1


def test_phase_scalar_runs_from_one_to_zero():
    assert phase_scalar(chess.Board()) == 1.0
    assert phase_scalar(chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")) == 0.0


# --- parameterised evaluation --------------------------------------------


@pytest.mark.parametrize("fen", POSITIONS)
def test_default_parameters_reproduce_the_engine_exactly(fen):
    """The decomposition into material + placement + structure is exact.

    Tapering is linear and material does not depend on the phase, so lifting
    the piece values out of the tables cannot change a score. If this ever
    fails, "did tuning help?" stops having a clean answer.
    """
    board = chess.Board(fen)
    assert make_static_eval(DEFAULT_PARAMS)(board) == positional_eval(board)


def test_changing_a_parameter_changes_the_evaluation():
    board = chess.Board("4k3/8/8/8/8/2P5/2P5/4K3 w - - 0 1")
    harsher = make_static_eval(EvalParams(doubled_penalty=40))
    assert harsher(board) < make_static_eval(DEFAULT_PARAMS)(board)


def test_parameters_survive_a_vector_round_trip():
    params = EvalParams(knight=311.5, pst_scale=0.75)
    assert EvalParams.from_vector(params.to_vector()) == params
    assert EvalParams.names()[0] == "pawn"
    # Grows when a term is adopted; the rook bonuses arrived with the term that
    # measured +44 Elo on its own.
    assert "rook_open_file" in EvalParams.names()
    assert len(EvalParams.names()) == len(EvalParams().to_vector())


def test_clipping_keeps_proposals_playable():
    """An optimiser will eventually propose a negative rook; it costs games."""
    wild = EvalParams(queen=-500, pawn=10_000, pst_scale=99).clipped()
    assert wild.queen == 500 and wild.pawn == 200 and wild.pst_scale == 3.0
    assert DEFAULT_PARAMS.clipped() == DEFAULT_PARAMS


def test_tables_are_built_for_both_colours_and_phases():
    mg, eg = build_tables(DEFAULT_PARAMS)
    white_mg, black_mg = mg[chess.KNIGHT]
    assert len(white_mg) == len(black_mg) == 64
    # A knight on e4 for White mirrors one on e5 for Black.
    assert white_mg[chess.E4] == black_mg[chess.E5]
    assert eg[chess.PAWN][0][chess.A7] > eg[chess.PAWN][0][chess.A2]


def test_evaluation_is_white_relative():
    evaluate = make_static_eval(DEFAULT_PARAMS)
    white_up = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    black_up = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1")
    assert evaluate(white_up) == -evaluate(black_up) > 800


# --- tunable engine -------------------------------------------------------


def test_tunable_engine_plays_and_reports_its_depth():
    engine = TunableEngine(seed=1, depth=3, time_limit=1.0)
    result = engine.analyse(chess.Board())
    assert result.move in chess.Board().legal_moves
    assert result.depth == 3


def test_tunable_engine_matches_the_engines_evaluation_by_default():
    board = chess.Board(POSITIONS[1])
    assert TunableEngine().static_eval(board) == positional_eval(board)


def test_a_materially_blind_engine_values_a_queen_differently():
    """Sanity check that the parameters actually reach the search."""
    normal = TunableEngine(seed=1, depth=2, time_limit=1.0)
    blind = TunableEngine(EvalParams(queen=100.0), seed=1, depth=2, time_limit=1.0)

    # Mirror-symmetric queens: both engines have to call this level.
    balanced = chess.Board("3qk3/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert normal.static_eval(balanced) == blind.static_eval(balanced) == 0

    # Black a queen up: only the engine that values queens is alarmed.
    lopsided = chess.Board("3qk3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert normal.static_eval(lopsided) < blind.static_eval(lopsided) < 0


# --- policy gradient ------------------------------------------------------


def test_optimizer_normalises_every_parameter_to_its_own_scale():
    """One sigma has to mean the same nudge for a queen and for a scale factor."""
    optimizer = ParameterOptimizer()
    assert np.allclose(optimizer.theta, 1.0)
    assert optimizer.scale[4] == 900.0  # queen
    assert optimizer.current == DEFAULT_PARAMS


def test_optimizer_maps_theta_back_through_clipping():
    optimizer = ParameterOptimizer()
    optimizer.theta = optimizer.theta * 10
    assert optimizer.current == optimizer.current.clipped()


def test_a_step_plays_the_budget_it_promises():
    config = TuningConfig(population=2, games=2, max_plies=30, time_limit=0.02)
    optimizer = ParameterOptimizer(config=config)
    step = optimizer.step(1)

    # Antithetic pairs: population x 2 candidates, each playing `games` games.
    assert step.games_played == 2 * 2 * 2
    assert 0.0 <= step.mean_reward <= 1.0
    assert step.gradient_norm >= 0.0


def test_the_gradient_follows_the_perturbation_that_won(monkeypatch):
    """The REINFORCE update, tested without the noise of real games.

    Real matches are far too noisy to assert a direction on: two candidates
    two games apart routinely tie, the advantage is zero and the parameters
    correctly do not move. Feeding the step known rewards tests the update
    itself — that a winning perturbation is followed and its mirror is not.
    """
    optimizer = ParameterOptimizer(config=TuningConfig(population=1, sigma=0.1, learning_rate=1.0))
    before = optimizer.theta.copy()
    captured: dict = {}

    def fake_evaluate(candidates, iteration):
        captured["plus"] = candidates[0]
        return np.array([1.0, 0.0])  # the +epsilon candidate swept the match

    monkeypatch.setattr(optimizer, "_evaluate", fake_evaluate)
    optimizer.step(1)

    epsilon = captured["plus"] - before
    movement = optimizer.theta - before
    assert np.dot(movement, epsilon) > 0, "the step should follow the winning perturbation"


def test_a_tied_pair_leaves_the_parameters_alone():
    """No signal, no update — the honest response to two equal results."""
    optimizer = ParameterOptimizer(config=TuningConfig(population=2))
    before = optimizer.theta.copy()
    optimizer._evaluate = lambda candidates, iteration: np.full(len(candidates), 0.5)
    optimizer.step(1)
    assert np.allclose(optimizer.theta, before)


def test_iteration_callback_fires():
    seen: list[int] = []
    optimizer = ParameterOptimizer(
        config=TuningConfig(iterations=2, population=1, games=2, max_plies=20, time_limit=0.02),
        on_iteration=lambda step: seen.append(step.iteration),
    )
    result = optimizer.run()
    assert seen == [1, 2]
    assert len(result.history) == 2
    assert result.games_played == 2 * (1 * 2 * 2)
    assert "iter" in result.table()


def test_scoring_a_candidate_against_itself_is_a_fair_fight():
    """Identical parameters, so the score is decided by the games, not the eval."""
    vector = DEFAULT_PARAMS.to_vector()
    score = score_against_baseline(
        vector, vector, games=2, depth=2, max_plies=30, time_limit=0.02, seed=3
    )
    assert 0.0 <= score <= 1.0
