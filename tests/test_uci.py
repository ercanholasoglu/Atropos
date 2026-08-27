"""The UCI layer: parsing, options, the clock, and the engine loop.

The protocol's rules are unforgiving in one direction only — a GUI that gets
no `bestmove` waits forever, and an engine that crashes on a stray token
forfeits. Most of these tests are about those two failure modes.
"""

from __future__ import annotations

import io
import threading
import time

import chess
import pytest

from engine.utils.constants import MATE_SCORE, MATE_THRESHOLD
from uci.engine import UciEngine
from uci.options import EngineOptions, describe_options, parse_setoption, set_option
from uci.protocol import format_score, parse_command, parse_go, parse_position
from uci.time_manager import allocate

MIDDLEGAME = "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9"
CHECKMATE = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"


@pytest.fixture
def engine():
    instance = UciEngine(io.StringIO(), io.StringIO())
    yield instance
    instance.request_stop(join=True)


def drive(engine: UciEngine, *lines: str) -> str:
    """Feed lines and return everything written to the output stream."""
    engine.output.truncate(0)
    engine.output.seek(0)
    for line in lines:
        engine.handle_line(line)
    return engine.output.getvalue()


def finish(engine: UciEngine) -> str:
    if engine._search_thread is not None:
        engine._search_thread.join(timeout=30)
    return engine.output.getvalue()


# --- protocol -------------------------------------------------------------


def test_a_blank_line_is_not_a_command():
    assert parse_command("   ") is None
    assert parse_command("") is None


def test_a_command_splits_into_name_and_arguments():
    command = parse_command("  position startpos moves e2e4  ")
    assert command.name == "position"
    assert command.args == ("startpos", "moves", "e2e4")
    assert command.text == "position startpos moves e2e4"


def test_go_reads_the_clock_in_seconds():
    params = parse_go("wtime 300000 btime 295000 winc 2000 binc 1000 movestogo 40".split())
    assert (params.wtime, params.btime) == (300.0, 295.0)
    assert (params.winc, params.binc) == (2.0, 1.0)
    assert params.movestogo == 40 and params.has_clock


def test_go_accepts_contradictory_but_legal_combinations():
    params = parse_go("infinite depth 8".split())
    assert params.infinite and params.depth == 8


def test_go_skips_junk_rather_than_failing():
    """An engine that dies on a stray token forfeits the game."""
    params = parse_go("depth notanumber wobble movetime 1500 --flag".split())
    assert params.depth is None
    assert params.movetime == 1.5


def test_go_searchmoves_stops_at_the_next_keyword():
    params = parse_go("searchmoves e2e4 d2d4 zzz depth 3".split())
    assert [m.uci() for m in params.searchmoves] == ["e2e4", "d2d4"]
    assert params.depth == 3


def test_position_startpos_with_moves():
    parsed = parse_position("startpos moves e2e4 e7e5 g1f3".split())
    assert parsed.board().fen().startswith("rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2")


def test_position_from_fen():
    parsed = parse_position(f"fen {MIDDLEGAME}".split())
    assert parsed.board().fen() == MIDDLEGAME


def test_position_stops_at_an_illegal_move_instead_of_corrupting_the_board():
    parsed = parse_position("startpos moves e2e4 e2e5 d2d4".split())
    board = parsed.board()
    assert board.fullmove_number == 1 and board.turn == chess.BLACK


def test_position_rejects_what_it_cannot_read():
    assert parse_position("wat".split()) is None
    assert parse_position([]) is None
    assert parse_position("fen not-a-fen".split()) is None


def test_scores_are_reported_in_the_two_forms_uci_knows():
    assert format_score(123, MATE_THRESHOLD) == "cp 123"
    assert format_score(MATE_SCORE - 3, MATE_THRESHOLD) == "mate 2"
    assert format_score(-(MATE_SCORE - 4), MATE_THRESHOLD) == "mate -2"


# --- options --------------------------------------------------------------


def test_the_level_is_an_option_because_the_ladder_is_the_product():
    names = [description.name for description in describe_options()]
    assert "Level" in names
    level = next(d for d in describe_options() if d.name == "Level")
    assert level.to_uci() == "option name Level type spin default 7 min 1 max 8"


