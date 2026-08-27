"""Run a tournament and write the results to the rating database.

Named ``tournaments.py``, plural, on purpose: Streamlit puts the running
script's own directory at the front of ``sys.path``, so a page called
``tournament.py`` would shadow the top-level ``tournament`` package and every
``from tournament.match import ...`` in the project would resolve to this file.
"""

from __future__ import annotations

import io
import zipfile

import streamlit as st

from app.state import get_tracker, level_label, page_header
from engine.levels import available_levels, create_engine
from tournament.gauntlet import GauntletTournament
from tournament.match import GameRecord
from tournament.openings import book
from tournament.round_robin import RoundRobinTournament
from tournament.swiss import SwissTournament

page_header("Tournament", "Round-robin, Swiss or gauntlet — results feed the ladder.")

FORMATS = {
    "Round-robin": "Everybody plays everybody. Fairest, and the most games.",
    "Swiss": "Pairs engines on similar scores. A ranking in far fewer games.",
    "Gauntlet": "One engine against a field. Every game is signal.",
}

with st.sidebar:
    st.subheader("Format")
    format_name = st.radio("Format", list(FORMATS), key="tour_format", label_visibility="collapsed")
    st.caption(FORMATS[format_name])

    st.divider()
    st.subheader("Field")
    levels = st.multiselect(
        "Engines",
        available_levels(),
        default=available_levels()[:4],
        format_func=level_label,
        key="tour_levels",
    )

    test_level = None
    if format_name == "Gauntlet":
        test_level = st.selectbox(
            "Engine under test", available_levels(), format_func=level_label, key="tour_test"
        )

    st.divider()
    st.subheader("Settings")
    games = st.slider("Games per pairing", 1, 10, 2, key="tour_games")
    rounds = st.slider(
        "Rounds (Swiss)", 1, 11, 5, key="tour_rounds", disabled=format_name != "Swiss"
    )
    think_time = st.slider("Thinking time (s)", 0.05, 3.0, 0.3, 0.05, key="tour_time")
    max_plies = st.slider("Move limit (plies)", 40, 400, 200, 20, key="tour_plies")
    rate = st.checkbox("Record results in the Elo database", value=True, key="tour_rate")


def build_tournament(progress_hook):
    engines = [
        create_engine(level, seed=level * 7, time_limit=think_time) for level in sorted(levels)
    ]
    common = dict(
        openings=book(),
        max_plies=max_plies,
        tracker=get_tracker() if rate else None,
        on_game=progress_hook,
    )
    if format_name == "Gauntlet":
        opponents = [e for e in engines if e.level != test_level]
        if not opponents:
            raise ValueError("the field cannot be only the engine under test")
        test_engine = create_engine(test_level, seed=99, time_limit=think_time)
        return GauntletTournament(test_engine, opponents, games_per_opponent=games, **common)
    if format_name == "Swiss":
        return SwissTournament(engines, rounds=rounds, **common)
    return RoundRobinTournament(engines, games_per_pair=games, **common)


if len(levels) < 2:
    st.info("Pick at least two engines.")
    st.stop()

if st.button("Run tournament", type="primary", use_container_width=True):
    progress = st.progress(0.0, text="Starting…")
    log = st.empty()
    lines: list[str] = []

    def on_game(done: int, total: int, record: GameRecord) -> None:
        progress.progress(done / total, text=f"Game {done} of {total}")
        lines.append(
            f"{record.white} – {record.black}  {record.result}  "
            f"({record.plies} plies, {record.reason})"
        )
        log.code("\n".join(lines[-12:]), language="text")

    try:
        tournament = build_tournament(on_game)
    except ValueError as error:
        st.error(str(error))
        st.stop()

    with st.spinner(f"Playing {tournament.total_games} games…"):
        result = tournament.run()

    progress.progress(1.0, text="Done")
    st.session_state.tour_result = result
    st.session_state.tour_estimate = (
        tournament.estimate_rating(result) if isinstance(tournament, GauntletTournament) else None
    )
    st.session_state.tour_test_name = (
        tournament.test_engine.name if isinstance(tournament, GauntletTournament) else None
    )

result = st.session_state.get("tour_result")
if result is None:
    st.stop()

st.subheader(f"{result.format} — {result.played} games")
st.code(result.table(), language="text")

estimate = st.session_state.get("tour_estimate")
if estimate is not None:
    st.metric(
        f"Performance rating for {st.session_state.tour_test_name}",
        f"{estimate:.0f}",
        help="The rating this whole score implies against this field.",
    )

with st.expander("Games"):
    for index, record in enumerate(result.games, start=1):
        st.write(
            f"**{index}.** {record.white} – {record.black} · `{record.result}` · "
            f"{record.opening} · {record.plies} plies · {record.reason}"
        )

archive = io.BytesIO()
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    bundle.writestr("tournament.pgn", "\n\n".join(record.pgn for record in result.games))
st.download_button(
    "Download all games (PGN)",
    data=archive.getvalue(),
    file_name=f"{result.format}.zip",
    mime="application/zip",
    use_container_width=True,
)
