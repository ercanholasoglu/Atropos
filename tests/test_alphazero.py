"""AlphaZero-lite: encoding, network, tree search and the self-play loop."""

from __future__ import annotations

import chess
import numpy as np
import pytest

from research.alphazero_lite.encoding import (
    MOVE_PLANES,
    PLANES,
    POLICY_SIZE,
    encode_board,
    index_to_move,
    legal_move_mask,
    move_index,
    move_plane,
    policy_to_moves,
)
from research.alphazero_lite.mcts import MCTS, MCTSConfig, Node, terminal_value
from research.alphazero_lite.network import (
    Evaluator,
    NetworkConfig,
    UniformEvaluator,
    build_network,
    parameter_count,
    torch_available,
)
from research.alphazero_lite.selfplay import (
    AlphaZeroLite,
    SelfPlayConfig,
    TrainConfig,
    play_self_play_game,
    policy_target,
)

torch_only = pytest.mark.skipif(not torch_available(), reason="torch is not installed")

# Kiwipete with a white pawn added on b7, so the position also offers
# promotions and underpromotions alongside castling and en passant.
KIWIPETE = "r3k2r/pPppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
MATE_IN_ONE = "6k1/5ppp/8/8/8/8/5PPP/4Q1K1 w - - 0 1"


# --- board encoding -------------------------------------------------------


def test_the_board_becomes_the_planes_it_promises():
    planes = encode_board(chess.Board())
    assert planes.shape == (PLANES, 8, 8)
    assert planes[0].sum() == 8  # our pawns
    assert planes[6].sum() == 8  # theirs
    assert all(planes[12 + i, 0, 0] == 1.0 for i in range(4))  # all castling rights


def test_the_board_is_written_from_the_side_to_moves_point_of_view():
    """Flipping for Black is what stops the network learning chess twice."""
    board = chess.Board()
    board.push_san("e4")  # Black to move now
    planes = encode_board(board)
    assert planes[0].sum() == 8 and planes[6].sum() == 8
    # Our own pawns sit on the second rank from our side, whichever side that is.
    assert planes[0, 1].sum() >= 7


def test_en_passant_and_the_halfmove_clock_are_recorded():
    board = chess.Board("rnbqkbnr/pppp1ppp/8/3Pp3/8/8/PPP1PPPP/RNBQKBNR w KQkq e6 0 3")
    planes = encode_board(board)
    assert planes[17].sum() == 1.0

    quiet = chess.Board("4k3/8/8/8/8/8/8/4K3 w - - 40 60")
    assert encode_board(quiet)[18, 0, 0] == pytest.approx(0.4)


def test_castling_planes_follow_the_rights():
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1")
    planes = encode_board(board)
    assert planes[12:16].sum() == 0


# --- move encoding --------------------------------------------------------


def test_every_legal_move_in_a_busy_position_encodes_uniquely():
    """Kiwipete covers castling, en passant, promotion and underpromotion."""
    board = chess.Board(KIWIPETE)
    seen: dict[int, chess.Move] = {}
    for move in board.legal_moves:
        index = move_index(move, board.turn == chess.BLACK)
        assert 0 <= index < POLICY_SIZE
        assert index not in seen, f"{move} collides with {seen.get(index)}"
        seen[index] = move
    assert len(seen) == board.legal_moves.count() == 56


def test_every_encoded_move_decodes_back():
    board = chess.Board(KIWIPETE)
    for move in board.legal_moves:
        assert index_to_move(move_index(move, False), board) == move


def test_underpromotions_get_their_own_planes():
    """The reason for 73 planes rather than a flat from-to table."""
    board = chess.Board(KIWIPETE)
    promotions = [m for m in board.legal_moves if m.promotion]
    under = [m for m in promotions if m.promotion != chess.QUEEN]
    assert under, "the test position should offer underpromotions"

    queen_promotions = [m for m in promotions if m.promotion == chess.QUEEN]
    # Underpromotions live in the last nine planes; a queen promotion is just
    # a pawn push as far as the encoding is concerned.
    assert all(move_plane(move, False) >= 64 for move in under)
    assert all(move_plane(move, False) < 56 for move in queen_promotions)
    assert len({move_plane(move, False) for move in under}) > 1


def test_no_two_legal_moves_ever_share_an_index():
    """A sweep over random positions, because a collision is silent.

    Two moves mapping to one output would make the policy target ambiguous
    and the network's advice wrong, with nothing to notice it at runtime. An
    off-ray move used to encode as its ray neighbour; this is what caught it.
    """
    import random

    rng = random.Random(0)
    checked = 0
    for _ in range(120):
        board = chess.Board()
        for _ in range(rng.randint(0, 40)):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        if board.is_game_over():
            continue

        flip = board.turn == chess.BLACK
        seen: dict[int, chess.Move] = {}
        for move in board.legal_moves:
            index = move_index(move, flip)
            assert index not in seen, f"{move} collides with {seen[index]} in {board.fen()}"
            seen[index] = move
            checked += 1
    assert checked > 2000