def test_setoption_names_can_contain_spaces():
    assert parse_setoption("name Move Overhead value 120".split()) == ("Move Overhead", "120")
    assert parse_setoption("name Clear Hash".split()) == ("Clear Hash", "")
    assert parse_setoption("value 3".split()) is None


def test_options_are_clamped_not_rejected():
    options = EngineOptions()
    set_option(options, "Level", "99")
    assert options.level == 8
    set_option(options, "Hash", "99999")
    assert options.hash_mb == 1024


def test_a_value_that_is_not_a_number_leaves_the_setting_alone():
    options = EngineOptions()
    assert not set_option(options, "Hash", "lots")
    assert options.hash_mb == 16


def test_unknown_options_are_reported_not_applied():
    assert not set_option(EngineOptions(), "Nonsense", "3")


def test_threads_is_declared_honestly():
    options = EngineOptions()
    set_option(options, "Threads", "8")
    assert options.threads == 1


# --- the clock ------------------------------------------------------------


def test_movetime_is_honoured_minus_the_overhead():
    budget = allocate(parse_go("movetime 5000".split()), chess.WHITE, move_overhead_ms=30)
    assert budget.seconds == pytest.approx(4.97)


def test_a_clock_is_spread_over_the_moves_still_to_come():
    budget = allocate(parse_go("wtime 300000 btime 300000 movestogo 40".split()), chess.WHITE)
    assert budget.seconds == pytest.approx(300 / 40, abs=0.05)


def test_the_increment_is_mostly_spendable():
    without = allocate(parse_go("wtime 60000 btime 60000".split()), chess.WHITE).seconds
    with_increment = allocate(
        parse_go("wtime 60000 btime 60000 winc 2000 binc 2000".split()), chess.WHITE
    ).seconds
    assert with_increment > without
    assert with_increment - without == pytest.approx(1.5, abs=0.01)


def test_no_single_move_may_eat_the_clock():
    """Even 'one move to go' does not license spending all of it."""
    budget = allocate(parse_go("wtime 300000 btime 300000 movestogo 1".split()), chess.WHITE)
    assert budget.seconds < 300 * 0.5


def test_a_nearly_flagged_clock_still_returns_something_playable():
    budget = allocate(parse_go("wtime 100 btime 300000".split()), chess.WHITE)
    assert 0 < budget.seconds < 0.1


def test_each_side_reads_its_own_clock():
    params = parse_go("wtime 300000 btime 6000".split())
    assert allocate(params, chess.WHITE).seconds > allocate(params, chess.BLACK).seconds


def test_infinite_and_ponder_have_no_deadline():
    assert allocate(parse_go(["infinite"]), chess.WHITE).infinite
    assert allocate(parse_go(["ponder"]), chess.WHITE).infinite


def test_a_fixed_depth_with_no_clock_is_not_timed():
    budget = allocate(parse_go("depth 6".split()), chess.WHITE)
    assert budget.depth == 6 and budget.seconds is None


def test_go_with_nothing_at_all_still_gets_a_budget():
    budget = allocate(parse_go([]), chess.WHITE, default_seconds=2.0)
    assert budget.seconds == 2.0


# --- the engine loop ------------------------------------------------------


def test_the_handshake_advertises_the_engine_and_its_options(engine):
    text = drive(engine, "uci")
    assert "id name chess-bot" in text
    assert "option name Level" in text
    assert text.strip().endswith("uciok")


def test_an_unknown_command_is_ignored_and_noted(engine):
    assert drive(engine, "flibbertigibbet") == ""
    assert "unknown command" in engine.log.getvalue()


def test_a_search_produces_exactly_one_bestmove(engine):
    drive(engine, "setoption name Level value 4", "position startpos", "go movetime 300")
    text = finish(engine)
    assert text.count("bestmove ") == 1
    assert "info depth" in text
    move = text.strip().splitlines()[-1].split()[1]
    assert chess.Move.from_uci(move) in chess.Board().legal_moves


