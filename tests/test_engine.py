import chess
import pytest

from engine.base_engine import BaseEngine, SearchResult
from engine.levels import (
    Level1Random,
    Level2Material,
    Level3Minimax,
    Level4AlphaBeta,
    Level5Positional,
    Level6Tactical,
    Level7Advanced,
    Level8Neural,
    available_levels,
    create_engine,
)
from engine.utils.constants import INITIAL_ELO, MATE_THRESHOLD
from tests.conftest import MATE_IN_ONE_FENS, delivers_mate
from tournament.match import play_game, play_match
from tournament.openings import book

# --- registry / base class -----------------------------------------------


def test_registry_and_factory():
    assert available_levels() == [1, 2, 3, 4, 5, 6, 7, 8]
    engine = create_engine(1, seed=7)
    assert isinstance(engine, Level1Random)
    assert engine.level == 1
    assert engine.elo == INITIAL_ELO[1]


def test_factory_rejects_a_level_outside_the_ladder():
    with pytest.raises(ValueError):
        create_engine(9)
    with pytest.raises(ValueError):
        create_engine(0)


def test_factory_reports_an_unbuilt_level_clearly(monkeypatch):
    """Every level is built now, so the guard is exercised by removing one.

    It is still worth keeping: the failure it prevents is silently falling
    back to a different engine than the one that was asked for.
    """
    from engine.levels import LEVELS

    monkeypatch.delitem(LEVELS, 8)
    with pytest.raises(NotImplementedError, match="not implemented yet"):
        create_engine(8)


def test_base_engine_is_abstract():
    with pytest.raises(TypeError):
        BaseEngine(name="nope", level=1)  # type: ignore[abstract]


def test_get_info_shape():
    info = create_engine(2).get_info()
    assert set(info) == {"name", "level", "elo", "games_played"}
    assert info["level"] == 2 and info["elo"] == 600


def test_analyse_reports_stats():
    result = create_engine(2, seed=1).analyse(chess.Board())
    assert isinstance(result, SearchResult)
    assert result.move in chess.Board().legal_moves
    assert result.nodes == 20  # 20 legal moves in the start position
    assert result.time_ms >= 0 and result.nps >= 0


# --- Level 1 --------------------------------------------------------------


def test_level1_returns_legal_move():
    engine = Level1Random(seed=42)
    board = chess.Board()
    for _ in range(200):
        move = engine.get_best_move(board)
        assert move in board.legal_moves
        board.push(move)
        if board.is_game_over():
            board.reset()


def test_level1_is_reproducible_with_a_seed():
    board = chess.Board()
    first = [Level1Random(seed=5).get_best_move(board) for _ in range(3)]
    assert len(set(first)) == 1  # same seed -> same first move
    others = {Level1Random(seed=s).get_best_move(board) for s in range(30)}
    assert len(others) > 1  # different seeds do explore different moves


def test_level1_raises_when_game_is_over():
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    with pytest.raises(ValueError):
        Level1Random().get_best_move(board)


def test_level1_has_no_evaluation():
    assert Level1Random().evaluate(chess.Board()) == 0.0


# --- Level 2 --------------------------------------------------------------


@pytest.mark.parametrize("fen", MATE_IN_ONE_FENS)
def test_level2_finds_mate_in_one(fen):
    board = chess.Board(fen)
    result = Level2Material(seed=1).analyse(board)
    assert delivers_mate(board, result.move)
    assert result.score > MATE_THRESHOLD


def test_level2_takes_free_material():
    # Black queen on d5 is undefended; White's pawn on e4 can take it.
    board = chess.Board("rnb1kbnr/ppp1pppp/8/3q4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1")
    move = Level2Material(seed=1).get_best_move(board)
    assert board.san(move) == "exd5"


def test_level2_avoids_stalemating_when_winning():
    # Qg6 would be stalemate (score 0); a queen grab of the rook scores higher.
    board = chess.Board("7k/8/8/8/8/8/5r2/K5Q1 w - - 0 1")
    move = Level2Material(seed=1).get_best_move(board)
    assert board.san(move) == "Qxf2"


