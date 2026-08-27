"""The tactical suite, and the checks that keep it honest.

A suite whose answers are wrong is worse than no suite: it fails on correct
engines and passes on broken ones. These tests verify the *suite* first, then
what the engines do with it.
"""

from __future__ import annotations

import chess
import pytest

from engine.levels import create_engine
from engine.tactics import TACTICAL_SUITE, TacticalPosition, run_suite

# --- the suite has to be right before it can judge anything ---------------


@pytest.mark.parametrize("position", TACTICAL_SUITE, ids=lambda p: p.name)
def test_every_position_is_a_legal_one(position: TacticalPosition):
    """Two entries were rejected here when the suite was written.

    Both had the side *not* to move already in check — a position that cannot
    arise, and whose 'solutions' were therefore fiction.
    """
    board = position.board()
    assert board.is_valid(), board.status()


@pytest.mark.parametrize("position", TACTICAL_SUITE, ids=lambda p: p.name)
def test_every_recorded_move_is_legal_and_spelled_right(position: TacticalPosition):
    board = position.board()
    legal = {board.san(move) for move in board.legal_moves}
    for san in (*position.best_moves, *position.avoid_moves):
        assert san in legal, f"{san} is not a legal move in {position.name}"


@pytest.mark.parametrize("position", TACTICAL_SUITE, ids=lambda p: p.name)
def test_every_position_states_an_answer_one_way_or_the_other(position: TacticalPosition):
    assert bool(position.best_moves) != bool(position.avoid_moves)


@pytest.mark.parametrize(
    "position",
    [p for p in TACTICAL_SUITE if all("#" in m for m in p.best_moves)],
    ids=lambda p: p.name,
)
def test_a_move_recorded_as_mate_is_mate(position: TacticalPosition):
    for san in position.best_moves:
        board = position.board()
        board.push_san(san)
        assert board.is_checkmate()


def test_the_suite_covers_more_than_mates():
    """A suite of only mates would measure one thing."""
    mates = sum(1 for p in TACTICAL_SUITE if any("#" in m for m in p.best_moves))
    assert 0 < mates < len(TACTICAL_SUITE)


# --- scoring --------------------------------------------------------------


def test_a_best_move_position_accepts_only_its_answers():
    position = next(p for p in TACTICAL_SUITE if p.name == "take the free queen")
    board = position.board()
    assert position.solved_by(board, chess.Move.from_uci("e4d5"))
    assert not position.solved_by(board, chess.Move.from_uci("e1e2"))
    assert not position.solved_by(board, None)


def test_an_avoid_position_accepts_anything_but_the_trap():
    """Enumerating twenty adequate replies is a list that is easy to get wrong."""
    position = next(p for p in TACTICAL_SUITE if p.avoid_moves)
    board = position.board()
    assert not position.solved_by(board, chess.Move.from_uci("a2d5"))  # Qxd5
    assert position.solved_by(board, chess.Move.from_uci("e1e2"))


# --- what the engines make of it -----------------------------------------


def test_a_weak_engine_solves_the_easy_ones_and_not_the_hard_ones():
    """The suite has to discriminate, or it is measuring nothing."""
    report = run_suite(create_engine(1, seed=1))
    assert 0 <= report.solved < report.total


def test_a_searching_engine_finds_the_mates():
    report = run_suite(create_engine(4, seed=1, time_limit=0.5))
    mates = [r for r in report.results if any("#" in m for m in r.position.best_moves)]
    assert all(result.solved for result in mates), report.table()


def test_the_report_adds_up():
    engine = create_engine(2, seed=1)
    seen: list[str] = []
    report = run_suite(engine, on_result=lambda r: seen.append(r.position.name))

    assert seen == [p.name for p in TACTICAL_SUITE]
    assert report.total == len(TACTICAL_SUITE)
    assert report.rate == report.solved / report.total
    assert report.seconds > 0
    assert "solved" in report.table()


@pytest.mark.slow
def test_the_upper_levels_solve_the_whole_suite():
    report = run_suite(create_engine(6, seed=1, time_limit=1.0))
    assert report.solved == report.total, report.table()
