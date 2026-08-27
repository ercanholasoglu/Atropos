import chess
import pytest

from engine.board import ChessGame


def test_push_and_history():
    game = ChessGame()
    assert game.push_san("e4") == "e4"
    game.push_san("e5")
    game.push_san("Nf3")
    assert game.ply == 3
    assert game.move_history_san() == ["e4", "e5", "Nf3"]
    assert game.turn == chess.BLACK


def test_illegal_move_rejected():
    game = ChessGame()
    with pytest.raises(ValueError):
        game.push(chess.Move.from_uci("e2e5"))


def test_pop_and_reset():
    game = ChessGame()
    game.push_san("e4")
    game.pop()
    assert game.ply == 0
    assert game.fen == chess.STARTING_FEN
    game.push_san("d4")
    game.reset()
    assert game.ply == 0


def test_game_over_detection():
    game = ChessGame()
    for san in ["f3", "e5", "g4", "Qh4#"]:
        game.push_san(san)
    assert game.is_game_over()
    assert game.result() == "0-1"
    assert game.outcome_reason() == "checkmate"


def test_adjudication_overrides_result():
    game = ChessGame()
    game.push_san("e4")
    game.adjudicate("1-0", "black resigned")
    assert game.is_game_over()
    assert game.result() == "1-0"
    assert game.outcome_reason() == "black resigned"
    with pytest.raises(ValueError):
        game.adjudicate("*", "nonsense")


def test_material_balance_tracks_captures():
    game = ChessGame("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
    assert game.material_balance() == 0
    game.push_san("exd5")
    assert game.material_balance() == 100


def test_pgn_roundtrip():
    game = ChessGame()
    for san in ["e4", "e5", "Nf3", "Nc6"]:
        game.push_san(san)
    pgn = game.to_pgn(white="L1-Random", black="L2-Material", round_="1")
    assert '[White "L1-Random"]' in pgn
    assert "1. e4 e5 2. Nf3 Nc6" in pgn

    replayed = ChessGame.from_pgn(pgn)
    assert replayed.move_history_san() == game.move_history_san()
    assert replayed.fen == game.fen


def test_pgn_from_custom_start_position():
    fen = "6k1/5ppp/8/8/8/8/5PPP/4Q1K1 w - - 0 1"
    game = ChessGame(fen)
    game.push_san("Qe8#")
    pgn = game.to_pgn()
    assert "[SetUp " in pgn and fen in pgn
    assert ChessGame.from_pgn(pgn).fen == game.fen