def test_level2_prefers_the_bigger_capture():
    # White knight on e5 can take a pawn on d7 or a rook on f7.
    board = chess.Board("4k3/3p1r2/8/4N3/8/8/8/4K3 w - - 0 1")
    move = Level2Material(seed=1).get_best_move(board)
    assert board.san(move) == "Nxf7"


def test_level2_evaluation_is_white_relative():
    engine = Level2Material()
    board = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert engine.evaluate(board) == 900


# --- ladder ---------------------------------------------------------------


def test_engines_finish_a_game_without_illegal_moves():
    record = play_game(Level1Random(seed=1), Level2Material(seed=2), max_plies=120)
    assert record.result in ("1-0", "0-1", "1/2-1/2")
    assert record.plies > 0


@pytest.mark.slow
def test_level2_beats_level1():
    match = play_match(Level2Material(seed=1), Level1Random(seed=2), openings=book(), max_plies=200)
    assert match.score > 0.7, match.summary()


def test_base_analyse_default_path_used_by_level1():
    """Level 1 does not override analyse, so this exercises the base version."""
    engine = Level1Random(seed=3)
    result = engine.analyse(chess.Board())
    assert result.move in chess.Board().legal_moves
    assert result.depth == 1 and result.pv == [result.move]
    assert result.score == 0.0  # level 1 evaluates everything as equal
    assert engine.last_result is result
    engine.new_game()
    assert engine.last_result is None and engine.nodes == 0


# --- Level 3 & 4 ----------------------------------------------------------

# White's queen can win a pawn on d5, but it is defended by the c6 pawn.
# One ply of lookahead sees the pawn; a real search sees the queen.
POISONED_PAWN_FEN = "4k3/8/2p5/3p4/8/8/Q7/4K3 w - - 0 1"

# Morphy-style puzzle: 1. Qd8+ Bxd8 2. Re8#
MATE_IN_TWO_FEN = "r1b2k1r/ppp1bppp/8/1B1Q4/5q2/2P5/PPP2PPP/R3R1K1 w - - 1 0"

# Thinking time per move in the ladder gate tests.
GATE_TIME_LIMIT = 0.2


def test_level2_falls_for_the_poisoned_pawn():
    """The blind spot Level 3 exists to fix — documented, not accidental."""
    board = chess.Board(POISONED_PAWN_FEN)
    move = Level2Material(seed=1).get_best_move(board)
    assert board.san(move) == "Qxd5"


@pytest.mark.parametrize(
    "engine_cls", [Level3Minimax, Level4AlphaBeta, Level5Positional, Level6Tactical, Level7Advanced]
)
def test_search_levels_refuse_the_poisoned_pawn(engine_cls):
    board = chess.Board(POISONED_PAWN_FEN)
    move = engine_cls(seed=1).get_best_move(board)
    assert board.san(move) != "Qxd5"


@pytest.mark.parametrize(
    "engine_cls", [Level3Minimax, Level4AlphaBeta, Level5Positional, Level6Tactical, Level7Advanced]
)
def test_search_levels_find_mate_in_two(engine_cls):
    board = chess.Board(MATE_IN_TWO_FEN)
    result = engine_cls(seed=1).analyse(board)
    assert board.san(result.move) == "Qd8+"
    assert result.score > MATE_THRESHOLD
    assert [m.uci() for m in result.pv] == ["d5d8", "e7d8", "e1e8"]


@pytest.mark.parametrize(
    "engine_cls", [Level3Minimax, Level4AlphaBeta, Level5Positional, Level6Tactical, Level7Advanced]
)
@pytest.mark.parametrize("fen", MATE_IN_ONE_FENS)
def test_search_levels_still_find_mate_in_one(engine_cls, fen):
    board = chess.Board(fen)
    result = engine_cls(seed=1).analyse(board)
    assert delivers_mate(board, result.move)
    assert result.score > MATE_THRESHOLD


