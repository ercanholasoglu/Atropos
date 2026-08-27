"""The scaled self-play experiment script.

Small runs only — the point is that the measurement machinery is right, not
that ten thousand games fit in a test.
"""

from __future__ import annotations

import json

import chess
import numpy as np
import pytest

from research.self_play.value_learner import PieceSquareEvaluator
from scripts.self_play_run import (
    CENTRE,
    RIM,
    LearnedEngine,
    centre_minus_rim,
    reference_centre_minus_rim,
    shape_correlation,
)


def test_centre_minus_rim_reads_a_table():
    weights = np.zeros(384)
    for square in CENTRE:
        weights[64 + square] = 100.0  # knights are plane 1
    for square in RIM:
        weights[64 + square] = -20.0
    assert centre_minus_rim(weights, 1) == pytest.approx(120.0)


def test_the_reference_is_what_the_engine_actually_uses():
    """The hand-written knight table is the target being chased."""
    assert reference_centre_minus_rim(chess.KNIGHT) == pytest.approx(70.0)
    assert reference_centre_minus_rim(chess.KING) < 0  # kings hide in the middlegame


def test_shape_correlation_ignores_the_piece_value():
    """The mean was seeded, not learned; leaving it in would inflate every score.

    A table that is the hand-written one plus a constant has learned nothing
    about placement beyond what it started with, and must not score as though
    it had.
    """
    reference = PieceSquareEvaluator.from_engine_tables().weights
    assert shape_correlation(reference, 1, chess.KNIGHT) == pytest.approx(1.0)

    shifted = reference.copy()
    shifted[64:128] += 500.0
    assert shape_correlation(shifted, 1, chess.KNIGHT) == pytest.approx(1.0)

    flat = np.zeros(384)
    assert shape_correlation(flat, 1, chess.KNIGHT) == 0.0


def test_an_inverted_table_correlates_negatively():
    reference = PieceSquareEvaluator.from_engine_tables().weights
    inverted = reference.copy()
    inverted[64:128] = -inverted[64:128]
    assert shape_correlation(inverted, 1, chess.KNIGHT) == pytest.approx(-1.0)


def test_a_learned_table_can_be_played():
    """Playing strength is the measure; the table has to reach a search."""
    evaluator = PieceSquareEvaluator.from_engine_tables()
    engine = LearnedEngine(evaluator, seed=1, depth=2, time_limit=0.3)
    board = chess.Board()
    result = engine.analyse(board)

    assert result.move in board.legal_moves
    assert engine.static_eval(board) == 0  # a symmetric position is level


def test_the_script_writes_a_readable_record(tmp_path):
    from scripts.self_play_run import main
    import sys

    output = tmp_path / "run.json"
    argv = sys.argv
    sys.argv = [
        "self_play_run",
        "--games",
        "3",
        "--max-plies",
        "20",
        "--match-games",
        "0",
        "--out",
        str(output),
    ]
    try:
        assert main() == 0
    finally:
        sys.argv = argv

    record = json.loads(output.read_text())
    assert record["games"] == 3
    assert len(record["weights"]) == 384
    assert set(record["shapes"]) == {"pawn", "knight", "bishop", "rook", "queen", "king"}
    assert record["match_scores"] == {}
