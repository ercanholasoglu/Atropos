import chess
import pytest

from engine.evaluation.material import (
    capture_gain,
    evaluate_material,
    material_score,
    piece_value,
    terminal_score,
)
from engine.utils.constants import MATE_SCORE, TOTAL_PHASE
from engine.utils.helpers import (
    flip_square,
    format_eval,
    game_phase,
    is_endgame,
    mate_in,
    result_to_score,
)


def test_start_position_is_balanced():
    assert material_score(chess.Board()) == 0


def test_material_score_counts_from_white_perspective():
    # Black is a queen down.
    board = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    assert material_score(board) == 900
    board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1")
    assert material_score(board) == -900


def test_king_does_not_affect_balance():
    assert piece_value(chess.KING) == 20000
    assert material_score(chess.Board()) == 0


def test_terminal_score_checkmate():
    # Fool's mate: White is mated, so the score is hugely negative.
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert board.is_checkmate()
    assert terminal_score(board) == -MATE_SCORE


def test_terminal_score_stalemate_and_ongoing():
    stalemate = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert stalemate.is_stalemate()
    assert terminal_score(stalemate) == 0
    assert terminal_score(chess.Board()) is None


def test_mate_score_shrinks_with_distance():
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    near = evaluate_material(board, ply=1)
    far = evaluate_material(board, ply=5)
    # Both are losses for White; the one further away is less bad.
    assert near < far < 0


def test_capture_gain_plain_capture():
    board = chess.Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
    exd5 = chess.Move.from_uci("e4d5")
    assert capture_gain(board, exd5) == 100
    assert capture_gain(board, chess.Move.from_uci("g1f3")) == 0


def test_capture_gain_en_passant():
    board = chess.Board("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3")
    ep = chess.Move.from_uci("e5f6")
    assert board.is_en_passant(ep)
    assert capture_gain(board, ep) == 100


def test_capture_gain_promotion():
    board = chess.Board("8/P7/8/8/8/8/8/K6k w - - 0 1")
    promo = chess.Move.from_uci("a7a8q")
    assert capture_gain(board, promo) == 900 - 100


def test_flip_square_mirrors_vertically():
    assert flip_square(chess.A1) == chess.A8
    assert flip_square(chess.E2) == chess.E7
    assert flip_square(flip_square(chess.C4)) == chess.C4


def test_game_phase_and_endgame():
    assert game_phase(chess.Board()) == TOTAL_PHASE
    assert not is_endgame(chess.Board())
    bare = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert game_phase(bare) == 0
    assert is_endgame(bare)


def test_format_eval_and_mate_in():
    assert format_eval(125) == "+1.25"
    assert format_eval(-40) == "-0.40"
    assert format_eval(MATE_SCORE - 3) == "M2"
    assert format_eval(-(MATE_SCORE - 4)) == "-M2"
    assert mate_in(50) is None


def test_result_to_score():
    assert result_to_score("1-0") == 1.0
    assert result_to_score("0-1") == 0.0
    assert result_to_score("1/2-1/2") == 0.5
    with pytest.raises(KeyError):
        result_to_score("*")


# --- positional terms -----------------------------------------------------


def test_doubled_pawns_are_counted_per_extra_pawn():
    from engine.evaluation.positional import count_doubled_pawns

    stacked = chess.Board("4k3/8/8/8/8/2P5/2P5/4K3 w - - 0 1")
    assert count_doubled_pawns(stacked, chess.WHITE) == 1
    tripled = chess.Board("4k3/8/8/8/2P5/2P5/2P5/4K3 w - - 0 1")
    assert count_doubled_pawns(tripled, chess.WHITE) == 2
    assert count_doubled_pawns(chess.Board(), chess.WHITE) == 0


def test_isolated_pawns_need_a_neighbour_on_an_adjacent_file():
    from engine.evaluation.positional import count_isolated_pawns

    alone = chess.Board("4k3/8/8/8/8/8/2P5/4K3 w - - 0 1")
    assert count_isolated_pawns(alone, chess.WHITE) == 1
    supported = chess.Board("4k3/8/8/8/8/8/1PP5/4K3 w - - 0 1")
    assert count_isolated_pawns(supported, chess.WHITE) == 0
    assert count_isolated_pawns(chess.Board(), chess.WHITE) == 0


def test_isolated_counts_every_pawn_on_a_lonely_file():
    from engine.evaluation.positional import count_isolated_pawns

    # Two pawns stacked on c-file with nothing on b or d: both are isolated.
    board = chess.Board("4k3/8/8/8/8/2P5/2P5/4K3 w - - 0 1")
    assert count_isolated_pawns(board, chess.WHITE) == 2


