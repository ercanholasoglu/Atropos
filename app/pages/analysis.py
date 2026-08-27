"""Analyse a position with every level at once."""

from __future__ import annotations

import chess
import pandas as pd
import streamlit as st

from app.components.board_view import render_svg_board
from app.state import level_label, page_header
from engine.board import ChessGame
from engine.levels import available_levels, create_engine
from engine.utils.helpers import format_eval

page_header("Analysis", "Give the same position to every level and compare.")

SAMPLES = {
    "Starting position": chess.STARTING_FEN,
    "Italian Game": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 5 4",
    "Mate in two": "r1b2k1r/ppp1bppp/8/1B1Q4/5q2/2P5/PPP2PPP/R3R1K1 w - - 1 0",
    "Poisoned pawn": "4k3/8/2p5/3p4/8/8/Q7/4K3 w - - 0 1",
    "Rook endgame": "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
}

with st.sidebar:
    st.subheader("Position")
    sample = st.selectbox("Load an example", ["(custom)"] + list(SAMPLES), key="an_sample")
    st.divider()
    st.subheader("Analysis")
    levels = st.multiselect(
        "Levels",
        available_levels(),
        default=available_levels()[-3:],
        format_func=level_label,
        key="an_levels",
    )
    think_time = st.slider("Thinking time (s)", 0.1, 10.0, 1.0, 0.1, key="an_time")

default_fen = SAMPLES.get(sample, chess.STARTING_FEN)
source = st.radio("Input", ["FEN", "PGN"], horizontal=True, key="an_source")

board: chess.Board | None = None
if source == "FEN":
    fen = st.text_input("FEN", value=default_fen, key="an_fen")
    try:
        board = chess.Board(fen)
    except ValueError as error:
        st.error(f"Not a valid FEN: {error}")
else:
    pgn_text = st.text_area("PGN", height=140, key="an_pgn", placeholder="1. e4 e5 2. Nf3 ...")
    if pgn_text.strip():
        try:
            board = ChessGame.from_pgn(pgn_text).board
        except ValueError as error:
            st.error(f"Could not read that PGN: {error}")
    else:
        st.info("Paste a game to analyse its final position.")

if board is None:
    st.stop()

board_column, info_column = st.columns([3, 2], gap="large")
with board_column:
    render_svg_board(board, orientation=board.turn)
with info_column:
    st.write(f"**{'White' if board.turn == chess.WHITE else 'Black'} to move**")
    st.write(f"Legal moves: {board.legal_moves.count()}")
    if board.is_checkmate():
        st.error("Checkmate.")
    elif board.is_stalemate():
        st.warning("Stalemate.")
    elif board.is_check():
        st.warning("Check.")
    st.code(board.fen(), language="text")

if not levels:
    st.info("Pick at least one level to analyse with.")
    st.stop()

if board.is_game_over():
    st.warning("The game is already over — there is nothing to search.")
    st.stop()

if st.button("Analyse", type="primary", use_container_width=True):
    rows = []
    progress = st.progress(0.0)
    for index, level in enumerate(sorted(levels), start=1):
        engine = create_engine(level, seed=1, time_limit=think_time)
        result = engine.analyse(board.copy())
        rows.append(
            {
                "Level": level,
                "Engine": engine.name,
                "Best move": board.san(result.move) if result.move else "—",
                "Evaluation": format_eval(result.score),
                "Depth": result.depth,
                "Nodes": result.nodes,
                "Time (ms)": round(result.time_ms),
                "Line": " ".join(board.variation_san(result.pv)) if result.pv else "",
            }
        )
        progress.progress(index / len(levels))
    st.session_state.an_rows = rows

rows = st.session_state.get("an_rows")
if rows:
    st.subheader("What each level says")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    if len({row["Best move"] for row in rows}) > 1:
        st.caption("The levels disagree — the deeper ones are usually, but not always, right.")
