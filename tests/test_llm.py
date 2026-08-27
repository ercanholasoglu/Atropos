"""The optional language-model layer, and Level 8's use of it.

No test here touches the network. The point of the layer is that it is
optional, so most of these assert what happens when it is absent, and the
rest drive a stand-in client.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess
import pytest

from engine.levels import Level8Neural, available_levels, create_engine
from llm.analysis import analyse_position
from llm.client import DEFAULT_MODEL, ClaudeClient, LLMConfig, LLMUnavailable, available
from llm.commentary import ChessCommentator, describe_line, describe_position

SHARP = "r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9"
QUIET = "8/8/4k3/8/8/4K3/8/4R3 w - - 0 1"
CHECKMATE = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"


# --- a stand-in for the SDK ----------------------------------------------


@dataclass
class FakeBlock:
    text: str
    type: str = "text"


@dataclass
class FakeMessage:
    content: list
    stop_reason: str = "end_turn"
    stop_details: object | None = None


class FakeMessages:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kwargs):
        self.owner.calls.append(kwargs)
        return self.owner.reply


class FakeAnthropic:
    """Records what it was asked and returns whatever it was told to."""

    def __init__(self, reply: FakeMessage | None = None):
        self.calls: list[dict] = []
        self.reply = reply or FakeMessage([FakeBlock("Because the knight is loose on c6.")])
        self.messages = FakeMessages(self)
        self.beta = type("Beta", (), {"messages": FakeMessages(self)})()


def wired_client(reply: FakeMessage | None = None) -> tuple[ClaudeClient, FakeAnthropic]:
    client = ClaudeClient(api_key_=None)
    fake = FakeAnthropic(reply)
    client._client = fake
    return client, fake


# --- client ---------------------------------------------------------------


def test_the_default_model_is_current_and_temperature_is_gone():
    """``temperature`` was removed from this model generation; sending it 400s."""
    assert DEFAULT_MODEL == "claude-opus-5"
    assert "temperature" not in LLMConfig.__dataclass_fields__


def test_no_key_means_no_client_rather_than_a_crash():
    client = ClaudeClient(api_key_=None)
    assert not client.available
    with pytest.raises(LLMUnavailable):
        client.complete("hello")


def test_availability_needs_both_a_key_and_the_sdk(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr("llm.client.sdk_installed", lambda: False)
    assert not available()
    monkeypatch.setattr("llm.client.sdk_installed", lambda: True)
    assert available()


def test_a_completion_sends_the_current_request_shape():
    client, fake = wired_client()
    answer = client.complete("Explain Nxc6", system="You are a coach.")

    assert answer == "Because the knight is loose on c6."
    request = fake.calls[0]
    assert request["model"] == "claude-opus-5"
    assert request["system"] == "You are a coach."
    assert request["output_config"] == {"effort": "low"}
    assert request["messages"] == [{"role": "user", "content": "Explain Nxc6"}]
    assert "temperature" not in request
    # Refusal fallback is on by default and rides the beta endpoint.
    assert request["fallbacks"] == "default"
    assert request["betas"] == ["server-side-fallback-2026-07-01"]


def test_the_fallback_can_be_turned_off():
    client, fake = wired_client()
    client.config = LLMConfig(refusal_fallback=False)
    client.complete("hi")
    assert "fallbacks" not in fake.calls[0]


def test_a_refusal_is_a_two_hundred_not_an_exception():
    """The API returns HTTP 200 on a decline — stop_reason has to be checked."""
    refusal = FakeMessage(
        content=[], stop_reason="refusal", stop_details=type("D", (), {"category": "cyber"})()
    )
    client, _ = wired_client(refusal)
    with pytest.raises(LLMUnavailable, match="cyber"):
        client.complete("hi")


def test_only_text_blocks_are_read():
    reply = FakeMessage([FakeBlock("", type="thinking"), FakeBlock("The real answer.")])
    client, _ = wired_client(reply)
    assert client.complete("hi") == "The real answer."


# --- prompt building ------------------------------------------------------


def test_position_description_carries_the_facts():
    text = describe_position(chess.Board(SHARP))
    assert "FEN:" in text and "To move: White" in text
    assert "opening" in text and "52" in text


def test_a_position_in_check_says_so():
    board = chess.Board("4r3/8/8/8/8/8/8/4K3 w - - 0 1")  # rook checks down the e-file
    assert board.is_check()
    assert "in check" in describe_position(board)


def test_a_line_is_rendered_in_readable_notation():
    board = chess.Board()
    moves = [chess.Move.from_uci(uci) for uci in ("e2e4", "e7e5", "g1f3")]
    assert describe_line(board, moves) == "1. e4 e5 2. Nf3"
    assert describe_line(board, []) == ""


# --- commentary -----------------------------------------------------------


def test_commentary_is_empty_rather_than_absent_without_a_key():
    """Callers render it unconditionally, so it has to be a string."""
    commentator = ChessCommentator()
    board = chess.Board(SHARP)
    assert commentator.explain_move(board, chess.Move.from_uci("d4c6"), 0, 20) == ""
    assert commentator.analyze_position(board) == ""
    assert commentator.suggest_plan(board) == ""
    assert not commentator.available


def test_an_illegal_move_is_rejected_before_any_call():
    commentator = ChessCommentator()
    with pytest.raises(ValueError):
        commentator.explain_move(chess.Board(), chess.Move.from_uci("e2e5"), 0, 0)


def test_the_prompt_hands_the_model_the_engines_verdict():
    client, fake = wired_client()
    commentator = ChessCommentator(client=client)
    board = chess.Board(SHARP)
    engine = create_engine(4, seed=1, time_limit=0.3)
    search = engine.analyse(board.copy())

    commentator.explain_move(board, chess.Move.from_uci("d4c6"), 10.0, 95.0, search)
    prompt = fake.calls[0]["messages"][0]["content"]

    assert "Nxc6" in prompt
    assert "Evaluation before: +0.10" in prompt
    assert "Change: +0.85 pawns" in prompt
    assert "Engine's main line:" in prompt
    assert "capture" in prompt


def test_commentary_is_cached_per_position():
    client, fake = wired_client()
    commentator = ChessCommentator(client=client)
    board = chess.Board(SHARP)
    move = chess.Move.from_uci("d4c6")

    first = commentator.explain_move(board, move, 0, 20)
    second = commentator.explain_move(board, move, 0, 20)
    assert first == second
    assert len(fake.calls) == 1


def test_mate_and_check_are_flagged_to_the_model():
    client, fake = wired_client()
    commentator = ChessCommentator(client=client)
    board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/4Q1K1 w - - 0 1")
    commentator.explain_move(board, chess.Move.from_uci("e1e8"), 0, 99999)
    assert "checkmate" in fake.calls[0]["messages"][0]["content"]


# --- analysis -------------------------------------------------------------


def test_analysis_reports_the_engines_findings():
    analysis = analyse_position(chess.Board(SHARP), level=4, time_limit=0.3)
    assert analysis.best_move_san
    assert analysis.depth >= 1 and analysis.nodes > 0
    assert analysis.line_san
    assert not analysis.has_commentary  # no key configured


def test_analysis_attaches_commentary_when_it_can():
    client, fake = wired_client()
    analysis = analyse_position(
        chess.Board(SHARP), level=4, time_limit=0.3, commentator=ChessCommentator(client=client)
    )
    assert analysis.has_commentary
    assert analysis.explanation and analysis.plan
    assert len(fake.calls) == 2  # one for the description, one for the plan


def test_a_finished_game_has_nothing_to_analyse():
    with pytest.raises(ValueError):
        analyse_position(chess.Board(CHECKMATE))


# --- Level 8 --------------------------------------------------------------


def test_level_eight_is_registered():
    assert available_levels() == [1, 2, 3, 4, 5, 6, 7, 8]
    assert isinstance(create_engine(8), Level8Neural)


def test_a_sharp_position_earns_more_clock_than_a_quiet_one():
    """The whole point of the level: effort follows difficulty."""
    engine = Level8Neural(seed=1, time_limit=1.0)
    quiet = engine.time_for(chess.Board(QUIET))
    quiet_score = engine.last_complexity.score
    sharp = engine.time_for(chess.Board(SHARP))

    assert quiet < 1.0 < sharp
    assert quiet_score < engine.last_complexity.score
    assert 0.5 <= quiet <= 2.0 and 0.5 <= sharp <= 2.0


def test_adaptive_timing_can_be_switched_off():
    engine = Level8Neural(seed=1, time_limit=1.0, adaptive_time=False)
    assert engine.time_for(chess.Board(SHARP)) == 1.0
    assert Level8Neural(seed=1, time_limit=None).time_for(chess.Board(SHARP)) is None


def test_a_custom_evaluator_replaces_the_classical_one():
    engine = Level8Neural(seed=1, evaluator=lambda board: 4242)
    assert engine.static_eval(chess.Board()) == 4242


def test_level_eight_plays_a_legal_move():
    board = chess.Board(SHARP)
    result = Level8Neural(seed=1, time_limit=0.3).analyse(board)
    assert result.move in board.legal_moves


class AlwaysAdvises:
    def __init__(self, move: chess.Move | None):
        self.move = move
        self.calls = 0

    def choose(self, board, result):
        self.calls += 1
        return self.move


def test_the_advisor_is_left_alone_when_the_search_is_sure():
    """A clear best move needs no second opinion, however sharp the position."""
    board = chess.Board("4k3/8/8/3q4/8/8/8/4K2R w - - 0 1")  # Rxh8?? no — queen is free
    advisor = AlwaysAdvises(None)
    engine = Level8Neural(seed=1, time_limit=0.3, advisor=advisor)
    engine.analyse(board)
    assert engine.advisor_calls == 0


def test_an_advisors_illegal_suggestion_is_ignored():
    board = chess.Board(SHARP)
    engine = Level8Neural(
        seed=1, time_limit=0.3, advisor=AlwaysAdvises(chess.Move.from_uci("a1a8"))
    )
    result = engine.analyse(board)
    assert result.move in board.legal_moves
    assert engine.advisor_calls == 0