def test_level3_reports_its_depth_and_a_legal_pv():
    board = chess.Board()
    result = Level3Minimax(seed=1).analyse(board)
    assert result.depth == 3
    replay = chess.Board()
    for move in result.pv:
        assert move in replay.legal_moves
        replay.push(move)


def test_level4_deepens_further_on_fewer_nodes_than_level3():
    board = chess.Board()
    l3 = Level3Minimax(seed=1).analyse(board)
    l4 = Level4AlphaBeta(seed=1).analyse(board)
    assert l4.depth == 4 > l3.depth
    assert l4.nodes < l3.nodes


def test_level4_respects_a_time_limit():
    """A tight budget must still produce a legal move from a shallower depth."""
    board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
    engine = Level4AlphaBeta(seed=1, time_limit=0.01)
    result = engine.analyse(board)
    assert result.move in board.legal_moves
    assert result.time_ms < 500


def test_search_engines_evaluate_from_white_perspective():
    board = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert Level3Minimax().evaluate(board) == 900
    assert Level4AlphaBeta().evaluate(board) == 900


@pytest.mark.parametrize(
    "engine_cls", [Level3Minimax, Level4AlphaBeta, Level5Positional, Level6Tactical, Level7Advanced]
)
def test_search_levels_raise_when_game_is_over(engine_cls):
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    with pytest.raises(ValueError):
        engine_cls().get_best_move(board)


@pytest.mark.slow
@pytest.mark.parametrize("higher,lower", [(3, 2), (4, 3), (5, 4), (6, 5), (7, 6)])
def test_level_beats_the_one_below(higher, lower):
    """Regression guard, not the headline number.

    Twelve games is far too small a sample to certify the ">70% against the
    level below" success criterion — at a true 80% it would fail by chance
    about one run in five. So the threshold here is set where only a real
    regression trips it, and ``scripts/ladder.py`` runs the long gauntlet
    that produces the number quoted in the README.

    Every engine gets the same short thinking time, which is both how engines
    are normally compared and the only way to keep this bounded: Level 5 at
    its native settings spends a couple of seconds on a middlegame move.
    """
    match = play_match(
        create_engine(higher, seed=higher * 10, time_limit=GATE_TIME_LIMIT),
        create_engine(lower, seed=lower * 10 + 1, time_limit=GATE_TIME_LIMIT),
        openings=book(6),
        max_plies=200,
    )
    assert match.score > 0.6, match.summary()


# --- Level 5 --------------------------------------------------------------


def test_level5_opens_with_a_central_pawn():
    """Piece-square tables at work: Level 4 has no reason to prefer 1.e4."""
    board = chess.Board()
    move = Level5Positional(seed=1).get_best_move(board)
    assert board.san(move) in {"e4", "d4"}


def test_level5_develops_knights_towards_the_centre():
    engine = Level5Positional(seed=1)
    rim = chess.Board("4k3/8/8/8/8/8/8/N3K3 w - - 0 1")
    centre = chess.Board("4k3/8/8/8/4N3/8/8/4K3 w - - 0 1")
    assert engine.static_eval(centre) > engine.static_eval(rim)


def test_level5_dislikes_doubled_isolated_pawns():
    engine = Level5Positional(seed=1)
    healthy = chess.Board("4k3/8/8/8/8/8/1PP5/4K3 w - - 0 1")
    ruined = chess.Board("4k3/8/8/8/8/2P5/2P5/4K3 w - - 0 1")
    assert engine.static_eval(healthy) > engine.static_eval(ruined)


def test_level5_values_the_bishop_pair():
    engine = Level5Positional(seed=1)
    pair = chess.Board("4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1")
    bishop_and_knight = chess.Board("4k3/8/8/8/8/8/8/2B1KN2 w - - 0 1")
    # A bishop is worth 10 more than a knight, and the pair adds 30 on top.
    assert engine.static_eval(pair) - engine.static_eval(bishop_and_knight) > 30


