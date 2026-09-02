import chess
import pytest

from engine.search.transposition import (
    EXACT,
    LOWER,
    UPPER,
    TranspositionTable,
    position_key,
    score_from_tt,
    score_to_tt,
)
from engine.utils.constants import MATE_SCORE

INF = float("inf")


# --- keys -----------------------------------------------------------------


def test_identical_positions_share_a_key():
    assert position_key(chess.Board()) == position_key(chess.Board())


def test_move_order_does_not_change_the_key():
    """The whole point of the table: 1.e4 e5 2.Nf3 Nc6 == 1.Nf3 Nc6 2.e4 e5."""
    first = chess.Board()
    for san in ["e4", "e5", "Nf3", "Nc6"]:
        first.push_san(san)
    second = chess.Board()
    for san in ["Nf3", "Nc6", "e4", "e5"]:
        second.push_san(san)
    assert first.fen() != second.fen()  # move counters differ
    assert position_key(first) == position_key(second)


def test_key_covers_side_to_move_castling_and_en_passant():
    base = chess.Board()
    black_to_move = chess.Board(chess.STARTING_FEN.replace(" w ", " b "))
    assert position_key(base) != position_key(black_to_move)

    no_castling = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1")
    assert position_key(base) != position_key(no_castling)

    # The en passant square only counts when the capture is actually
    # available — python-chess normalises away a square nobody can use, which
    # is exactly right for a transposition key.
    with_ep = chess.Board("rnbqkbnr/pppp1ppp/8/3Pp3/8/8/PPP1PPPP/RNBQKBNR w KQkq e6 0 3")
    without_ep = chess.Board("rnbqkbnr/pppp1ppp/8/3Pp3/8/8/PPP1PPPP/RNBQKBNR w KQkq - 0 3")
    assert chess.Move.from_uci("d5e6") in with_ep.legal_moves
    assert position_key(with_ep) != position_key(without_ep)


def test_an_unusable_en_passant_square_is_ignored():
    """No pawn can take on e6, so the two positions are genuinely identical."""
    unusable = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 3")
    plain = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3")
    assert position_key(unusable) == position_key(plain)


def test_different_positions_get_different_keys():
    keys = set()
    board = chess.Board()
    for san in ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6"]:
        board.push_san(san)
        keys.add(position_key(board))
    assert len(keys) == 8


# --- mate score adjustment ------------------------------------------------


@pytest.mark.parametrize("ply", [0, 1, 7])
@pytest.mark.parametrize("score", [0, 55, -120, MATE_SCORE - 3, -(MATE_SCORE - 5)])
def test_mate_scores_survive_a_round_trip(score, ply):
    assert score_from_tt(score_to_tt(score, ply), ply) == score


def test_only_mate_scores_are_adjusted():
    assert score_to_tt(42, 5) == 42
    assert score_to_tt(MATE_SCORE - 1, 5) == MATE_SCORE + 4


# --- table behaviour ------------------------------------------------------


def test_store_then_probe_returns_the_score_and_move():
    table = TranspositionTable(size=64)
    move = chess.Move.from_uci("e2e4")
    table.store(123, depth=4, score=55.0, flag=EXACT, move=move, ply=0)
    score, stored_move = table.probe(123, depth=4, alpha=-INF, beta=INF, ply=0)
    assert score == 55.0 and stored_move == move
    assert table.hits == 1 and table.stores == 1


def test_a_shallower_entry_still_offers_its_move():
    table = TranspositionTable(size=64)
    move = chess.Move.from_uci("e2e4")
    table.store(1, depth=2, score=55.0, flag=EXACT, move=move, ply=0)
    score, stored_move = table.probe(1, depth=5, alpha=-INF, beta=INF, ply=0)
    assert score is None  # not deep enough to trust
    assert stored_move == move  # but still the best guess for move ordering


def test_bounds_are_only_used_when_they_settle_the_window():
    table = TranspositionTable(size=64)
    table.store(1, depth=4, score=100.0, flag=LOWER, move=None, ply=0)
    # A lower bound of 100 is enough when beta is below it.
    assert table.probe(1, 4, alpha=0, beta=50, ply=0)[0] == 100.0
    assert table.probe(1, 4, alpha=0, beta=500, ply=0)[0] is None

    table.store(2, depth=4, score=-100.0, flag=UPPER, move=None, ply=0)
    assert table.probe(2, 4, alpha=-50, beta=500, ply=0)[0] == -100.0
    assert table.probe(2, 4, alpha=-500, beta=500, ply=0)[0] is None


