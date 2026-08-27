"""Session state, cached resources and shared widgets.

Streamlit reruns the whole script on every interaction, so anything that must
survive a click lives in ``st.session_state``, and anything expensive to build
is cached. Engines belong in session state rather than a global cache: they
carry a transposition table and killer moves from one move to the next, and
two browser tabs must not share them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Streamlit runs the entry script directly, so the repository root is not on
# the path unless it is put there.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from elo.database import DEFAULT_DB_PATH, EloDatabase  # noqa: E402
from elo.tracker import EloTracker  # noqa: E402
from engine.base_engine import BaseEngine  # noqa: E402
from engine.levels import available_levels, create_engine  # noqa: E402
from engine.utils.constants import INITIAL_ELO, LEVEL_NAMES  # noqa: E402

DB_PATH = str(ROOT / DEFAULT_DB_PATH)

LEVEL_BLURBS = {
    1: "Random legal moves.",
    2: "Counts material one move ahead.",
    3: "Minimax to depth 3 — sees your reply.",
    4: "Alpha-beta to depth 4 with iterative deepening.",
    5: "Piece-square tables and tapered evaluation.",
    6: "Quiescence, transposition table, killer moves.",
    7: "Null-move pruning, late move reductions, aspiration windows.",
    8: "Adaptive time management, optional LLM second opinion.",
}


def level_label(level: int) -> str:
    return f"Level {level} — {LEVEL_NAMES[level]} (~{INITIAL_ELO[level]} Elo)"


@st.cache_resource
def get_db() -> EloDatabase:
    """One database handle per server process."""
    return EloDatabase(DB_PATH)


def get_tracker() -> EloTracker:
    return EloTracker(get_db())


def session_engine(slot: str, level: int, time_limit: float | None = None, **kwargs) -> BaseEngine:
    """An engine kept in session state, rebuilt when the level changes.

    Rebuilding on a level change matters: a Level 7 searcher holds a table
    full of positions scored by Level 7's evaluation, which would be wrong to
    hand to another level. The clock is not part of that signature — moving
    the time slider should not throw away what the engine has learned this
    game, so it is applied to the existing engine instead.
    """
    signature = (level, tuple(sorted(kwargs.items())))
    if st.session_state.get(f"{slot}_signature") != signature:
        st.session_state[slot] = create_engine(level, **kwargs)
        st.session_state[f"{slot}_signature"] = signature
    engine = st.session_state[slot]
    if time_limit is not None:
        engine.time_limit = time_limit
    return engine


def level_selector(label: str, key: str, default: int = 3) -> int:
    """A level dropdown with its description underneath."""
    levels = available_levels()
    if default not in levels:
        default = levels[0]
    level = st.selectbox(
        label,
        levels,
        index=levels.index(default),
        format_func=level_label,
        key=key,
    )
    st.caption(LEVEL_BLURBS.get(level, ""))
    return int(level)


def thinking_time_selector(key: str, default: float = 1.0) -> float:
    return st.slider(
        "Thinking time (seconds per move)",
        min_value=0.1,
        max_value=10.0,
        value=default,
        step=0.1,
        key=key,
        help="Levels 6 and 7 search as deep as this budget allows.",
    )


@st.cache_resource
def get_commentator():
    """The commentary client, shared across reruns.

    Cached because it holds a per-position cache of its own: without that a
    Streamlit rerun would pay for the same sentence twice.
    """
    from llm.commentary import ChessCommentator

    return ChessCommentator()


def commentary_toggle(key: str) -> bool:
    """Offer LLM commentary, and say plainly when it is not available."""
    from llm.client import available as llm_available

    if not llm_available():
        st.caption(
            "Commentary needs `ANTHROPIC_API_KEY` and the `anthropic` package. "
            "Everything else works without it."
        )
        return False
    return st.toggle("Explain each move", value=False, key=key)


def page_header(title: str, subtitle: str) -> None:
    st.title(title)
    st.caption(subtitle)
