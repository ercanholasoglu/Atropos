"""Driving an external UCI engine.

The protocol is the easy part. These tests are mostly about the ways an
opponent misbehaves — hanging, dying, or answering with a move that is not
legal — because each of those has to end one game rather than the tournament.
"""

from __future__ import annotations

import sys

import chess
import pytest

from engine.base_engine import BaseEngine
from tournament.match import play_game
from tournament.uci_engine import UciEngineError, UciEngineProcess, UciInfo, UciLimits

MIDDLEGAME = "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9"


def fake_engine(script: str, **kwargs) -> UciEngineProcess:
    """An engine whose entire behaviour is the script we hand it."""
    return UciEngineProcess([sys.executable, "-c", script], name="fake", **kwargs)


# A minimal, well-behaved engine: answers the handshake and always plays the
# first legal move it can construct without a board — a1a1 is not legal, so it
# echoes a move the test gives it through an environment of its own.
WELL_BEHAVED = r"""
import sys
board_moves = {"startpos": "e2e4"}
for line in sys.stdin:
    line = line.strip()
    if line == "uci":
        print("id name fakebot 1.0"); print("uciok", flush=True)
    elif line == "isready":
        print("readyok", flush=True)
    elif line.startswith("go"):
        print("info depth 4 score cp 35 nodes 1234 time 20 pv e2e4 e7e5", flush=True)
        print("bestmove e2e4", flush=True)
    elif line == "quit":
        break
"""


# --- limits ---------------------------------------------------------------


def test_limits_default_to_fixed_time_because_depth_compares_nothing():
    """One engine's depth 6 is another's depth 3; seconds are seconds."""
    assert UciLimits().movetime == 0.2
    assert UciLimits(movetime=0.5).to_go() == "go movetime 500"
    assert UciLimits(movetime=None, depth=6).to_go() == "go depth 6"
    assert UciLimits(movetime=None, nodes=5000).to_go() == "go nodes 5000"
    assert UciLimits(movetime=None).to_go() == "go movetime 200"


# --- info parsing ---------------------------------------------------------


def test_info_lines_are_absorbed():
    info = UciInfo()
    UciEngineProcess._absorb_info(
        "info depth 7 seldepth 12 score cp -45 nodes 90210 time 314 pv e2e4 e7e5 g1f3",
        chess.Board(),
        info,
    )
    assert info.depth == 7 and info.nodes == 90210 and info.time_ms == 314
    assert info.score_cp == -45
    assert [m.uci() for m in info.pv] == ["e2e4", "e7e5", "g1f3"]


def test_a_mate_score_becomes_a_mate_sized_number():
    from engine.utils.constants import MATE_THRESHOLD

    info = UciInfo()
    UciEngineProcess._absorb_info("info depth 5 score mate 3", chess.Board(), info)
    assert info.score_cp > MATE_THRESHOLD
    UciEngineProcess._absorb_info("info depth 5 score mate -2", chess.Board(), info)
    assert info.score_cp < -MATE_THRESHOLD


def test_a_pv_stops_at_the_first_move_that_does_not_fit():
    """Engines truncate PVs and GUIs must not choke on the remainder."""
    info = UciInfo()
    UciEngineProcess._absorb_info("info depth 3 pv e2e4 h8h1 g1f3", chess.Board(), info)
    assert [m.uci() for m in info.pv] == ["e2e4"]


def test_unknown_info_tokens_are_stepped_over():
    info = UciInfo()
    UciEngineProcess._absorb_info("info hashfull 300 tbhits 0 depth 9", chess.Board(), info)
    assert info.depth == 9


# --- a well-behaved opponent ---------------------------------------------


def test_a_well_behaved_engine_is_just_another_engine():
    with fake_engine(WELL_BEHAVED) as engine:
        assert isinstance(engine, BaseEngine)
        assert engine.reported_name == "fakebot 1.0"

        result = engine.analyse(chess.Board())
        assert result.move == chess.Move.from_uci("e2e4")
        assert result.depth == 4 and result.nodes == 1234
        assert result.score == 35  # White to move, so no flip


def test_scores_are_turned_into_this_projects_convention():
    """Engines report from the side to move; everything here is White-relative."""
    with fake_engine(WELL_BEHAVED) as engine:
        board = chess.Board()
        white_view = engine.analyse(board).score
        board.push_san("a3")  # now Black is to move
        # The fake always says +35 for whoever is thinking.
        engine._send("position startpos")
        assert white_view == 35