def test_a_missing_key_is_a_miss():
    table = TranspositionTable(size=64)
    assert table.probe(999, 1, -INF, INF, 0) == (None, None)
    assert table.misses == 1


def test_slot_collisions_are_detected_not_believed():
    """Two keys can share a slot; the entry carries its own key to say so."""
    table = TranspositionTable(size=64)
    table.store(1, depth=4, score=55.0, flag=EXACT, move=None, ply=0)
    colliding = 1 + 64  # same index, different key
    assert table.probe(colliding, 4, -INF, INF, 0) == (None, None)

    table.store(colliding, depth=4, score=-30.0, flag=EXACT, move=None, ply=0)
    assert table.collisions == 1
    assert table.probe(colliding, 4, -INF, INF, 0)[0] == -30.0
    assert table.probe(1, 4, -INF, INF, 0)[0] is None  # evicted


def test_a_deeper_exact_entry_is_not_replaced_by_a_shallow_one():
    table = TranspositionTable(size=64)
    table.store(1, depth=8, score=55.0, flag=EXACT, move=None, ply=0)
    table.store(1, depth=2, score=-999.0, flag=EXACT, move=None, ply=0)
    assert table.probe(1, 8, -INF, INF, 0)[0] == 55.0


def test_clear_empties_the_table_and_the_counters():
    table = TranspositionTable(size=64)
    table.store(1, 4, 55.0, EXACT, None, 0)
    table.probe(1, 4, -INF, INF, 0)
    assert len(table) == 1 and table.occupancy > 0
    table.clear()
    assert len(table) == 0 and table.hits == 0 and table.stores == 0


def test_size_must_be_a_power_of_two():
    with pytest.raises(ValueError):
        TranspositionTable(size=100)
    TranspositionTable(size=128)  # fine


def test_lookup_does_not_move_the_counters():
    table = TranspositionTable(size=64)
    table.store(1, 4, 55.0, EXACT, None, 0)
    assert table.lookup(1) is not None
    assert table.lookup(2) is None
    assert table.hits == 0 and table.misses == 0


def test_narrow_key_returns_another_position_silently() -> None:
    """The failure a narrow key causes is a *false hit*, not a miss.

    Two keys that differ only above the truncation are the same key to the
    table, so the second position is handed the first one's score and move and
    nothing reports it. This is the behaviour `docs/ZOBRIST.md` measures.
    """
    table = TranspositionTable(size=64, key_bits=16)
    a = 0x1234
    b = (1 << 40) | 0x1234  # identical in the low 16 bits, different above
    table.store(a, depth=3, score=1.5, flag=EXACT, move=None, ply=0)
    entry = table.lookup(b)
    assert entry is not None
    assert entry.score == 1.5


def test_full_key_keeps_the_two_apart() -> None:
    table = TranspositionTable(size=64)
    a = 0x1234
    b = (1 << 40) | 0x1234
    table.store(a, depth=3, score=1.5, flag=EXACT, move=None, ply=0)
    assert table.lookup(b) is None


def test_narrow_key_converts_index_collisions_into_hits() -> None:
    """A key narrower than the index cannot detect anything.

    With 4 key bits and 64 slots the index is the key, so a slot mismatch is
    impossible: the counter that used to catch collisions reads zero, and the
    collisions it used to catch are now returned as results.
    """
    table = TranspositionTable(size=64, key_bits=4)
    for key in range(0, 256, 16):  # all congruent mod 16, so all one key
        table.store(key, depth=1, score=float(key), flag=EXACT, move=None, ply=0)
    assert table.collisions == 0
    assert table.lookup(0) is not None


def test_key_bits_must_be_a_usable_width() -> None:
    for bad in (0, 65, -1):
        with pytest.raises(ValueError):
            TranspositionTable(size=64, key_bits=bad)
    TranspositionTable(size=64, key_bits=64)  # fine
