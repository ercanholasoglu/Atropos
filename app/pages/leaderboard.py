"""Ratings, history and head-to-head records."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.elo_chart import render_elo_history, render_leaderboard_table
from app.state import get_db, get_tracker, page_header
from elo.leaderboard import gauntlet_rating, head_to_head_matrix

page_header("Leaderboard", "Ratings earned in play, not the numbers on the tin.")

db = get_db()
board = db.get_leaderboard()

if not board:
    st.info("No engines registered yet. Run a tournament to fill the ladder.")
    st.stop()

names = [row["name"] for row in board]

render_leaderboard_table(board)

st.subheader("Rating history")
selected = st.multiselect("Engines", names, default=names, key="lb_engines")
render_elo_history(db, selected)

st.subheader("Head to head")
matrix = head_to_head_matrix(db, names)
frame = pd.DataFrame([[matrix[a][b] for b in names] for a in names], index=names, columns=names)
st.dataframe(
    frame.style.format(lambda value: "—" if pd.isna(value) else f"{value:.0%}"),
    use_container_width=True,
)
st.caption("Row's score against column, both colours pooled.")

st.subheader("Engine detail")
engine_name = st.selectbox("Engine", names, key="lb_detail")
stats = get_tracker().statistics(engine_name)
estimate = gauntlet_rating(db, engine_name)

columns = st.columns(4)
columns[0].metric("Elo", f"{stats['elo']:.0f}", f"{stats['elo_change']:+.0f}")
columns[1].metric("Peak", f"{stats['peak_elo']:.0f}")
columns[2].metric("Games", stats["games_played"])
columns[3].metric(
    "Performance",
    f"{estimate:.0f}" if estimate is not None else "—",
    help="The rating this engine's whole record implies, independent of the order games were played.",
)
st.caption(
    f"{stats['wins']} wins · {stats['draws']} draws · {stats['losses']} losses "
    f"({stats['score_pct']:.1%})"
)

recent = db.get_games(engine_name=engine_name, limit=15)
if recent:
    st.subheader("Recent games")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "White": game["white_engine"],
                    "Black": game["black_engine"],
                    "Result": game["result"],
                    "Plies": game["moves_count"],
                    "Opening": game["opening"],
                    "Ended": game["termination"],
                }
                for game in recent
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )

with st.expander("Danger zone"):
    st.caption("Clears every engine, game and rating point.")
    if st.button("Reset the database", type="secondary"):
        db.reset()
        st.rerun()