def test_edge_files_only_have_one_neighbour():
    from engine.evaluation.positional import count_isolated_pawns

    supported = chess.Board("4k3/8/8/8/8/8/PP6/4K3 w - - 0 1")
    assert count_isolated_pawns(supported, chess.WHITE) == 0
    lonely = chess.Board("4k3/8/8/8/8/8/P7/4K3 w - - 0 1")
    assert count_isolated_pawns(lonely, chess.WHITE) == 1


def test_bishop_pair_needs_two_bishops():
    from engine.evaluation.positional import BISHOP_PAIR_BONUS, has_bishop_pair, positional_score

    pair = chess.Board("4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1")
    assert has_bishop_pair(pair, chess.WHITE)
    assert not has_bishop_pair(pair, chess.BLACK)
    assert positional_score(pair) == BISHOP_PAIR_BONUS

    single = chess.Board("4k3/8/8/8/8/8/8/2B1K3 w - - 0 1")
    assert not has_bishop_pair(single, chess.WHITE)


def test_positional_score_is_symmetric_at_the_start():
    from engine.evaluation.positional import positional_score

    assert positional_score(chess.Board()) == 0


def test_positional_score_penalises_the_side_with_the_worse_pawns():
    from engine.evaluation.positional import positional_score

    # White's c-pawns are doubled and isolated; Black's pawns are healthy.
    board = chess.Board("4k3/pp6/8/8/8/2P5/2P5/4K3 w - - 0 1")
    assert positional_score(board) < 0


def test_pawn_structure_score_is_zero_without_pawns():
    from engine.evaluation.positional import pawn_structure_score

    bare = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert pawn_structure_score(bare, chess.WHITE) == 0


def test_mobility_counts_moves_for_either_side():
    from engine.evaluation.positional import mobility

    board = chess.Board()
    assert mobility(board, chess.WHITE) == 20
    assert mobility(board, chess.BLACK) == 20  # works for the side not to move
    assert board.fen() == chess.STARTING_FEN  # and leaves the board alone


def test_king_shield_counts_pawns_in_front_of_the_king():
    from engine.evaluation.positional import king_shield

    castled = chess.Board("4k3/8/8/8/8/8/5PPP/6K1 w - - 0 1")
    assert king_shield(castled, chess.WHITE) == 3
    exposed = chess.Board("4k3/8/8/8/8/8/8/6K1 w - - 0 1")
    assert king_shield(exposed, chess.WHITE) == 0


def test_king_shield_handles_a_king_on_the_last_rank():
    from engine.evaluation.positional import king_shield

    board = chess.Board("6K1/8/8/8/8/8/8/4k3 w - - 0 1")
    assert king_shield(board, chess.WHITE) == 0


def test_the_bitboard_pawn_structure_matches_the_counters():
    """Exactly equivalent, and the first version of it was not.

    A bidirectional file fill marks every pawn as doubled, because a filled
    file is trivially above itself. This assertion caught that on its first
    run; it is here so the next rewrite has the same net under it.
    """
    import random

    from engine.evaluation.positional import (
        DOUBLED_PAWN_PENALTY,
        ISOLATED_PAWN_PENALTY,
        count_doubled_pawns,
        count_isolated_pawns,
        pawn_structure_score,
    )

    rng = random.Random(1)
    checked = 0
    for _ in range(150):
        board = chess.Board()
        for _ in range(rng.randint(0, 60)):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        for color in (chess.WHITE, chess.BLACK):
            expected = -(
                DOUBLED_PAWN_PENALTY * count_doubled_pawns(board, color)
                + ISOLATED_PAWN_PENALTY * count_isolated_pawns(board, color)
            )
            assert pawn_structure_score(board, color) == expected, board.fen()
            checked += 1
    assert checked > 200


def test_a_full_file_of_pawns_is_counted_once_per_extra_pawn():
    """The case the broken fill got wrong."""
    from engine.evaluation.positional import DOUBLED_PAWN_PENALTY, pawn_structure_score

    # Eight white pawns, one per file: no doubles, no isolani, no penalty.
    spread = chess.Board("4k3/8/8/8/1P3P1P/P5P1/2PPP3/4K3 w - - 0 1")
    assert pawn_structure_score(spread, chess.WHITE) == 0

    stacked = chess.Board("4k3/8/8/8/2P5/2P5/1PP5/4K3 w - - 0 1")
    assert pawn_structure_score(stacked, chess.WHITE) == -DOUBLED_PAWN_PENALTY * 2
