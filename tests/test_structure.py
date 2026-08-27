"""Evaluation v3: passed pawns, rook files and king safety."""

from __future__ import annotations

import chess
import pytest

from engine.evaluation.structure import (
    KING_SAFETY_MIN_PHASE,
    PASSED_PAWN_MASKS,
    king_attacker_score,
    king_safety_score,
    king_shelter_score,
    passed_pawn_score,
    passed_pawn_scores,
    rook_file_score,
    structure_score,
)
from engine.evaluation.tapered import positional_eval, positional_eval_v3
from engine.utils.constants import TOTAL_PHASE
from engine.utils.helpers import game_phase

# --- passed pawns ---------------------------------------------------------


def test_a_pawn_with_nothing_in_front_of_it_is_passed():
    board = chess.Board("4k3/8/8/8/8/5P2/8/4K3 w - - 0 1")
    middlegame, endgame = passed_pawn_scores(board, chess.WHITE)
    assert middlegame > 0 and endgame > middlegame


def test_an_enemy_pawn_ahead_stops_it():
    blocked = chess.Board("4k3/5p2/8/8/8/5P2/8/4K3 w - - 0 1")
    assert passed_pawn_scores(blocked, chess.WHITE) == (0, 0)


def test_an_enemy_pawn_on_an_adjacent_file_also_stops_it():
    """A passer has to be past the pawns that could capture it, too."""
    board = chess.Board("4k3/6p1/8/8/8/5P2/8/4K3 w - - 0 1")
    assert passed_pawn_scores(board, chess.WHITE) == (0, 0)


def test_a_pawn_behind_the_enemy_pawn_is_passed_again():
    board = chess.Board("4k3/8/5P2/6p1/8/8/8/4K3 w - - 0 1")
    assert passed_pawn_scores(board, chess.WHITE)[0] > 0


def test_the_further_it_has_come_the_more_it_is_worth():
    third = chess.Board("4k3/8/8/8/8/5P2/8/4K3 w - - 0 1")
    seventh = chess.Board("4k3/5P2/8/8/8/8/8/4K3 w - - 0 1")
    assert (
        passed_pawn_scores(seventh, chess.WHITE)[0] > passed_pawn_scores(third, chess.WHITE)[0] * 5
    )


def test_a_protected_passer_is_worth_more_than_a_lone_one():
    lone = chess.Board("4k3/8/8/4P3/8/8/8/4K3 w - - 0 1")
    protected = chess.Board("4k3/8/8/4P3/3P4/8/8/4K3 w - - 0 1")
    lone_score = passed_pawn_scores(lone, chess.WHITE)[0]
    both = passed_pawn_scores(protected, chess.WHITE)[0]
    assert both > 2 * lone_score - 40  # the d-pawn is passed too; the bonus is on top


def test_the_two_phase_scan_agrees_with_asking_for_one():
    board = chess.Board("4k3/5P2/8/4P3/8/8/8/4K3 w - - 0 1")
    middlegame, endgame = passed_pawn_scores(board, chess.WHITE)
    assert passed_pawn_score(board, chess.WHITE, endgame=False) == middlegame
    assert passed_pawn_score(board, chess.WHITE, endgame=True) == endgame