def test_a_move_pointing_along_a_ray_but_not_on_it_is_refused():
    """a1-c4 points north-east but lands beside the ray, not on it."""
    with pytest.raises(ValueError):
        move_plane(chess.Move(chess.A1, chess.C4), False)


def test_planes_and_policy_width_agree():
    assert MOVE_PLANES == 73
    assert POLICY_SIZE == 73 * 64 == 4672


def test_an_unencodable_move_is_refused():
    with pytest.raises(ValueError):
        # Two files and three ranks: neither a queen line nor a knight jump.
        move_plane(chess.Move(chess.A1, chess.C4), False)


def test_a_mask_marks_exactly_the_legal_moves():
    board = chess.Board(KIWIPETE)
    assert legal_move_mask(board).sum() == board.legal_moves.count()


def test_a_flat_policy_becomes_a_uniform_prior():
    """An untrained network must not silently prefer the first move."""
    board = chess.Board()
    priors = policy_to_moves(np.zeros(POLICY_SIZE, dtype=np.float32), board)
    assert len(priors) == 20
    assert sum(priors.values()) == pytest.approx(1.0)
    assert len(set(np.round(list(priors.values()), 6))) == 1


def test_a_peaked_policy_survives_the_mapping():
    board = chess.Board()
    policy = np.zeros(POLICY_SIZE, dtype=np.float32)
    policy[move_index(chess.Move.from_uci("e2e4"))] = 5.0
    priors = policy_to_moves(policy, board)
    assert sum(priors.values()) == pytest.approx(1.0)
    assert max(priors, key=priors.get).uci() == "e2e4"


# --- network --------------------------------------------------------------


@torch_only
def test_the_network_is_small_enough_to_train_here():
    """A dense policy head would make this 8.7M — 25x bigger, 96% of it output."""
    model = build_network()
    assert 200_000 < parameter_count(model) < 600_000


@torch_only
def test_the_two_heads_answer_the_two_questions():
    import torch

    model = build_network(NetworkConfig(blocks=2, channels=16))
    logits, value = model(torch.zeros(4, PLANES, 8, 8))
    assert logits.shape == (4, POLICY_SIZE)
    assert value.shape == (4, 1)
    assert torch.all(value.abs() <= 1.0)


@torch_only
def test_the_evaluator_returns_a_distribution_and_a_value():
    evaluator = Evaluator(build_network(NetworkConfig(blocks=1, channels=8)))
    policy, value = evaluator.evaluate(encode_board(chess.Board()))
    assert policy.shape == (POLICY_SIZE,)
    assert policy.sum() == pytest.approx(1.0, abs=1e-4)
    assert -1.0 <= value <= 1.0
    assert evaluator.calls == 1


def test_the_uniform_evaluator_knows_nothing_on_purpose():
    """The control for measuring what the network contributes."""
    evaluator = UniformEvaluator()
    policy, value = evaluator.evaluate(encode_board(chess.Board()))
    assert value == 0.0
    assert policy.sum() == pytest.approx(1.0)
    assert len(set(policy)) == 1


# --- tree search ----------------------------------------------------------


