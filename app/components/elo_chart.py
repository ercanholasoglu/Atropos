"""Rating charts."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from elo.database import EloDatabase


def elo_history_chart(db: EloDatabase, names: list[str]) -> go.Figure:
    """One line per engine, x-axis in games played rather than wall-clock.

    Games are what move a rating; two engines that played on different days
    should still be comparable along the same axis.
    """
    figure = go.Figure()
    for name in names:
        history = db.get_elo_history(name)
        if not history:
            continue
        figure.add_trace(
            go.Scatter(
                x=list(range(len(history))),
                y=[entry["elo"] for entry in history],
                mode="lines",
                name=name,
                hovertemplate=f"{name}<br>game %{{x}}<br>%{{y:.0f}} Elo<extra></extra>",
            )
        )
    figure.update_layout(
        xaxis_title="games played",
        yaxis_title="Elo",
        height=420,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return figure


def render_elo_history(db: EloDatabase, names: list[str]) -> None:
    if not names:
        st.info("No engines have played yet.")
        return
    st.plotly_chart(elo_history_chart(db, names), use_container_width=True)


def render_leaderboard_table(rows: list[dict]) -> None:
    if not rows:
        st.info("No games recorded yet. Run a tournament to populate the ladder.")
        return

    frame = pd.DataFrame(
        [
            {
                "#": row["rank"],
                "Engine": row["name"],
                "Level": row["level"],
                "Elo": round(row["elo"], 1),
                "Δ": round(row["elo_change"], 1),
                "Games": row["games_played"],
                "W": row["wins"],
                "D": row["draws"],
                "L": row["losses"],
                "Score": row["score_pct"],
            }
            for row in rows
        ]
    )
    st.dataframe(
        frame,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score", format="%.1f%%", min_value=0, max_value=1
            )
        },
    )


def eval_history_chart(scores: list[float]) -> go.Figure:
    """The evaluation over a game, clipped to a readable range."""
    clipped = [max(-1000, min(1000, score)) / 100 for score in scores]
    figure = go.Figure(
        go.Scatter(x=list(range(1, len(clipped) + 1)), y=clipped, mode="lines", fill="tozeroy")
    )
    figure.update_layout(
        xaxis_title="ply",
        yaxis_title="evaluation (pawns)",
        height=240,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(range=[-10, 10], zeroline=True),
    )
    return figure