def test_stop_ends_an_infinite_search_and_still_answers(engine):
    drive(engine, "setoption name Level value 6", f"position fen {MIDDLEGAME}", "go infinite")
    time.sleep(0.4)
    engine.handle_line("stop")
    text = finish(engine)
    assert text.count("bestmove ") == 1


def test_isready_is_answered_while_the_engine_is_thinking(engine):
    """A GUI uses it as a heartbeat, including mid-search."""
    drive(engine, "setoption name Level value 6", f"position fen {MIDDLEGAME}", "go infinite")
    time.sleep(0.2)
    engine.handle_line("isready")
    assert "readyok" in engine.output.getvalue()
    engine.handle_line("stop")
    finish(engine)


def test_a_finished_game_answers_with_the_null_move(engine):
    text = drive(engine, f"position fen {CHECKMATE}", "go movetime 100")
    assert "bestmove 0000" in text


def test_scores_are_reported_from_the_side_to_moves_point_of_view(engine):
    """White-relative inside the engine, mover-relative on the wire."""
    black_up = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1"
    drive(engine, "setoption name Level value 4", f"position fen {black_up}", "go movetime 200")
    text = finish(engine)
    scores = [
        int(line.split("score cp ")[1].split()[0])
        for line in text.splitlines()
        if "score cp " in line
    ]
    assert scores and all(score < 0 for score in scores)


def test_a_new_game_resets_the_board_and_the_engine(engine):
    drive(engine, "position startpos moves e2e4", "ucinewgame")
    assert engine.board.fen() == chess.STARTING_FEN


def test_changing_the_level_rebuilds_the_engine(engine):
    """A level 7 table is full of level 7 opinions; level 3 must not inherit it."""
    drive(engine, "setoption name Level value 6", "position startpos", "go movetime 150")
    finish(engine)
    first = engine.engine
    drive(engine, "setoption name Level value 3")
    assert engine.engine is None
    assert engine.current_engine() is not first
    assert engine.current_engine().level == 3


def test_quit_stops_the_search_and_ends_the_loop(engine):
    drive(engine, f"position fen {MIDDLEGAME}", "go infinite")
    time.sleep(0.2)
    assert engine.handle_line("quit") is False
    assert engine._search_thread is None


def test_the_loop_reads_a_stream_until_quit():
    instance = UciEngine(io.StringIO(), io.StringIO())
    instance.run(io.StringIO("uci\nisready\nquit\nuci\n"))
    text = instance.output.getvalue()
    assert "uciok" in text and "readyok" in text
    assert text.count("uciok") == 1  # the line after quit was never read


# --- extras ---------------------------------------------------------------


def test_perft_divides_and_totals(engine):
    text = drive(engine, "position startpos", "perft 2")
    assert "a2a3: 20" in text
    assert "nodes 400" in text


def test_bench_reports_a_verified_node_count(engine):
    text = drive(engine, "bench 2")
    assert "bench depth 2" in text and "ok yes" in text


def test_eval_and_board_display(engine):
    text = drive(engine, "position startpos", "eval", "d")
    assert "eval cp 0" in text
    assert "fen rnbqkbnr" in text


def test_a_depth_limited_go_is_actually_honoured(engine):
    """`go depth N` was accepted and silently ignored above Level 5.

    The searcher froze its depth into a config at construction, so setting the
    engine's depth did nothing — a GUI asking for a shallow search got a
    full-strength one instead.
    """
    drive(engine, "setoption name Level value 6", "position startpos", "go depth 2")
    text = finish(engine)
    depths = [
        int(line.split("depth ")[1].split()[0])
        for line in text.splitlines()
        if line.startswith("info depth")
    ]
    assert depths and max(depths) == 2


def test_a_depth_limit_belongs_to_one_search_only(engine):
    """It used to stick, capping every later search at the last depth asked for."""
    drive(engine, "setoption name Level value 6", "position startpos", "go depth 2")
    finish(engine)
    assert engine.current_engine().depth == 6

    text = drive(engine, "go movetime 400")
    text = finish(engine)
    depths = [
        int(line.split("depth ")[1].split()[0])
        for line in text.splitlines()
        if line.startswith("info depth")
    ]
    assert max(depths) > 2
