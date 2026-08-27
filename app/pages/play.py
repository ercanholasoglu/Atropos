"""Play against a level."""

from __future__ import annotations

import chess
import streamlit as st

from app.components.board_view import render_interactive_board
from app.components.eval_bar import render_eval_bar, render_eval_metrics
from app.components.move_history import render_move_history, render_pgn_download
from app.state import (
    commentary_toggle,
    get_commentator,
    level_selector,
    page_header,
    session_engine,
    thinking_time_selector,
)
from engine.board import ChessGame

page_header("Play", "Click a piece, then its destination.")


def new_game(human_is_white: bool) -> None:
    st.session_state.play_game = ChessGame()
    st.session_state.play_human_white = human_is_white
    st.session_state.play_selected = None
    st.session_state.play_lastmove = None
    st.session_state.play_evals = []
    st.session_state.play_result = None
    st.session_state.play_commentary_text = ""
    engine = st.session_state.get("play_engine")
    if engine is not None:
        engine.new_game()


if "play_game" not in st.session_state:
    new_game(human_is_white=True)

game: ChessGame = st.session_state.play_game

with st.sidebar:
    st.subheader("Opponent")
    level = level_selector("Engine level", key="play_level", default=3)
    think_time = thinking_time_selector("play_time", default=1.0)
    engine = session_engine("play_engine", level, seed=None, time_limit=think_time)

    st.divider()
    st.subheader("Commentary")
    want_commentary = commentary_toggle("play_commentary")

    st.divider()
    st.subheader("Game")
    play_white = (
        st.radio("You play", ["White", "Black"], horizontal=True, key="play_colour") == "White"
    )

    if st.button("New game", use_container_width=True, type="primary"):
        new_game(human_is_white=play_white)
        st.rerun()

    columns = st.columns(2)
    if columns[0].button("Undo", use_container_width=True, disabled=len(game.moves) < 2):
        game.pop()  # the engine's reply
        game.pop()  # and your move
        st.session_state.play_evals = st.session_state.play_evals[:-2]
        st.session_state.play_selected = None
        st.session_state.play_lastmove = None
        st.rerun()
    if columns[1].button("Resign", use_container_width=True, disabled=game.is_game_over()):
        game.adjudicate("0-1" if st.session_state.play_human_white else "1-0", "resignation")
        st.rerun()

human_white = st.session_state.play_human_white
human_colour = chess.WHITE if human_white else chess.BLACK
human_to_move = game.turn == human_colour and not game.is_game_over()


def engine_move() -> None:
    """Let the engine answer, recording what it thought."""
    with st.spinner(f"{engine.name} is thinking…"):
        result = engine.analyse(game.board)
    if result.move is None:
        return

    before = st.session_state.play_evals[-1] if st.session_state.play_evals else 0.0
    commentary = ""
    if want_commentary:
        # Ask before the move is played: the commentator needs the position
        # the move was chosen in, not the one it produced.
        with st.spinner("Writing commentary…"):
            commentary = get_commentator().explain_move(
                game.board, result.move, before, result.score, result
            )

    game.push(result.move)
    st.session_state.play_lastmove = result.move
    st.session_state.play_evals.append(result.score)
    st.session_state.play_last_search = result
    st.session_state.play_commentary_text = commentary


def try_move(from_square: chess.Square, to_square: chess.Square) -> bool:
    """Play a click pair if it is legal, promoting to a queen by default."""
    move = chess.Move(from_square, to_square)
    if move not in game.board.legal_moves:
        promotion = chess.Move(from_square, to_square, promotion=chess.QUEEN)
        if promotion not in game.board.legal_moves:
            return False
        move = promotion
    game.push(move)
    st.session_state.play_lastmove = move
    st.session_state.play_evals.append(engine.evaluate(game.board))
    return True


# The engine moves first when the human took Black.
if not human_to_move and not game.is_game_over() and game.ply == 0:
    engine_move()
    st.rerun()

board_column, side_column = st.columns([3, 2], gap="large")

with board_column:
    bar_column, grid_column = st.columns([1, 12], gap="small")
    with bar_column:
        latest = st.session_state.play_evals[-1] if st.session_state.play_evals else 0.0
        render_eval_bar(latest)
    with grid_column:
        clicked = render_interactive_board(
            game.board,
            selected=st.session_state.play_selected,
            orientation=human_colour,
            key_prefix="play",
            disabled=not human_to_move,
        )

    if clicked is not None and human_to_move:
        selected = st.session_state.play_selected
        piece = game.board.piece_at(clicked)
        if selected is None:
            if piece is not None and piece.color == human_colour:
                st.session_state.play_selected = clicked
        elif clicked == selected:
            st.session_state.play_selected = None
        elif try_move(selected, clicked):
            st.session_state.play_selected = None
            if not game.is_game_over():
                engine_move()
        elif piece is not None and piece.color == human_colour:
            st.session_state.play_selected = clicked
        else:
            st.session_state.play_selected = None
        st.rerun()

with side_column:
    if game.is_game_over():
        result = game.result()
        outcome = {"1-0": "White wins", "0-1": "Black wins", "1/2-1/2": "Draw"}[result]
        st.success(f"**{outcome}** — {game.outcome_reason()} ({result})")
    elif game.board.is_check():
        st.warning("Check!")

    search = st.session_state.get("play_last_search")
    if search is not None:
        render_eval_metrics(search, engine.name)

    commentary = st.session_state.get("play_commentary_text")
    if commentary:
        st.info(commentary)

    st.subheader("Moves")
    render_move_history(game)

    white_name = "You" if human_white else engine.name
    black_name = engine.name if human_white else "You"
    render_pgn_download(game, white=white_name, black=black_name, key="play_pgn")
