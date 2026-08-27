import chess
import pytest

from engine.evaluation.material import material_score
from engine.search.advanced import AdvancedSearch, SearchConfig
from engine.search.context import SearchStats
from engine.search.minimax import search_minimax
from engine.search.move_ordering import (
    CAPTURE_BASE,
    HISTORY_CAP,
    KILLER_BASE,
    TT_MOVE_SCORE,
    HistoryHeuristic,
    KillerMoves,
    mvv_lva,
    order_captures,
    order_moves,
)
from engine.search.pruning import (
    LMR_MIN_DEPTH,
    NULL_MOVE_REDUCTION,
    can_try_null_move,
    has_non_pawn_material,
    lmr_reduction,
)
from engine.search.quiescence import quiescence
from engine.utils.constants import MATE_SCORE, MATE_THRESHOLD

INF = float("inf")

# White's queen can take the d5 pawn, but c6 recaptures.
POISONED = "4k3/8/2p5/3p4/8/8/Q7/4K3 w - - 0 1"
MIDDLEGAME = "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9"

EXACT_CONFIG = SearchConfig(use_quiescence=False, check_extension=False)


def exact_search(depth: int) -> SearchConfig:
    """Level 6's techniques minus the ones that change the tree's shape."""
    return SearchConfig(
        max_depth=depth,
        use_tt=True,
        use_quiescence=False,
        use_killers=True,
        check_extension=False,
    )


# --- MVV-LVA --------------------------------------------------------------


def test_mvv_lva_prefers_the_cheap_attacker():
    """PxQ before QxQ: both win a queen, one risks far less."""
    board = chess.Board("4k3/8/8/3q4/4P3/8/8/3QK3 w - - 0 1")
    pawn_takes = chess.Move.from_uci("e4d5")
    queen_takes = chess.Move.from_uci("d1d5")
    assert mvv_lva(board, pawn_takes) > mvv_lva(board, queen_takes)


def test_mvv_lva_prefers_the_bigger_victim():
    board = chess.Board("4k3/3p1r2/8/4N3/8/8/8/4K3 w - - 0 1")
    assert mvv_lva(board, chess.Move.from_uci("e5f7")) > mvv_lva(board, chess.Move.from_uci("e5d7"))


def test_mvv_lva_values_en_passant_as_a_pawn():
    board = chess.Board("rnbqkbnr/pppp1ppp/8/3Pp3/8/8/PPP1PPPP/RNBQKBNR w KQkq e6 0 3")
    assert mvv_lva(board, chess.Move.from_uci("d5e6")) == 100 * 10 - 100


def test_order_captures_keeps_only_loud_moves():
    board = chess.Board(MIDDLEGAME)
    loud = order_captures(board, list(board.legal_moves))
    assert loud
    assert all(board.is_capture(m) or m.promotion for m in loud)


# --- killers and history --------------------------------------------------


def test_killers_remember_the_two_most_recent():
    killers = KillerMoves()
    first = chess.Move.from_uci("g1f3")
    second = chess.Move.from_uci("b1c3")
    killers.store(3, first)
    killers.store(3, second)
    assert killers.get(3) == (second, first)


def test_storing_the_same_killer_twice_does_not_evict_the_other():
    killers = KillerMoves()
    first = chess.Move.from_uci("g1f3")
    second = chess.Move.from_uci("b1c3")
    killers.store(3, first)
    killers.store(3, second)
    killers.store(3, second)
    assert killers.get(3) == (second, first)


def test_killers_are_per_ply_and_clearable():
    killers = KillerMoves()
    killers.store(3, chess.Move.from_uci("g1f3"))
    assert killers.get(4) == (None, None)
    killers.clear()
    assert killers.get(3) == (None, None)


def test_killers_ignore_plies_past_the_limit():
    killers = KillerMoves(max_ply=4)
    killers.store(99, chess.Move.from_uci("g1f3"))
    assert killers.get(99) == (None, None)


