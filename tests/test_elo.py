import chess
import pytest

from elo.calculator import (
    DRAW,
    LOSS,
    WIN,
    EloCalculator,
    elo_diff_from_score,
    expected_score_from_elo_diff,
    performance_rating,
)
from elo.database import EloDatabase
from elo.leaderboard import (
    format_leaderboard,
    gauntlet_rating,
    head_to_head_matrix,
    rankings,
)
from elo.tracker import EloTracker
from engine.levels import create_engine
from tournament.match import GameRecord, play_match
from tournament.openings import book


@pytest.fixture
def db():
    database = EloDatabase(":memory:")
    yield database
    database.close()


@pytest.fixture
def tracker(db):
    return EloTracker(db)


def game(white="L2-Material", black="L1-Random", result="1-0", plies=40) -> GameRecord:
    return GameRecord(
        white=white,
        black=black,
        result=result,
        reason="checkmate",
        plies=plies,
        pgn='[Event "test"]',
        opening="Open Game",
    )


# --- calculator -----------------------------------------------------------


def test_equal_ratings_expect_an_even_split():
    assert EloCalculator().expected_score(1500, 1500) == 0.5


def test_four_hundred_points_is_ten_to_one():
    expected = EloCalculator().expected_score(1900, 1500)
    assert round(expected, 4) == 0.9091


def test_expected_scores_sum_to_one():
    calculator = EloCalculator()
    assert calculator.expected_score(1700, 1300) + calculator.expected_score(1300, 1700) == 1.0


def test_beating_an_equal_opponent_moves_half_the_k_factor():
    calculator = EloCalculator(k_factor=32)
    new_a, new_b = calculator.update_ratings(1500, 1500, WIN)
    assert new_a == 1516 and new_b == 1484


def test_ratings_are_zero_sum_at_a_shared_k_factor():
    calculator = EloCalculator(k_factor=32)
    for result in (WIN, DRAW, LOSS):
        new_a, new_b = calculator.update_ratings(1600, 1400, result)
        assert round((new_a + new_b) - (1600 + 1400), 9) == 0


def test_beating_a_favourite_is_worth_more_than_beating_an_underdog():
    calculator = EloCalculator()
    upset = calculator.rating_change(1400, 1800, WIN)
    expected_win = calculator.rating_change(1800, 1400, WIN)
    assert upset > expected_win > 0


def test_drawing_a_much_weaker_opponent_costs_rating():
    """The subtle part of Elo: 83% against a far weaker engine is a bad day."""
    calculator = EloCalculator()
    assert calculator.rating_change(1800, 1000, DRAW) < 0


def test_provisional_engines_move_faster():
    calculator = EloCalculator(k_factor=32, provisional_k=40, provisional_games=30)
    assert calculator.k_for(0) == 40
    assert calculator.k_for(29) == 40
    assert calculator.k_for(30) == 32
    new_engine = calculator.rating_change(1500, 1500, WIN, games_a=0)
    veteran = calculator.rating_change(1500, 1500, WIN, games_a=100)
    assert new_engine > veteran


def test_an_impossible_result_is_rejected():
    with pytest.raises(ValueError):
        EloCalculator().update_ratings(1500, 1500, 1.5)


def test_elo_diff_and_expected_score_are_inverses():
    for score in (0.25, 0.5, 0.6, 0.9):
        assert round(expected_score_from_elo_diff(elo_diff_from_score(score)), 9) == score


def test_a_clean_sweep_is_capped_rather_than_infinite():
    assert elo_diff_from_score(1.0) == 800.0
    assert elo_diff_from_score(0.0) == -800.0


def test_performance_rating_of_an_even_score_is_the_opponents_average():
    assert round(performance_rating([1200, 1500, 1800], 0.5)) == 1500


def test_performance_rating_rises_with_the_score():
    opponents = [1500] * 10
    assert (
        performance_rating(opponents, 0.25)
        < performance_rating(opponents, 0.5)
        < performance_rating(opponents, 0.75)
    )


def test_performance_rating_needs_opponents():
    with pytest.raises(ValueError):
        performance_rating([], 1.0)


# --- database -------------------------------------------------------------


def test_registering_is_idempotent_and_never_resets_a_rating(db):
    db.register_engine("L1-Random", 1, 200)
    db.record_game("L1-Random", "L2-Material", "1-0", 200, 600, 230, 570)
    db.register_engine("L1-Random", 1, 200)
    assert db.get_rating("L1-Random") == 230


