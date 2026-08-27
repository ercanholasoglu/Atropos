"""Evaluation display: the bar, the number, and what they mean."""

from __future__ import annotations

import streamlit as st

from engine.utils.helpers import format_eval, is_mate_score


def win_probability(centipawns: float) -> float:
    """Map an evaluation onto White's expected score, 0 to 1.

    A raw centipawn score is unbounded and mostly noise past a few pawns; the
    logistic curve is the same one Elo uses, and it keeps the bar readable
    when one side is simply winning.
    """
    if is_mate_score(centipawns):
        return 1.0 if centipawns > 0 else 0.0
    return 1 / (1 + 10 ** (-centipawns / 400))


def render_eval_bar(centipawns: float, height: int = 420) -> None:
    """A vertical bar: White's share from the bottom."""
    white_share = win_probability(centipawns) * 100
    st.markdown(
        f"""
        <div style="height:{height}px;width:34px;border-radius:6px;overflow:hidden;
                    border:1px solid rgba(128,128,128,.35);display:flex;
                    flex-direction:column;justify-content:flex-end;margin:0 auto">
            <div style="height:{white_share:.1f}%;background:#f3f3f1"></div>
        </div>
        <div style="text-align:center;font-variant-numeric:tabular-nums;
                    font-size:.85rem;padding-top:.35rem">{format_eval(centipawns)}</div>
        """,
        unsafe_allow_html=True,
    )


def render_eval_metrics(result, engine_name: str) -> None:
    """The search summary under the board."""
    columns = st.columns(4)
    columns[0].metric("Evaluation", format_eval(result.score))
    columns[1].metric("Depth", result.depth)
    columns[2].metric("Nodes", f"{result.nodes:,}")
    columns[3].metric("Speed", f"{result.nps / 1000:,.0f}k n/s")
    st.caption(f"{engine_name} searched for {result.time_ms:.0f} ms")
