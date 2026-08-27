"""Watch two levels play each other."""

from __future__ import annotations

import chess
import streamlit as st

from app.components.board_view import render_svg_board
from app.components.elo_chart import eval_history_chart
from app.components.eval_bar import render_eval_bar
from app.components.move_history import render_move_history, render_pgn_download
from app.state import level_selector, page_header, session_engine
from engine.board import ChessGame

page_header("Watch", "Two engines, one board. Pick the levels and press play.")

MAX_PLIES = 300


def new_match() -> None:
    st.session_state.watch_game = ChessGame()
    st.session_state.watch_evals = []
    st.session_state.watch_lastmove = None
    st.session_state.watch_running = False
    st.session_state.watch_last_search = None
    for slot in ("watch_white_engine", "watch_black_engine"):
        engine = st.session_state.get(slot)
        if engine is not None:
            engine.new_game()


if "watch_game" not in st.session_state:
    new_match()
    st.session_state.watch_score = {"white": 0.0, "black": 0.0, "games": 0}

game: ChessGame = st.session_state.watch_game

with st.sidebar:
    st.subheader("White")
    white_level = level_selector("White engine", key="watch_white_level", default=4)
    st.subheader("Black")
    black_level = level_selector("Black engine", key="watch_black_level", default=2)

    st.divider()
    move_delay = st.select_slider(
        "Speed",
        options=[2.0, 1.0, 0.5, 0.25, 0.0],
        value=0.5,
        format_func=lambda seconds: (
            "as fast as it can" if seconds == 0 else f"{seconds:g}s per move"
        ),
        key="watch_delay",
    )
    think_time = st.slider("Thinking time (s)", 0.05, 5.0, 0.3, 0.05, key="watch_think")

white_engine = session_engine("watch_white_engine", white_level, time_limit=think_time)
black_engine = session_engine("watch_black_engine", black_level, time_limit=think_time)

controls = st.columns(4)
if controls[0].button("▶ Play", use_container_width=True, disabled=game.is_game_over()):
    st.session_state.watch_running = True
if controls[1].button("⏸ Pause", use_container_width=True):
    st.session_state.watch_running = False
if controls[2].button("⏭ Step", use_container_width=True, disabled=game.is_game_over()):
    st.session_state.watch_running = False
    st.session_state.watch_step = True
if controls[3].button("↺ New match", use_container_width=True):
    new_match()
    st.rerun()


def play_one_move() -> None:
    if game.is_game_over():
        st.session_state.watch_running = False
        return
    if game.ply >= MAX_PLIES:
        game.adjudicate("1/2-1/2", "move limit")
        st.session_state.watch_running = False
        return

    engine = white_engine if game.turn == chess.WHITE else black_engine
    result = engine.analyse(game.board)
    if result.move is None:
        st.session_state.watch_running = False
        return
    game.push(result.move)
    st.session_state.watch_lastmove = result.move
    st.session_state.watch_evals.append(result.score)
    st.session_state.watch_last_search = (engine.name, result)

    if game.is_game_over():
        st.session_state.watch_running = False
        score = st.session_state.watch_score
        score["games"] += 1
        white_score = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}[game.result()]
        score["white"] += white_score
        score["black"] += 1 - white_score


if st.session_state.pop("watch_step", False):
    play_one_move()

board_column, side_column = st.columns([3, 2], gap="large")

with board_column:
    bar_column, svg_column = st.columns([1, 10], gap="small")
    with bar_column:
        latest = st.session_state.watch_evals[-1] if st.session_state.watch_evals else 0.0
        render_eval_bar(latest)
    with svg_column:
        render_svg_board(game.board, lastmove=st.session_state.watch_lastmove)

    if st.session_state.watch_evals:
        st.plotly_chart(eval_history_chart(st.session_state.watch_evals), use_container_width=True)

with side_column:
    score = st.session_state.watch_score
    columns = st.columns(2)
    columns[0].metric("Ply", game.ply)
    columns[1].metric(
        "Match score",
        f"{score['white']:g} - {score['black']:g}",
        help=f"{score['games']} completed game(s) this session",
    )
    if game.is_game_over():
        st.success(f"{game.result()} — {game.outcome_reason()}")
    search = st.session_state.watch_last_search
    if search is not None:
        name, result = search
        st.caption(f"{name}: depth {result.depth}, {result.nodes:,} nodes, {result.time_ms:.0f} ms")
    st.subheader("Moves")
    render_move_history(game)
    render_pgn_download(game, white=white_engine.name, black=black_engine.name, key="watch_pgn")


# A fragment reruns on its own timer, so the match advances without the whole
# page (and both engines' state) being rebuilt on every move.
@st.fragment(run_every=1.0)
def autoplay() -> None:
    if st.session_state.get("watch_running"):
        play_one_move()
        st.rerun()


if st.session_state.get("watch_running"):
    autoplay()