def test_history_weighs_deeper_cutoffs_more():
    history = HistoryHeuristic()
    move = chess.Move.from_uci("g1f3")
    history.record(chess.WHITE, move, 2)
    shallow = history.get(chess.WHITE, move)
    history.clear()
    history.record(chess.WHITE, move, 5)
    assert history.get(chess.WHITE, move) > shallow


def test_history_is_per_colour():
    history = HistoryHeuristic()
    move = chess.Move.from_uci("g1f3")
    history.record(chess.WHITE, move, 4)
    assert history.get(chess.BLACK, move) == 0


def test_history_halves_itself_instead_of_saturating():
    """One move must not be able to climb into the killer band and stay there."""
    history = HistoryHeuristic()
    move = chess.Move.from_uci("g1f3")
    other = chess.Move.from_uci("b1c3")
    history.record(chess.WHITE, other, 10)
    before_other = history.get(chess.WHITE, other)
    for _ in range(400):
        history.record(chess.WHITE, move, 20)
    assert history.get(chess.WHITE, move) <= HISTORY_CAP
    assert history.get(chess.WHITE, other) < before_other  # aged down with it


# --- full ordering --------------------------------------------------------


def test_ordering_puts_the_table_move_first():
    board = chess.Board(MIDDLEGAME)
    quiet = next(m for m in board.legal_moves if not board.is_capture(m))
    ordered = order_moves(board, list(board.legal_moves), tt_move=quiet)
    assert ordered[0] == quiet


def test_ordering_bands_do_not_overlap():
    board = chess.Board(MIDDLEGAME)
    assert TT_MOVE_SCORE > CAPTURE_BASE > KILLER_BASE > HISTORY_CAP
    moves = list(board.legal_moves)
    killers = KillerMoves()
    killer = next(m for m in moves if not board.is_capture(m))
    killers.store(0, killer)
    ordered = order_moves(board, moves, killers=killers, ply=0)

    captures = [m for m in ordered if board.is_capture(m) or m.promotion]
    assert ordered[: len(captures)] == captures  # captures lead
    assert ordered[len(captures)] == killer  # then the killer


def test_ordering_keeps_every_move():
    board = chess.Board(MIDDLEGAME)
    moves = list(board.legal_moves)
    ordered = order_moves(board, moves, history=HistoryHeuristic())
    assert sorted(m.uci() for m in ordered) == sorted(m.uci() for m in moves)


# --- quiescence -----------------------------------------------------------


def test_quiescence_sees_the_recapture_a_static_eval_misses():
    board = chess.Board(POISONED)
    board.push_san("Qxd5")
    static = -material_score(board)  # Black's view: a pawn down
    stats = SearchStats()
    settled = quiescence(board, -INF, INF, material_score, stats, ply=0)
    assert static < 0 < settled  # cxd5 wins the queen


def test_quiescence_stands_pat_in_a_quiet_position():
    board = chess.Board("4k3/8/8/8/8/8/8/4K2R w - - 0 1")
    stats = SearchStats()
    score = quiescence(board, -INF, INF, material_score, stats, ply=0)
    assert score == material_score(board)
    assert stats.nodes == 1  # nothing to search


def test_quiescence_does_not_stand_pat_in_check():
    """Being a queen up is no comfort if you are mated on the spot."""
    board = chess.Board("6k1/5ppp/8/8/8/8/8/R5RK b - - 0 1")
    board.push_san("Kh8")
    stats = SearchStats()
    score = quiescence(board, -INF, INF, material_score, stats, ply=0)
    assert score >= 0  # White to move, about to mate or win material


def test_quiescence_reports_mate_when_there_are_no_evasions():
    board = chess.Board("6k1/5ppp/8/8/8/8/8/R5RK w - - 0 1")
    board.push_san("Ra8+")
    stats = SearchStats()
    score = quiescence(board, -INF, INF, material_score, stats, ply=2)
    assert score == -(MATE_SCORE - 2)