def test_a_side_with_no_pawns_scores_nothing():
    assert passed_pawn_scores(chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1"), chess.WHITE) == (0, 0)


def test_the_masks_look_forward_for_each_colour():
    white = PASSED_PAWN_MASKS[chess.WHITE][chess.E2]
    black = PASSED_PAWN_MASKS[chess.BLACK][chess.E7]
    assert white & chess.BB_SQUARES[chess.E7]
    assert not white & chess.BB_SQUARES[chess.E1]
    assert black & chess.BB_SQUARES[chess.E2]
    assert not black & chess.BB_SQUARES[chess.E8]


# --- rook files -----------------------------------------------------------


def test_a_rook_on_a_file_with_no_pawns_gets_the_full_bonus():
    board = chess.Board("4k3/8/8/8/8/8/8/3RK3 w - - 0 1")
    assert rook_file_score(board, chess.WHITE) > 0


def test_a_rook_behind_its_own_pawn_gets_nothing():
    board = chess.Board("4k3/8/8/8/8/3P4/8/3RK3 w - - 0 1")
    assert rook_file_score(board, chess.WHITE) == 0


def test_a_semi_open_file_is_worth_less_than_an_open_one():
    open_file = chess.Board("4k3/8/8/8/8/8/8/3RK3 w - - 0 1")
    semi_open = chess.Board("4k3/3p4/8/8/8/8/8/3RK3 w - - 0 1")
    assert rook_file_score(open_file, chess.WHITE) > rook_file_score(semi_open, chess.WHITE) > 0


def test_no_rooks_means_no_score():
    assert rook_file_score(chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1"), chess.WHITE) == 0


# --- king safety ----------------------------------------------------------


def test_a_king_behind_its_pawns_is_safer_than_one_in_the_open():
    sheltered = chess.Board("4k3/8/8/8/8/8/5PPP/6K1 w - - 0 1")
    exposed = chess.Board("4k3/8/8/8/8/8/8/6K1 w - - 0 1")
    assert king_shelter_score(sheltered, chess.WHITE) > king_shelter_score(exposed, chess.WHITE)


def test_an_open_file_beside_the_king_is_a_road_in():
    closed = chess.Board("4k3/8/8/8/8/8/5PPP/6K1 w - - 0 1")
    half_open = chess.Board("4k3/8/8/8/8/8/5P1P/6K1 w - - 0 1")
    assert king_shelter_score(closed, chess.WHITE) > king_shelter_score(half_open, chess.WHITE)


def test_pieces_aimed_at_the_king_are_a_penalty():
    quiet = chess.Board("4k3/8/8/8/8/8/5PPP/6K1 w - - 0 1")
    besieged = chess.Board("4k3/8/8/8/6q1/5n2/5PPP/6K1 w - - 0 1")
    assert king_attacker_score(besieged, chess.WHITE) < king_attacker_score(quiet, chess.WHITE) <= 0


def test_both_halves_add_up():
    board = chess.Board("4k3/8/8/8/6q1/8/5PPP/6K1 w - - 0 1")
    assert king_safety_score(board, chess.WHITE) == king_shelter_score(
        board, chess.WHITE
    ) + king_attacker_score(board, chess.WHITE)


def test_a_board_with_no_king_does_not_crash():
    board = chess.Board("8/8/8/8/8/8/5PPP/8 w - - 0 1")
    assert king_shelter_score(board, chess.WHITE) == 0
    assert king_attacker_score(board, chess.WHITE) == 0


# --- tapering and cost ----------------------------------------------------


def test_the_start_position_is_symmetric():
    assert structure_score(chess.Board(), TOTAL_PHASE) == 0


def test_king_safety_is_skipped_once_it_stops_mattering():
    """Computing it and multiplying by nearly zero is paying full price for
    a rounding error."""
    board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 1")
    assert game_phase(board) < KING_SAFETY_MIN_PHASE
    with_safety = structure_score(board, game_phase(board), king_attackers=True)
    without = structure_score(board, game_phase(board), king_attackers=False)
    assert with_safety == without


def test_passed_pawns_matter_more_as_the_board_empties():
    board = chess.Board("4k3/8/8/4P3/8/8/8/4K3 w - - 0 1")
    opening = structure_score(board, TOTAL_PHASE)
    ending = structure_score(board, 0)
    assert ending > opening > 0


def test_the_expensive_half_can_be_left_out():
    board = chess.Board("r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9")
    assert structure_score(board, 24, king_attackers=True) != structure_score(
        board, 24, king_attackers=False
    )


# --- the composed evaluation ---------------------------------------------


def test_v3_is_v2_plus_the_new_terms():
    board = chess.Board("r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1BP2/PPPQ2PP/R3K2R w KQ - 0 9")
    assert positional_eval_v3(board) == positional_eval(board) + structure_score(
        board, game_phase(board), True
    )


def test_v3_stays_white_relative():
    white_up = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
    black_up = chess.Board("4k3/4p3/8/8/8/8/8/4K3 w - - 0 1")
    assert positional_eval_v3(white_up) == -positional_eval_v3(black_up)


def test_v3_agrees_with_v2_where_it_has_nothing_to_add():
    """Bare kings: no pawns, no rooks, nothing to say."""
    bare = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert positional_eval_v3(bare) == positional_eval(bare)
