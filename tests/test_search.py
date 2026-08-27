import time

import chess
import pytest

from engine.evaluation.material import material_score
from engine.search.alphabeta import search_alphabeta
from engine.search.context import (
    SearchStats,
    SearchTimeout,
    is_draw,
    unwind_to,
)
from engine.search.minimax import search_minimax
from engine.search.move_ordering import (
    basic_move_score,
    captures_first,
    order_moves_basic,
)
from engine.utils.constants import MATE_SCORE

POSITIONS = [
    chess.STARTING_FEN,
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
]


# --- alpha-beta must be minimax, only cheaper ----------------------------


@pytest.mark.parametrize("fen", POSITIONS)
@pytest.mark.parametrize("depth", [1, 2, 3])
def test_alphabeta_returns_the_same_score_as_minimax(fen, depth):
    """The defining property of alpha-beta: it prunes without changing the answer."""
    board = chess.Board(fen)
    moves = list(board.legal_moves)  # identical root order for both searches

    mm_stats, ab_stats = SearchStats(), SearchStats()
    mm = search_minimax(board, depth, material_score, mm_stats, root_moves=list(moves))
    ab = search_alphabeta(
        board, depth, material_score, ab_stats, root_moves=list(moves), min_depth=depth
    )

    assert ab.score == mm.score
    assert ab_stats.nodes <= mm_stats.nodes


def test_alphabeta_prunes_a_large_fraction_of_the_tree():
    board = chess.Board()
    mm_stats, ab_stats = SearchStats(), SearchStats()
    search_minimax(board, 4, material_score, mm_stats)
    search_alphabeta(board, 4, material_score, ab_stats)
    assert ab_stats.nodes < mm_stats.nodes / 10


@pytest.mark.parametrize("search", [search_minimax, search_alphabeta])
def test_search_leaves_the_board_untouched(search):
    board = chess.Board(POSITIONS[1])
    before = board.fen()
    search(board, 3, material_score)
    assert board.fen() == before


@pytest.mark.parametrize("search", [search_minimax, search_alphabeta])
def test_search_raises_without_legal_moves(search):
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    with pytest.raises(ValueError):
        search(board, 3, material_score)


@pytest.mark.parametrize("search", [search_minimax, search_alphabeta])
def test_pv_is_a_playable_line(search):
    board = chess.Board(POSITIONS[2])
    result = search(board, 3, material_score)
    replay = board.copy()
    for move in result.pv:
        assert move in replay.legal_moves
        replay.push(move)
    assert len(result.pv) >= 1


# --- mate handling --------------------------------------------------------


def test_search_prefers_the_faster_mate():
    """Rf8# now, or a slower rook-ladder mate — the score must pick the quick one."""
    board = chess.Board("6k1/5ppp/8/8/8/8/8/R4R1K w - - 0 1")
    result = search_alphabeta(board, 4, material_score)
    assert result.score == MATE_SCORE - 1  # mate delivered on the first ply
    board.push(result.move)
    assert board.is_checkmate()


def test_search_sees_it_is_being_mated():
    """Black to move with only Kg8 available, and Ra8# waiting after it."""
    board = chess.Board("7k/8/6K1/8/8/8/8/R7 b - - 0 1")
    result = search_alphabeta(board, 3, material_score)
    assert result.score == -(MATE_SCORE - 2)  # mated two plies from here


def test_stalemate_scores_as_a_draw_not_a_loss():
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert board.is_stalemate()
    # From the root there are no moves at all, so the search itself refuses.
    with pytest.raises(ValueError):
        search_alphabeta(board, 2, material_score)


# --- draw detection -------------------------------------------------------


def test_is_draw_insufficient_material():
    assert is_draw(chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1"))
    assert not is_draw(chess.Board())


def test_is_draw_fifty_move_rule():
    board = chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 99 60")
    board.halfmove_clock = 100
    assert is_draw(board)


def test_is_draw_repetition():
    board = chess.Board()
    for _ in range(2):
        for san in ["Nf3", "Nf6", "Ng1", "Ng8"]:
            board.push_san(san)
    assert is_draw(board)


# --- time control ---------------------------------------------------------


def test_stats_tick_raises_once_the_budget_is_spent():
    stats = SearchStats(time_limit=0.0, check_interval=1)
    stats.start = time.perf_counter() - 1.0
    with pytest.raises(SearchTimeout):
        stats.tick()


def test_stats_without_a_limit_never_times_out():
    stats = SearchStats(check_interval=1)
    for _ in range(10):
        stats.tick()
    assert stats.nodes == 10 and not stats.out_of_time()


@pytest.mark.parametrize("search", [search_minimax, search_alphabeta])
def test_timeout_restores_the_board_and_returns_a_legal_move(search):
    """Regression: an aborted search must not leave pushed moves on the board."""
    board = chess.Board(POSITIONS[2])
    board.push_san("O-O")
    before, stack = board.fen(), len(board.move_stack)

    result = search(board, 6, material_score, SearchStats(time_limit=0.02))

    assert board.fen() == before
    assert len(board.move_stack) == stack
    assert result.move in board.legal_moves


def test_iterative_deepening_reports_the_depth_it_completed():
    board = chess.Board(POSITIONS[2])
    shallow = search_alphabeta(board, 8, material_score, SearchStats(time_limit=0.05))
    deep = search_alphabeta(board, 4, material_score)
    assert 0 < shallow.depth < 8
    assert deep.depth == 4


def test_unwind_to_takes_back_only_the_extra_moves():
    board = chess.Board()
    board.push_san("e4")
    depth = len(board.move_stack)
    board.push_san("e5")
    board.push_san("Nf3")
    unwind_to(board, depth)
    assert len(board.move_stack) == depth


# --- move ordering --------------------------------------------------------


def test_captures_and_promotions_sort_ahead_of_quiet_moves():
    board = chess.Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
    ordered = order_moves_basic(board, list(board.legal_moves))
    assert board.san(ordered[0]) == "exd5"


def test_ordering_prefers_the_valuable_victim():
    board = chess.Board("4k3/3p1r2/8/4N3/8/8/8/4K3 w - - 0 1")
    ordered = order_moves_basic(board, list(board.legal_moves))
    assert board.san(ordered[0]) == "Nxf7"  # rook before pawn
    assert basic_move_score(board, chess.Move.from_uci("e5f7")) > basic_move_score(
        board, chess.Move.from_uci("e5d7")
    )


def test_promotion_outranks_a_plain_capture():
    board = chess.Board("6r1/P7/8/8/8/8/8/K5k1 w - - 0 1")
    ordered = order_moves_basic(board, list(board.legal_moves))
    assert ordered[0].promotion == chess.QUEEN


def test_ordering_keeps_every_move():
    board = chess.Board(POSITIONS[2])
    moves = list(board.legal_moves)
    expected = sorted(m.uci() for m in moves)
    assert sorted(m.uci() for m in order_moves_basic(board, moves)) == expected
    assert sorted(m.uci() for m in captures_first(board, moves)) == expected


def test_captures_first_partitions_without_sorting():
    board = chess.Board(POSITIONS[2])
    moves = list(board.legal_moves)
    partitioned = captures_first(board, moves)
    loud = [m for m in partitioned if board.is_capture(m) or m.promotion]
    assert partitioned[: len(loud)] == loud