def test_level5_evaluation_stays_white_relative():
    engine = Level5Positional(seed=1)
    white_up = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    black_up = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1")
    assert engine.static_eval(white_up) > 800
    assert engine.static_eval(white_up) == -engine.static_eval(black_up)


def test_level5_reports_depth_five():
    result = Level5Positional(seed=1).analyse(chess.Board())
    assert result.depth == 5
    assert result.nodes > 0


# --- Levels 6 & 7 ---------------------------------------------------------


@pytest.mark.parametrize("engine_cls", [Level6Tactical, Level7Advanced])
def test_quiescence_stops_the_horizon_grab_that_level5_falls_for(engine_cls):
    """Same evaluation, same one-ply search — only quiescence differs.

    At depth 1 Level 5 sees a free pawn and takes it with the queen. Levels 6
    and 7 keep searching the captures past that ply, see cxd5, and decline.
    """
    board = chess.Board(POISONED_PAWN_FEN)
    assert board.san(Level5Positional(seed=1, depth=1).get_best_move(board)) == "Qxd5"
    move = engine_cls(seed=1, depth=1).get_best_move(board)
    assert board.san(move) != "Qxd5"


@pytest.mark.slow
def test_level7_searches_deeper_than_level6_in_the_same_time():
    """Level 7's whole advantage: the same clock buys more plies.

    Marked slow and given a generous budget on purpose. With a short limit
    the two levels finish the same iteration and tie, which says nothing —
    the gap only opens once there is time for an iteration Level 6 cannot
    afford. The deterministic version of this claim is
    ``test_pruning_shrinks_the_tree_at_equal_depth``.
    """
    board = chess.Board("r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9")
    six = Level6Tactical(seed=1, time_limit=2.0).analyse(board)
    seven = Level7Advanced(seed=1, time_limit=2.0).analyse(board)
    assert seven.depth > six.depth, f"L6 reached {six.depth}, L7 reached {seven.depth}"


@pytest.mark.parametrize("engine_cls", [Level6Tactical, Level7Advanced])
def test_advanced_levels_clear_their_memory_between_games(engine_cls):
    engine = engine_cls(seed=1, time_limit=0.2)
    engine.analyse(chess.Board())
    assert len(engine.searcher.tt) > 0
    engine.new_game()
    assert len(engine.searcher.tt) == 0
    assert engine.last_result is None


@pytest.mark.parametrize("engine_cls", [Level6Tactical, Level7Advanced])
def test_advanced_levels_keep_the_white_relative_convention(engine_cls):
    engine = engine_cls(seed=1)
    white_up = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    black_up = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1")
    assert engine.static_eval(white_up) == -engine.static_eval(black_up) > 800


def test_level6_and_level7_report_a_playable_pv():
    board = chess.Board("r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9")
    for engine in (Level6Tactical(seed=1, time_limit=0.3), Level7Advanced(seed=1, time_limit=0.3)):
        result = engine.analyse(board)
        replay = board.copy()
        for move in result.pv:
            assert move in replay.legal_moves, f"{engine.name} produced an illegal PV"
            replay.push(move)
        assert result.depth >= 1


@pytest.mark.parametrize(
    "engine_cls", [Level4AlphaBeta, Level5Positional, Level6Tactical, Level7Advanced, Level8Neural]
)
def test_the_depth_attribute_is_what_the_search_obeys(engine_cls):
    """Every level, not just the ones whose search reads it directly.

    Levels 6 and up build a searcher whose config used to freeze the depth at
    construction, so assigning `engine.depth` was accepted and ignored.
    """
    engine = engine_cls(seed=1, time_limit=None)
    engine.depth = 3
    assert engine.analyse(chess.Board()).depth == 3

    engine.depth = 4
    assert engine.analyse(chess.Board()).depth == 4
