"""Perft — the proof that the move generation wiring is correct.

Every other test in this suite assumes the legal moves are the legal moves.
These are the ones that check it, against counts published to the node.
"""

from __future__ import annotations

import chess
import pytest

from engine.perft import (
    PERFT_POSITIONS,
    PerftPosition,
    perft,
    perft_divide,
    run_perft,
    run_suite,
)


def test_depth_zero_is_the_position_itself():
    assert perft(chess.Board(), 0) == 1
    assert perft(chess.Board(), -1) == 1


def test_depth_one_counts_the_legal_moves():
    board = chess.Board(PERFT_POSITIONS[1].fen)  # kiwipete
    assert perft(board, 1) == board.legal_moves.count() == 48


@pytest.mark.parametrize("position", PERFT_POSITIONS, ids=lambda p: p.name)
@pytest.mark.parametrize("depth", [1, 2, 3])
def test_published_counts_match(position: PerftPosition, depth: int):
    assert perft(chess.Board(position.fen), depth) == position.counts[depth - 1]


@pytest.mark.slow
@pytest.mark.parametrize("position", PERFT_POSITIONS, ids=lambda p: p.name)
def test_published_counts_match_deeper(position: PerftPosition):
    """Depth 4 catches what depth 3 does not — en passant pins, mostly."""
    depth = min(4, position.max_depth)
    assert perft(chess.Board(position.fen), depth) == position.counts[depth - 1]


def test_perft_leaves_the_board_alone():
    board = chess.Board(PERFT_POSITIONS[1].fen)
    before = board.fen()
    perft(board, 3)
    assert board.fen() == before


def test_divide_sums_to_the_total():
    """A wrong total says something broke; a divide says which move."""
    board = chess.Board(PERFT_POSITIONS[1].fen)
    divided = perft_divide(board, 3)
    assert len(divided) == board.legal_moves.count()
    assert sum(divided.values()) == perft(board, 3)
    assert all(chess.Move.from_uci(uci) in board.legal_moves for uci in divided)


def test_divide_at_depth_zero_is_empty():
    assert perft_divide(chess.Board(), 0) == {}


def test_a_result_knows_whether_it_matched():
    result = run_perft(PERFT_POSITIONS[0], 2)
    assert result.matches and result.expected == 400
    assert result.nps > 0 and result.seconds > 0


def test_a_depth_past_the_published_counts_has_nothing_to_check_against():
    """A one-line branch, tested on a position small enough to be free.

    Asking kiwipete for one depth past what it publishes would run perft 5 —
    193 million nodes, and it cost 70% of the whole fast test suite before
    anyone looked at the timings.
    """
    shallow = PerftPosition("startpos-shallow", chess.STARTING_FEN, (20,))
    result = run_perft(shallow, shallow.max_depth + 1)
    assert result.nodes == 400  # depth 2
    assert result.expected is None
    assert result.matches  # nothing to contradict


def test_the_suite_reports_every_position():
    seen: list[str] = []
    suite = run_suite(depth=2, on_result=lambda r: seen.append(r.name))
    assert seen == [p.name for p in PERFT_POSITIONS]
    assert suite.passed
    assert suite.nodes == sum(p.counts[1] for p in PERFT_POSITIONS)
    assert "position" in suite.table() and "nps" in suite.table()


def test_the_suite_clamps_to_what_each_position_publishes():
    """Clamping is what the assertion is about; depth 2 shows it just as well."""
    shallow = tuple(PerftPosition(p.name, p.fen, p.counts[:2]) for p in PERFT_POSITIONS)
    suite = run_suite(depth=9, positions=shallow)
    for result, position in zip(suite.results, shallow):
        assert result.depth == position.max_depth == 2
        assert result.expected is not None
    assert suite.passed
