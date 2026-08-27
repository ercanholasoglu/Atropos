import chess
import pytest

from engine.evaluation.pst import (
    EG_TABLES,
    MG_TABLES,
    RAW_EG,
    RAW_MG,
    pst_scores,
    pst_value,
)
from engine.evaluation.tapered import taper, tapered_pst
from engine.utils.constants import PIECE_VALUES, TOTAL_PHASE
from engine.utils.helpers import game_phase

PIECES = [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]


# --- table shape ----------------------------------------------------------


@pytest.mark.parametrize("piece_type", PIECES)
def test_every_table_covers_the_whole_board(piece_type):
    assert len(RAW_MG[piece_type]) == 64
    assert len(RAW_EG[piece_type]) == 64
    for color in (chess.WHITE, chess.BLACK):
        assert len(MG_TABLES[color][piece_type]) == 64
        assert len(EG_TABLES[color][piece_type]) == 64


@pytest.mark.parametrize("piece_type", PIECES)
def test_tables_are_left_right_symmetric(piece_type):
    """No table should prefer the queenside to the kingside."""
    for table in (RAW_MG[piece_type], RAW_EG[piece_type]):
        for rank in range(8):
            row = table[rank * 8 : rank * 8 + 8]
            assert row == row[::-1], f"rank {rank} of {piece_type} is lopsided"


@pytest.mark.parametrize("piece_type", PIECES)
def test_folded_tables_carry_the_piece_value(piece_type):
    """A folded entry is material + placement, so one lookup covers both."""
    expected_value = 0 if piece_type == chess.KING else PIECE_VALUES[piece_type]
    for square in (chess.A1, chess.E4, chess.H8):
        placement = pst_value(chess.Piece(piece_type, chess.WHITE), square)
        assert MG_TABLES[chess.WHITE][piece_type][square] == expected_value + placement


# --- orientation ----------------------------------------------------------


def test_tables_are_read_from_whites_side():
    """Index 0 of a raw table is a8, not a1."""
    # The pawn table's second row (index 8-15) is the seventh rank bonus.
    assert RAW_MG[chess.PAWN][8] == 50
    assert pst_value(chess.Piece(chess.PAWN, chess.WHITE), chess.A7) == 50


@pytest.mark.parametrize(
    "white_square,black_square",
    [(chess.E2, chess.E7), (chess.A1, chess.A8), (chess.C4, chess.C5)],
)
@pytest.mark.parametrize("piece_type", PIECES)
def test_colours_see_mirrored_squares(piece_type, white_square, black_square):
    white = pst_value(chess.Piece(piece_type, chess.WHITE), white_square)
    black = pst_value(chess.Piece(piece_type, chess.BLACK), black_square)
    assert white == black


def test_knights_prefer_the_centre_to_the_rim():
    centre = pst_value(chess.Piece(chess.KNIGHT, chess.WHITE), chess.E4)
    rim = pst_value(chess.Piece(chess.KNIGHT, chess.WHITE), chess.A1)
    assert centre > 0 > rim


def test_the_king_wants_shelter_early_and_the_centre_late():
    king = chess.Piece(chess.KING, chess.WHITE)
    assert pst_value(king, chess.G1) > pst_value(king, chess.E4)
    assert pst_value(king, chess.E4, endgame=True) > pst_value(king, chess.G1, endgame=True)


# --- pst_scores -----------------------------------------------------------


def test_start_position_scores_zero_in_both_phases():
    assert pst_scores(chess.Board()) == (0, 0)


def test_a_central_pawn_push_is_worth_something():
    board = chess.Board()
    board.push_san("e4")
    middlegame, endgame = pst_scores(board)
    assert middlegame == 40  # e2 is -20, e4 is +20
    assert endgame == 10


def test_pst_scores_include_material():
    """Take Black's queen off the start position: the swing is value + placement."""
    board = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    middlegame, _ = pst_scores(board)
    queen_on_d8 = pst_value(chess.Piece(chess.QUEEN, chess.BLACK), chess.D8)
    assert middlegame == PIECE_VALUES[chess.QUEEN] + queen_on_d8


def test_pst_scores_flip_sign_with_colour():
    white = chess.Board("4k3/8/8/8/4N3/8/8/4K3 w - - 0 1")
    black = chess.Board("4k3/8/8/4n3/8/8/8/4K3 w - - 0 1")
    assert pst_scores(white)[0] == -pst_scores(black)[0]


# --- tapering -------------------------------------------------------------


def test_taper_endpoints_and_midpoint():
    assert taper(100, 200, TOTAL_PHASE) == 100
    assert taper(100, 200, 0) == 200
    assert taper(100, 200, TOTAL_PHASE // 2) == 150


def test_taper_clamps_impossible_phases():
    assert taper(10, 90, TOTAL_PHASE * 3) == 10
    assert taper(10, 90, -5) == 90


def test_game_phase_counts_down_as_pieces_come_off():
    assert game_phase(chess.Board()) == TOTAL_PHASE
    queenless = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1")
    assert game_phase(queenless) == TOTAL_PHASE - 8
    assert game_phase(chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")) == 0


def test_game_phase_is_clamped_when_pawns_promote():
    """Three queens a side would otherwise push the phase past the opening."""
    crowded = chess.Board("qqqqkqqq/8/8/8/8/8/8/QQQQKQQQ w - - 0 1")
    assert game_phase(crowded) == TOTAL_PHASE


def test_tapered_eval_follows_the_phase():
    """The same king placement is judged differently once the pieces are gone."""

    def with_king_on(fen: str, square: str) -> int:
        """Drop White's king on an empty square, so only its placement varies."""
        board = chess.Board(fen)
        target = chess.parse_square(square)
        assert board.piece_at(target) is None
        board.set_piece_at(target, chess.Piece(chess.KING, chess.WHITE))
        return tapered_pst(board)

    # Both boards are missing White's king, and g1 and e4 are empty on both,
    # so the two branches differ in nothing but where the king lands.
    opening = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQ1B1R w kq - 0 1"
    bare = "4k3/8/8/8/8/8/8/8 w - - 0 1"
    assert game_phase(chess.Board(opening)) > TOTAL_PHASE * 0.9
    assert game_phase(chess.Board(bare)) == 0

    # Full board: tucked away beats centralised. Bare kings: the reverse.
    assert with_king_on(opening, "g1") > with_king_on(opening, "e4")
    assert with_king_on(bare, "e4") > with_king_on(bare, "g1")


def test_tapered_pst_is_white_relative():
    board = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert tapered_pst(board) > 800
    mirrored = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1")
    assert tapered_pst(mirrored) == -tapered_pst(board)
