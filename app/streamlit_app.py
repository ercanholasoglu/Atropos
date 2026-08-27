"""chess-bot — the Streamlit front end.

Run with ``make run`` or ``streamlit run app/streamlit_app.py``.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="chess-bot",
    page_icon="♞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Declaring the pages explicitly (rather than letting Streamlit discover the
# pages/ directory) is what puts them in playing order instead of alphabetical.
pages = [
    st.Page("pages/play.py", title="Play", icon="♟", default=True),
    st.Page("pages/watch.py", title="Watch", icon="👁"),
    st.Page("pages/tournaments.py", title="Tournament", icon="🏆"),
    st.Page("pages/leaderboard.py", title="Leaderboard", icon="📈"),
    st.Page("pages/analysis.py", title="Analysis", icon="🔍"),
]

navigation = st.navigation(pages)

with st.sidebar:
    st.markdown("### ♞ chess-bot")
    st.caption("Eight engine levels, one ladder, live Elo.")

navigation.run()