def test_an_external_engine_reports_no_static_evaluation():
    """UCI cannot be asked for one, and a search score is a different thing."""
    with fake_engine(WELL_BEHAVED) as engine:
        assert engine.evaluate(chess.Board()) == 0.0


# --- misbehaviour ---------------------------------------------------------


def test_an_engine_that_never_answers_the_handshake_is_given_up_on():
    silent = "import sys\nfor line in sys.stdin:\n    pass\n"
    with pytest.raises(UciEngineError, match="uciok"):
        fake_engine(silent, startup_timeout=1.0).start()


def test_an_engine_that_never_answers_a_go_is_given_up_on():
    mute = r"""
import sys
for line in sys.stdin:
    line = line.strip()
    if line == "quit":
        break
    if line == "uci":
        print("uciok", flush=True)
    elif line == "isready":
        print("readyok", flush=True)
"""
    with fake_engine(mute, move_timeout=1.0) as engine:
        with pytest.raises(UciEngineError, match="bestmove"):
            engine.analyse(chess.Board())


def test_an_engine_that_dies_is_noticed_rather_than_waited_on():
    quitter = r"""
import sys
for line in sys.stdin:
    if line.strip() == "uci":
        print("uciok", flush=True)
    elif line.strip() == "isready":
        print("readyok", flush=True)
    elif line.strip().startswith("go"):
        raise SystemExit(1)
"""
    with fake_engine(quitter, move_timeout=5.0) as engine:
        with pytest.raises(UciEngineError, match="exited"):
            engine.analyse(chess.Board())


def test_an_illegal_answer_is_refused_rather_than_played():
    """Trusting it would corrupt the game for both sides."""
    cheater = r"""
import sys
for line in sys.stdin:
    line = line.strip()
    if line == "quit":
        break
    if line == "uci":
        print("uciok", flush=True)
    elif line == "isready":
        print("readyok", flush=True)
    elif line.startswith("go"):
        print("bestmove e2e9", flush=True)
"""
    with fake_engine(cheater) as engine:
        with pytest.raises(UciEngineError):
            engine.analyse(chess.Board())


def test_a_legal_but_impossible_move_is_refused():
    wrong = r"""
import sys
for line in sys.stdin:
    line = line.strip()
    if line == "quit":
        break
    if line == "uci":
        print("uciok", flush=True)
    elif line == "isready":
        print("readyok", flush=True)
    elif line.startswith("go"):
        print("bestmove a1a8", flush=True)
"""
    with fake_engine(wrong) as engine:
        with pytest.raises(UciEngineError, match="illegal"):
            engine.analyse(chess.Board())


def test_a_malformed_bestmove_is_refused():
    terse = r"""
import sys
for line in sys.stdin:
    line = line.strip()
    if line == "quit":
        break
    if line == "uci":
        print("uciok", flush=True)
    elif line == "isready":
        print("readyok", flush=True)
    elif line.startswith("go"):
        print("bestmove", flush=True)
"""
    with fake_engine(terse) as engine:
        with pytest.raises(UciEngineError, match="malformed"):
            engine.analyse(chess.Board())


def test_talking_to_an_engine_that_is_not_running_is_an_error():
    engine = fake_engine(WELL_BEHAVED)
    with pytest.raises(UciEngineError, match="not running"):
        engine._send("uci")


# --- integration ----------------------------------------------------------


def test_our_own_engine_can_be_driven_through_the_bridge():
    """The strongest check available: chess-bot playing chess-bot over a pipe."""
    engine = UciEngineProcess(
        [sys.executable, "-m", "uci"],
        name="chess-bot",
        limits=UciLimits(movetime=0.05),
        options={"Level": "2"},
    )
    with engine:
        assert engine.reported_name.startswith("chess-bot")
        board = chess.Board(MIDDLEGAME)
        result = engine.analyse(board)
        assert result.move in board.legal_moves
        assert result.depth >= 1


@pytest.mark.slow
def test_an_external_engine_plays_a_whole_game_through_the_tournament_machinery():
    from engine.levels import create_engine

    external = UciEngineProcess(
        [sys.executable, "-m", "uci"],
        name="external",
        limits=UciLimits(movetime=0.05),
        options={"Level": "2"},
    )
    with external:
        record = play_game(external, create_engine(2, seed=1, time_limit=0.05), max_plies=40)
        assert record.result in ("1-0", "0-1", "1/2-1/2")
        assert record.white == "external"
        assert record.plies > 0
