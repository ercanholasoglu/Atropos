"""The benchmark, and the distinction it exists to enforce."""

from __future__ import annotations

import json

import pytest

from scripts.bench import POSITIONS, compare, run_once


@pytest.mark.parametrize("name,fen", POSITIONS)
def test_every_position_is_legal(name: str, fen: str) -> None:
    """A benchmark position that is not a legal chess position measures nothing."""
    import chess

    board = chess.Board(fen)
    assert board.is_valid(), name
    assert not board.is_game_over(), f"{name} is already over"


def test_the_suite_covers_both_shapes() -> None:
    """Quiet and sharp positions search very differently; one alone is a biased sample."""
    kinds = {name.split(":", 1)[0] for name, _ in POSITIONS}
    assert kinds == {"open", "tact"}


def test_node_counts_are_deterministic() -> None:
    """The whole basis of the benchmark: same build, same nodes, every time."""
    first, _ = run_once(level=4, depth=2)
    second, _ = run_once(level=4, depth=2)
    assert first == second


def test_identical_nodes_report_a_clean_speed_comparison() -> None:
    baseline = {"nodes": {"a": 100, "b": 200}, "nps": 1000.0}
    current = {"nodes": {"a": 100, "b": 200}, "nps": 2000.0}
    lines = "\n".join(compare(current, baseline))
    assert "search unchanged" in lines
    assert "faster" in lines
    # One doubling of speed, so the conversion should name the measured slope.
    assert "+171" in lines


def test_changed_nodes_refuse_a_speed_comparison() -> None:
    """A different node count means a different engine, and nps stops meaning speed."""
    baseline = {"nodes": {"a": 100, "b": 200}, "nps": 1000.0}
    current = {"nodes": {"a": 100, "b": 150}, "nps": 2000.0}
    lines = "\n".join(compare(current, baseline))
    assert "SEARCH CHANGED" in lines
    assert "not a speed comparison" in lines
    assert "faster" not in lines, "a behaviour change must not be reported as speed"


def test_a_recorded_run_round_trips() -> None:
    nodes, seconds = run_once(level=4, depth=2)
    payload = {"nodes": nodes, "nps": sum(nodes.values()) / seconds, "level": 4, "depth": 2}
    assert json.loads(json.dumps(payload))["nodes"] == nodes