def test_quiescence_leaves_the_board_alone():
    board = chess.Board(MIDDLEGAME)
    before = board.fen()
    quiescence(board, -INF, INF, material_score, SearchStats(), ply=0)
    assert board.fen() == before


# --- pruning helpers ------------------------------------------------------


def test_non_pawn_material_detection():
    assert has_non_pawn_material(chess.Board(), chess.WHITE)
    pawns_only = chess.Board("4k3/pppppppp/8/8/8/8/PPPPPPPP/4K3 w - - 0 1")
    assert not has_non_pawn_material(pawns_only, chess.WHITE)


def test_null_move_is_refused_where_it_is_unsafe():
    board = chess.Board(MIDDLEGAME)
    assert can_try_null_move(board, depth=4, in_check=False)
    assert not can_try_null_move(board, depth=1, in_check=False)  # too shallow
    assert not can_try_null_move(board, depth=4, in_check=True)  # illegal anyway

    # Zugzwang country: with only pawns, passing is not a safe assumption.
    pawns_only = chess.Board("4k3/pppppppp/8/8/8/8/PPPPPPPP/4K3 w - - 0 1")
    assert not can_try_null_move(pawns_only, depth=4, in_check=False)


def test_null_move_never_verifies_at_zero_depth():
    """``depth - 1 - R`` must leave a real ply under the verification search.

    Otherwise the cutoff is decided by quiescence alone — a gamble taken in
    exchange for no depth at all, which is exactly the case that cost Level 7
    its edge over Level 6 at a fast time control.
    """
    board = chess.Board(MIDDLEGAME)
    for depth in range(1, 12):
        if can_try_null_move(board, depth, in_check=False):
            assert depth - 1 - NULL_MOVE_REDUCTION >= 1, f"depth {depth} verifies at zero"


def test_lmr_leaves_early_and_shallow_moves_alone():
    assert lmr_reduction(depth=LMR_MIN_DEPTH - 1, move_index=10) == 0
    assert lmr_reduction(depth=6, move_index=0) == 0


def test_lmr_reduces_later_moves_more_but_never_past_quiescence():
    assert lmr_reduction(6, 3) < lmr_reduction(6, 10)
    for depth in range(3, 12):
        for index in range(0, 30):
            reduction = lmr_reduction(depth, index)
            assert 0 <= reduction <= depth - 2


# --- the search itself ----------------------------------------------------


@pytest.mark.parametrize("fen", [chess.STARTING_FEN, MIDDLEGAME, POISONED])
@pytest.mark.parametrize("depth", [2, 3])
def test_exact_techniques_do_not_change_the_score(fen, depth):
    """A transposition table and better ordering must not alter the answer.

    Level 6 adds nothing that guesses, so at the same depth and evaluation it
    has to agree with plain minimax — the same equivalence that protects
    alpha-beta, extended to the table and the killers.
    """
    board = chess.Board(fen)
    reference = search_minimax(board, depth, material_score, SearchStats())
    search = AdvancedSearch(material_score, exact_search(depth))
    result = search.search(board, SearchStats())
    assert result.score == reference.score


def test_quiescence_changes_the_score_on_purpose():
    """The same search with quiescence rejects the material a shallow one grabs."""
    board = chess.Board(POISONED)
    naive = AdvancedSearch(material_score, exact_search(1)).search(board, SearchStats())
    settled = AdvancedSearch(
        material_score, SearchConfig(max_depth=1, check_extension=False)
    ).search(board, SearchStats())

    assert board.san(naive.move) == "Qxd5"
    assert board.san(settled.move) != "Qxd5"
    assert settled.score < naive.score


