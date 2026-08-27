import chess
import pytest

from engine.levels import Level1Random, Level2Material, Level4AlphaBeta, create_engine
from tournament.match import GameRecord, play_game, play_match
from tournament.openings import OPENING_BOOK, STARTING_OPENING, book

# --- opening book ---------------------------------------------------------


def test_every_opening_line_is_legal_and_reaches_its_fen():
    assert len(OPENING_BOOK) == 8
    for opening in OPENING_BOOK:
        board = chess.Board()
        for san in opening.moves:
            board.push_san(san)
        assert board.fen() == opening.fen
        assert opening.ply >= 5


def test_openings_are_distinct():
    assert len({o.fen for o in OPENING_BOOK}) == len(OPENING_BOOK)


def test_book_slices():
    assert len(book(3)) == 3
    assert len(book()) == len(OPENING_BOOK)
    assert STARTING_OPENING.fen == chess.STARTING_FEN


# --- single game ----------------------------------------------------------


def test_play_game_produces_a_complete_record():
    record = play_game(Level2Material(seed=1), Level1Random(seed=2), max_plies=120)
    assert isinstance(record, GameRecord)
    assert record.result in ("1-0", "0-1", "1/2-1/2")
    assert record.plies > 0
    assert record.white == "L2-Material" and record.black == "L1-Random"
    assert record.reason
    assert '[White "L2-Material"]' in record.pgn
    assert record.nodes > 0


def test_move_limit_is_adjudicated_as_a_draw():
    record = play_game(Level1Random(seed=1), Level1Random(seed=2), max_plies=4)
    assert record.plies == 4
    assert record.result == "1/2-1/2"
    assert record.reason == "move limit"


def test_play_game_from_an_opening():
    opening = OPENING_BOOK[0]
    record = play_game(
        Level1Random(seed=1),
        Level1Random(seed=2),
        start_fen=opening.fen,
        max_plies=6,
        opening=opening.name,
    )
    assert record.opening == "Open Game"
    assert "[SetUp " in record.pgn


def test_on_move_hook_sees_every_move():
    seen = []
    play_game(
        Level1Random(seed=1),
        Level1Random(seed=2),
        max_plies=6,
        on_move=lambda game, engine, result: seen.append((game.ply, engine.name, result.move)),
    )
    assert [ply for ply, _, _ in seen] == [1, 2, 3, 4, 5, 6]
    assert seen[0][1] == "L1-Random"


def test_white_score_and_decisive():
    record = GameRecord("A", "B", "1-0", "checkmate", 30, "", "Start")
    assert record.white_score == 1.0 and record.decisive
    drawn = GameRecord("A", "B", "1/2-1/2", "move limit", 300, "", "Start")
    assert drawn.white_score == 0.5 and not drawn.decisive


# --- match ----------------------------------------------------------------


def test_match_alternates_colours_and_counts_correctly():
    match = play_match(Level1Random(seed=1), Level1Random(seed=2), openings=book(2), max_plies=8)
    assert match.played == 4
    assert match.wins + match.losses + match.draws == 4
    assert [g.white for g in match.games] == [
        "L1-Random",
        "L1-Random",
        "L1-Random",
        "L1-Random",
    ]
    # Colours alternate: A is White on even games, Black on odd ones.
    assert match.games[0].white == match.engine_a
    assert match.games[1].black == match.engine_a
    assert 0.0 <= match.score <= 1.0
    assert match.summary().startswith("L1-Random vs L1-Random")


def test_match_uses_each_opening_twice():
    match = play_match(Level1Random(seed=1), Level1Random(seed=2), openings=book(3), max_plies=4)
    openings = [g.opening for g in match.games]
    assert openings == [
        "Open Game",
        "Open Game",
        "Ruy Lopez",
        "Ruy Lopez",
        "Sicilian",
        "Sicilian",
    ]


def test_match_score_is_points_per_game():
    match = play_match(
        Level4AlphaBeta(seed=1), Level1Random(seed=2), openings=book(1), max_plies=60
    )
    expected = (match.wins + 0.5 * match.draws) / match.played
    assert match.score == pytest.approx(expected)


def test_empty_match_scores_zero_without_dividing_by_zero():
    match = play_match(Level1Random(seed=1), Level1Random(seed=2), openings=book(1), games=0)
    assert match.played == 0 and match.score == 0.0


@pytest.mark.slow
def test_a_stronger_engine_wins_the_match():
    match = play_match(
        create_engine(4, seed=1), create_engine(1, seed=2), openings=book(2), max_plies=120
    )
    assert match.score == 1.0, match.summary()