def test_recording_a_game_updates_both_records(db):
    db.register_engine("L2-Material", 2, 600)
    db.register_engine("L1-Random", 1, 200)
    game_id = db.record_game("L2-Material", "L1-Random", "1-0", 600, 200, 608, 192)

    winner = db.get_engine("L2-Material")
    loser = db.get_engine("L1-Random")
    assert winner["elo"] == 608 and winner["wins"] == 1 and winner["games_played"] == 1
    assert loser["elo"] == 192 and loser["losses"] == 1
    assert db.get_game(game_id)["result"] == "1-0"


def test_a_draw_counts_for_both_sides(db):
    db.register_engine("A", 1, 1000)
    db.register_engine("B", 2, 1000)
    db.record_game("A", "B", "1/2-1/2", 1000, 1000, 1000, 1000)
    assert db.get_engine("A")["draws"] == 1
    assert db.get_engine("B")["draws"] == 1


def test_an_invalid_result_is_refused(db):
    db.register_engine("A", 1, 1000)
    db.register_engine("B", 2, 1000)
    with pytest.raises(ValueError):
        db.record_game("A", "B", "*", 1000, 1000, 1000, 1000)


def test_history_starts_at_the_initial_rating(db):
    db.register_engine("A", 1, 1000)
    history = db.get_elo_history("A")
    assert len(history) == 1
    assert history[0]["elo"] == 1000 and history[0]["game_id"] is None


def test_history_grows_one_point_per_game(db):
    db.register_engine("A", 1, 1000)
    db.register_engine("B", 2, 1000)
    for _ in range(3):
        db.record_game("A", "B", "1-0", 1000, 1000, 1010, 990)
    assert len(db.get_elo_history("A")) == 4  # registration + three games


def test_leaderboard_is_ordered_by_rating(db):
    for name, level, elo in (("A", 1, 1200), ("B", 2, 1800), ("C", 3, 1500)):
        db.register_engine(name, level, elo)
    board = db.get_leaderboard()
    assert [row["name"] for row in board] == ["B", "C", "A"]
    assert [row["rank"] for row in board] == [1, 2, 3]


def test_head_to_head_pools_both_colours(db):
    db.register_engine("A", 1, 1000)
    db.register_engine("B", 2, 1000)
    db.record_game("A", "B", "1-0", 1000, 1000, 1010, 990)  # A wins as White
    db.record_game("B", "A", "0-1", 1000, 1000, 990, 1010)  # A wins as Black
    db.record_game("A", "B", "1/2-1/2", 1000, 1000, 1000, 1000)

    record = db.head_to_head("A", "B")
    assert (record["wins"], record["losses"], record["draws"]) == (2, 0, 1)
    assert record["score"] == pytest.approx(2.5 / 3)

    mirror = db.head_to_head("B", "A")
    assert (mirror["wins"], mirror["losses"]) == (0, 2)


def test_head_to_head_of_strangers_is_empty_not_an_error(db):
    db.register_engine("A", 1, 1000)
    db.register_engine("B", 2, 1000)
    assert db.head_to_head("A", "B")["games"] == 0


def test_games_can_be_filtered_and_limited(db):
    db.register_engine("A", 1, 1000)
    db.register_engine("B", 2, 1000)
    db.register_engine("C", 3, 1000)
    db.record_game("A", "B", "1-0", 1000, 1000, 1010, 990)
    db.record_game("B", "C", "1-0", 1000, 1000, 1010, 990)
    assert len(db.get_games()) == 2
    assert len(db.get_games(engine_name="A")) == 1
    assert len(db.get_games(limit=1)) == 1


def test_reset_empties_everything(db):
    db.register_engine("A", 1, 1000)
    db.register_engine("B", 2, 1000)
    db.record_game("A", "B", "1-0", 1000, 1000, 1010, 990)
    db.reset()
    assert db.game_count() == 0 and db.list_engines() == []


def test_a_file_database_persists(tmp_path):
    path = tmp_path / "nested" / "elo.db"
    first = EloDatabase(path)
    first.register_engine("A", 1, 1234)
    assert path.exists()
    assert EloDatabase(path).get_rating("A") == 1234


# --- tracker --------------------------------------------------------------