def test_terminal_values_are_from_the_movers_point_of_view():
    mated = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert terminal_value(mated) == -1.0
    assert terminal_value(chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")) == 0.0
    assert terminal_value(chess.Board()) is None


def test_search_finds_mate_in_one_knowing_nothing():
    """The strongest check on the tree: no evaluation, just correct backup.

    With a uniform evaluator the network contributes nothing at all, so a
    move found here was found by search — and a sign error anywhere in the
    backup would make it pick something else.
    """
    board = chess.Board(MATE_IN_ONE)
    mcts = MCTS(UniformEvaluator(), MCTSConfig(simulations=300, dirichlet_weight=0.0), seed=1)
    _, visits = mcts.search(board)
    chosen = mcts.select_move(visits, ply=99)

    board.push(chosen)
    assert board.is_checkmate()
    assert mcts.stats.terminal_hits > 0


def test_search_leaves_the_board_alone():
    board = chess.Board(KIWIPETE)
    before = board.fen()
    MCTS(UniformEvaluator(), MCTSConfig(simulations=40), seed=1).search(board)
    assert board.fen() == before


def test_search_refuses_a_finished_game():
    over = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    with pytest.raises(ValueError):
        MCTS(UniformEvaluator()).search(over)


def test_every_simulation_is_counted_once():
    mcts = MCTS(UniformEvaluator(), MCTSConfig(simulations=50), seed=2)
    root, visits = mcts.search(chess.Board())
    assert mcts.stats.simulations == 50
    # The root's expansion does not count as a visit; each simulation passes
    # through it exactly once, and lands on exactly one child.
    assert root.visits == 50
    assert sum(visits.values()) == 50


def test_visits_become_the_training_target():
    mcts = MCTS(UniformEvaluator(), MCTSConfig(simulations=40), seed=3)
    _, visits = mcts.search(chess.Board())
    distribution = mcts.visit_distribution(visits)
    assert sum(distribution.values()) == pytest.approx(1.0)
    assert all(value >= 0 for value in distribution.values())


def test_temperature_explores_early_and_commits_later():
    mcts = MCTS(UniformEvaluator(), MCTSConfig(simulations=60, temperature_plies=20), seed=4)
    _, visits = mcts.search(chess.Board())
    best = max(visits, key=visits.get)

    assert mcts.select_move(visits, ply=30) == best  # past the cutoff: greedy
    sampled = {mcts.select_move(visits, ply=0) for _ in range(30)}
    assert len(sampled) > 1  # before it: varied


def test_root_noise_is_what_stops_self_play_repeating_itself():
    board = chess.Board()

    def priors(weight: float) -> list[float]:
        mcts = MCTS(UniformEvaluator(), MCTSConfig(simulations=1, dirichlet_weight=weight), seed=5)
        root, _ = mcts.search(board)
        return [child.prior for child in root.children.values()]

    assert len(set(np.round(priors(0.0), 6))) == 1  # untouched: flat
    assert len(set(np.round(priors(0.25), 6))) > 1  # noisy: not flat


def test_puct_prefers_the_prior_before_it_has_visits():
    parent = Node(visits=10)
    favoured = Node(prior=0.9)
    ignored = Node(prior=0.01)
    assert parent.puct(favoured, 1.5) > parent.puct(ignored, 1.5)

    # Once a move has been tried and found wanting, its value takes over.
    tried = Node(prior=0.9, visits=8, value_sum=8.0)  # good for the opponent
    assert parent.puct(tried, 1.5) < parent.puct(ignored, 1.5)


# --- self play ------------------------------------------------------------


def test_the_policy_target_is_the_searchs_distribution():
    board = chess.Board()
    visits = {chess.Move.from_uci("e2e4"): 30, chess.Move.from_uci("d2d4"): 10}
    target = policy_target(visits, board)

    assert target.shape == (POLICY_SIZE,)
    assert target.sum() == pytest.approx(1.0)
    assert target[move_index(chess.Move.from_uci("e2e4"))] == pytest.approx(0.75)


def test_an_empty_search_produces_an_empty_target():
    assert policy_target({}, chess.Board()).sum() == 0.0


def test_a_self_play_game_labels_both_sides_correctly():
    """Each position's value target is the result seen by whoever was to move."""
    mcts = MCTS(UniformEvaluator(), MCTSConfig(simulations=8, temperature_plies=2), seed=6)
    examples, summary = play_self_play_game(mcts, max_plies=8)

    assert len(examples) == summary.plies == 8
    assert summary.result in ("1-0", "0-1", "1/2-1/2")
    assert all(example.planes.shape == (PLANES, 8, 8) for example in examples)
    # Consecutive positions are seen by opposite players, so their targets
    # must be opposite too.
    values = [example.value for example in examples]
    assert all(a == -b for a, b in zip(values, values[1:])) or set(values) == {0.0}


@torch_only
def test_a_full_iteration_generates_data_and_learns_from_it():
    trainer = AlphaZeroLite(
        network=build_network(NetworkConfig(blocks=1, channels=8)),
        mcts_config=MCTSConfig(simulations=6, temperature_plies=2),
        selfplay_config=SelfPlayConfig(games=2, max_plies=8, seed=1),
        train_config=TrainConfig(iterations=1, epochs=2, batch_size=8),
    )
    seen: list[int] = []
    report = trainer.run(on_iteration=lambda r: seen.append(r.iteration))

    assert seen == [1]
    assert report.iterations[0].examples == len(trainer.buffer) == 16
    assert report.iterations[0].policy_loss > 0
    assert "policy" in report.table()


@torch_only
def test_the_buffer_is_a_window_not_a_history():
    """Positions from an older network describe a player that no longer exists."""
    trainer = AlphaZeroLite(
        network=build_network(NetworkConfig(blocks=1, channels=8)),
        mcts_config=MCTSConfig(simulations=4, temperature_plies=2),
        selfplay_config=SelfPlayConfig(games=1, max_plies=6, seed=2),
        train_config=TrainConfig(iterations=3, epochs=1, batch_size=4, buffer_size=8),
    )
    trainer.run()
    assert len(trainer.buffer) == 8
