"""Smoke tests for the Streamlit pages.

``AppTest`` runs a page the way Streamlit would and surfaces any exception it
raises, which catches the class of mistake — a bad widget key, a missing
session-state entry, a typo in a callback — that only shows up at runtime.
"""

from __future__ import annotations

from pathlib import Path

import chess
import pytest

from streamlit.testing.v1 import AppTest

# AppTest resolves relative paths against the *calling* file, so pages are
# addressed from the repository root instead.
ROOT = Path(__file__).resolve().parent.parent
PAGES = ["play", "watch", "tournaments", "leaderboard", "analysis"]


def page(name: str) -> str:
    return str(ROOT / "app" / "pages" / f"{name}.py")


def run_page(name: str, timeout: float = 60) -> AppTest:
    app = AppTest.from_file(page(name), default_timeout=timeout)
    app.run()
    return app


@pytest.mark.parametrize("name", PAGES)
def test_page_loads_without_raising(name):
    app = run_page(name)
    assert not app.exception, [str(e) for e in app.exception]


def test_play_page_starts_a_game_and_offers_the_controls():
    app = run_page("play")
    assert app.session_state.play_game.ply == 0
    assert app.session_state.play_human_white is True
    labels = [button.label for button in app.sidebar.button]
    assert "New game" in labels and "Undo" in labels and "Resign" in labels
    # 64 squares plus the sidebar controls and the PGN download.
    assert len([b for b in app.button if b.key and b.key.startswith("play_")]) == 64


def test_play_page_lets_a_human_move_and_the_engine_answer():
    app = run_page("play")
    app.button(key=f"play_{chess.E2}").click().run()
    assert app.session_state.play_selected == chess.E2

    app.button(key=f"play_{chess.E4}").click().run()
    game = app.session_state.play_game
    assert game.move_history_san()[0] == "e4"
    assert game.ply == 2, "the engine should have replied"
    assert not app.exception


def test_play_page_deselects_when_the_same_square_is_clicked_twice():
    app = run_page("play")
    app.button(key=f"play_{chess.E2}").click().run()
    app.button(key=f"play_{chess.E2}").click().run()
    assert app.session_state.play_selected is None
    assert app.session_state.play_game.ply == 0


def test_play_page_ignores_a_click_on_an_empty_square():
    app = run_page("play")
    app.button(key=f"play_{chess.E5}").click().run()
    assert app.session_state.play_selected is None
    assert app.session_state.play_game.ply == 0


def test_watch_page_steps_one_move_at_a_time():
    app = run_page("watch")
    assert app.session_state.watch_game.ply == 0
    app.button[2].click().run()  # ⏭ Step
    assert app.session_state.watch_game.ply == 1
    assert app.session_state.watch_running is False


def test_analysis_page_reports_a_best_move_for_each_level():
    app = AppTest.from_file(page("analysis"), default_timeout=120)
    app.session_state.an_levels = [1, 2, 3]
    app.session_state.an_time = 0.2
    app.run()
    app.button[0].click().run()

    rows = app.session_state.an_rows
    assert [row["Level"] for row in rows] == [1, 2, 3]
    assert all(row["Best move"] for row in rows)
    assert not app.exception


def test_tournament_page_needs_two_engines():
    app = AppTest.from_file(page("tournaments"), default_timeout=60)
    app.session_state.tour_levels = [1]
    app.run()
    assert any("at least two" in info.value for info in app.info)


def test_tournament_page_runs_a_small_round_robin(tmp_path, monkeypatch):
    import app.state as state

    monkeypatch.setattr(state, "DB_PATH", str(tmp_path / "elo.db"))
    state.get_db.clear()

    app = AppTest.from_file(page("tournaments"), default_timeout=180)
    app.session_state.tour_levels = [1, 2]
    app.session_state.tour_games = 2
    app.session_state.tour_plies = 60
    app.session_state.tour_time = 0.05
    app.run()
    app.button[0].click().run()

    result = app.session_state.tour_result
    assert result.played == 2
    assert not app.exception
    state.get_db.clear()


def test_leaderboard_page_says_so_when_there_is_nothing_to_show(tmp_path, monkeypatch):
    import app.state as state

    monkeypatch.setattr(state, "DB_PATH", str(tmp_path / "empty.db"))
    state.get_db.clear()

    app = AppTest.from_file(page("leaderboard"), default_timeout=60)
    app.run()
    assert any("No engines registered" in info.value for info in app.info)
    state.get_db.clear()


def test_play_page_offers_commentary_only_when_it_can(monkeypatch):
    """Without a key the toggle is replaced by a note, not a broken control."""
    import llm.client as client_module

    monkeypatch.setattr(client_module, "sdk_installed", lambda: False)
    app = run_page("play")
    assert not app.toggle
    assert any("ANTHROPIC_API_KEY" in caption.value for caption in app.sidebar.caption)


def test_play_page_shows_the_toggle_when_a_key_is_present(monkeypatch):
    import app.state as state
    import llm.client as client_module

    monkeypatch.setattr(client_module, "sdk_installed", lambda: True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    state.get_commentator.clear()

    app = run_page("play")
    assert [toggle.label for toggle in app.toggle] == ["Explain each move"]
    state.get_commentator.clear()