def test_register_adopts_the_stored_rating_over_the_nominal_one(tracker, db):
    db.register_engine("L1-Random", 1, 200)
    db.record_game("L1-Random", "L2-Material", "1-0", 200, 600, 260, 540)

    engine = create_engine(1)
    assert engine.elo == 200
    tracker.register(engine)
    assert engine.elo == 260 and engine.games_played == 1


def test_recording_a_game_moves_both_ratings(tracker):
    tracker.register(create_engine(2))
    tracker.register(create_engine(1))
    update = tracker.record_game(game())

    assert update.white_delta > 0
    assert update.black_delta < 0
    assert update.white_after == tracker.rating("L2-Material")


def test_an_unregistered_engine_is_an_error(tracker):
    tracker.register(create_engine(2))
    with pytest.raises(KeyError):
        tracker.record_game(game())


def test_statistics_report_the_peak_not_just_the_present(tracker):
    tracker.register(create_engine(2))
    tracker.register(create_engine(1))
    tracker.record_game(game(result="1-0"))
    peak = tracker.rating("L2-Material")
    tracker.record_game(game(result="0-1"))
    tracker.record_game(game(result="0-1"))

    stats = tracker.statistics("L2-Material")
    assert stats["elo"] < peak == stats["peak_elo"]
    assert stats["games_played"] == 3 and stats["wins"] == 1 and stats["losses"] == 2
    assert stats["score_pct"] == pytest.approx(1 / 3)


def test_statistics_of_an_unknown_engine_raise(tracker):
    with pytest.raises(KeyError):
        tracker.statistics("nobody")


def test_rebuild_reproduces_the_ratings_from_the_game_log(tracker, db):
    """The log is the source of truth; the ratings column is a cache of it."""
    tracker.register(create_engine(2))
    tracker.register(create_engine(1))
    for result in ("1-0", "1/2-1/2", "0-1", "1-0"):
        tracker.record_game(game(result=result))

    before = {e["name"]: e["elo"] for e in db.list_engines()}
    tracker.rebuild()
    after = {e["name"]: e["elo"] for e in db.list_engines()}
    assert before == after
    assert len(db.get_elo_history("L2-Material")) == 4


def test_rebuild_picks_up_a_changed_k_factor(tracker, db):
    tracker.register(create_engine(2))
    tracker.register(create_engine(1))
    tracker.record_game(game())
    original = db.get_rating("L2-Material")

    EloTracker(db, EloCalculator(k_factor=64, provisional_k=64)).rebuild()
    assert db.get_rating("L2-Material") != original


# --- leaderboard ----------------------------------------------------------


def test_rankings_and_formatting(tracker, db):
    tracker.register(create_engine(2))
    tracker.register(create_engine(1))
    tracker.record_game(game())

    board = rankings(db)
    assert board[0]["name"] == "L2-Material"
    text = format_leaderboard(board)
    assert "L2-Material" in text and "elo" in text
    assert format_leaderboard([]) == "no engines registered"


def test_head_to_head_matrix_has_a_hole_on_the_diagonal(tracker, db):
    tracker.register(create_engine(2))
    tracker.register(create_engine(1))
    tracker.record_game(game())

    matrix = head_to_head_matrix(db)
    assert matrix["L2-Material"]["L2-Material"] is None
    assert matrix["L2-Material"]["L1-Random"] == 1.0
    assert matrix["L1-Random"]["L2-Material"] == 0.0


def test_gauntlet_rating_needs_games(tracker, db):
    tracker.register(create_engine(2))
    assert gauntlet_rating(db, "L2-Material") is None


def test_gauntlet_rating_reflects_the_whole_record(tracker, db):
    tracker.register(create_engine(2))
    tracker.register(create_engine(1))
    for _ in range(6):
        tracker.record_game(game(result="1-0"))
    rating = gauntlet_rating(db, "L2-Material")
    assert rating is not None and rating > db.get_rating("L1-Random")


# --- end to end -----------------------------------------------------------


def test_a_played_match_flows_into_the_ratings(tracker, db):
    stronger = create_engine(2, seed=1)
    weaker = create_engine(1, seed=2)
    tracker.register_all([stronger, weaker])

    match = play_match(stronger, weaker, openings=book(2), max_plies=100)
    updates = tracker.record_match(match, event="smoke")

    assert len(updates) == match.played == db.game_count()
    assert db.get_games(limit=1)[0]["event"] == "smoke"
    assert db.get_rating("L2-Material") > db.get_rating("L1-Random")
    assert sum(row["games_played"] for row in db.get_leaderboard()) == 2 * match.played