@pytest.mark.parametrize(
    "config",
    [
        SearchConfig(max_depth=4),
        SearchConfig(
            max_depth=4,
            use_history=True,
            use_null_move=True,
            use_lmr=True,
            use_aspiration=True,
        ),
    ],
    ids=["level6-style", "level7-style"],
)
def test_every_configuration_finds_mate_in_two(config):
    board = chess.Board("r1b2k1r/ppp1bppp/8/1B1Q4/5q2/2P5/PPP2PPP/R3R1K1 w - - 1 0")
    result = AdvancedSearch(material_score, config).search(board, SearchStats())
    assert board.san(result.move) == "Qd8+"
    assert result.score > MATE_THRESHOLD


def test_search_leaves_the_board_untouched():
    board = chess.Board(MIDDLEGAME)
    before = board.fen()
    AdvancedSearch(material_score, SearchConfig(max_depth=4)).search(board, SearchStats())
    assert board.fen() == before


def test_timeout_returns_a_usable_move_and_rewinds_the_board():
    board = chess.Board(MIDDLEGAME)
    board.push_san("O-O")
    before, stack = board.fen(), len(board.move_stack)
    search = AdvancedSearch(material_score, SearchConfig(max_depth=20))
    result = search.search(board, SearchStats(time_limit=0.05))
    assert board.fen() == before and len(board.move_stack) == stack
    assert result.move in board.legal_moves
    assert 0 < result.depth < 20


def test_search_raises_without_legal_moves():
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    with pytest.raises(ValueError):
        AdvancedSearch(material_score, SearchConfig(max_depth=3)).search(board, SearchStats())


def test_the_table_is_reused_between_moves_and_cleared_between_games():
    search = AdvancedSearch(material_score, SearchConfig(max_depth=3))
    search.search(chess.Board(), SearchStats())
    assert len(search.tt) > 0
    search.new_game()
    assert len(search.tt) == 0
    assert search.killers.get(1) == (None, None)


def test_pruning_shrinks_the_tree_at_equal_depth():
    """Null move and LMR exist to buy depth; at fixed depth they cost nodes."""
    board = chess.Board(MIDDLEGAME)
    exact_stats = SearchStats()
    AdvancedSearch(material_score, SearchConfig(max_depth=5)).search(board, exact_stats)
    pruned_stats = SearchStats()
    AdvancedSearch(
        material_score,
        SearchConfig(
            max_depth=5,
            use_history=True,
            use_null_move=True,
            use_lmr=True,
            use_aspiration=True,
        ),
    ).search(board, pruned_stats)
    assert pruned_stats.nodes < exact_stats.nodes / 2


# --- generating the quiescence move list ---------------------------------


def test_loud_moves_are_generated_not_filtered():
    """The same list either way — one costs four times less.

    Quiescence used to build every legal move and throw most of them away,
    which was 6.6 move generations per node. Asking for the captures directly
    and adding the quiet promotions gives an identical list.
    """
    from engine.search.move_ordering import generate_loud_moves

    for fen in (MIDDLEGAME, POISONED, chess.STARTING_FEN):
        board = chess.Board(fen)
        generated = sorted(move.uci() for move in generate_loud_moves(board))
        filtered = sorted(
            move.uci() for move in board.legal_moves if board.is_capture(move) or move.promotion
        )
        assert generated == filtered


def test_loud_moves_include_en_passant_and_quiet_promotions():
    from engine.search.move_ordering import generate_loud_moves

    en_passant = chess.Board("rnbqkbnr/pppp1ppp/8/3Pp3/8/8/PPP1PPPP/RNBQKBNR w KQkq e6 0 3")
    assert "d5e6" in [move.uci() for move in generate_loud_moves(en_passant)]

    # A promotion that captures nothing is still forcing.
    promotion = chess.Board("8/P7/8/8/8/8/8/K6k w - - 0 1")
    assert any(move.promotion for move in generate_loud_moves(promotion))


def test_loud_moves_are_ordered_by_what_they_win():
    from engine.search.move_ordering import order_loud_moves

    board = chess.Board("4k3/3p1r2/8/4N3/8/8/8/4K3 w - - 0 1")
    assert board.san(order_loud_moves(board)[0]) == "Nxf7"
