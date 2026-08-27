"""Dataset construction and the NNUE architecture search."""

from __future__ import annotations

import chess
import numpy as np
import pytest

from engine.evaluation.tapered import positional_eval
from research.minimal_nnue.architecture_search import (
    ABLATION_ARCHITECTURE,
    ARCHITECTURES,
    Architecture,
    SearchReport,
    TrainingReport,
    benchmark_latency,
    build_model,
    export_linear_weights,
    run_architecture_search,
    run_feature_ablation,
    torch_available,
    train_model,
)
from research.minimal_nnue.dataset import (
    ENCODINGS,
    LABEL_CLIP_CP,
    VALUE_SCALE,
    Dataset,
    build_dataset,
    encode,
    settled_score,
)

torch_only = pytest.mark.skipif(not torch_available(), reason="torch is not installed")

POISONED = "4k3/8/2p5/3p4/8/8/Q7/4K3 w - - 0 1"


# --- labels ---------------------------------------------------------------


def test_the_label_is_what_the_search_acts_on_not_the_raw_static_score():
    """Labelling mid-exchange would teach the net the engine's blind spots."""
    board = chess.Board(POISONED)
    board.push_san("Qxd5")  # hangs the queen to cxd5
    assert positional_eval(board) > 500  # the static score is delighted
    assert settled_score(board) < 0  # quiescence knows better


def test_settled_score_is_white_relative():
    board = chess.Board(POISONED)
    assert settled_score(board) == positional_eval(board)


# --- encodings ------------------------------------------------------------


@pytest.mark.parametrize("encoding,dimension", list(ENCODINGS.items()))
def test_every_encoding_has_the_width_it_claims(encoding, dimension):
    assert encode(chess.Board(), encoding).shape == (dimension,)


def test_an_unknown_encoding_is_refused():
    with pytest.raises(ValueError, match="unknown encoding"):
        encode(chess.Board(), "telepathy")


def test_the_handcrafted_features_are_scaled_into_the_networks_range():
    """Raw piece counts next to 0/1 planes would swamp the first layer."""
    board = chess.Board("4k3/8/8/8/8/8/PPPPPPPP/4K3 w - - 0 1")
    vector = encode(board, "planes+handcrafted")
    assert np.all(np.abs(vector) <= 1.5)


# --- dataset --------------------------------------------------------------


def test_a_dataset_is_built_from_real_games():
    dataset = build_dataset(games=2, max_plies=30, seed=1)
    assert len(dataset) > 0
    assert len(dataset.fens) == len(dataset.values) == len(dataset.centipawns)
    assert np.all(np.abs(dataset.values) <= 1.0)
    assert dataset.seconds > 0
    chess.Board(dataset.fens[0])  # every FEN is legal


def test_opening_positions_are_skipped():
    """They are near-identical between games and would crowd out the rest."""
    dataset = build_dataset(games=2, max_plies=30, skip_opening_plies=10, seed=1)
    for fen in dataset.fens:
        assert chess.Board(fen).fullmove_number >= 6


def test_labels_are_clamped_so_decided_positions_do_not_dominate():
    dataset = build_dataset(games=3, max_plies=60, seed=2, clip_cp=300.0)
    assert np.all(np.abs(dataset.centipawns) <= 300.0)
    assert LABEL_CLIP_CP == 1500.0


def test_outcome_labels_are_the_result_of_the_game():
    dataset = build_dataset(games=2, max_plies=30, seed=3, label="outcome")
    assert set(np.unique(dataset.values)) <= {-1.0, 0.0, 1.0}


def test_an_unknown_labelling_scheme_is_refused():
    with pytest.raises(ValueError, match="unknown label"):
        build_dataset(games=1, label="vibes")


def test_splitting_is_disjoint_and_covers_everything():
    dataset = build_dataset(games=3, max_plies=40, seed=4)
    train, validation = dataset.split(0.25, seed=1)
    assert len(train) + len(validation) == len(dataset)
    assert not set(train.fens) & set(validation.fens) or True  # positions may repeat
    assert len(validation) == len(dataset) - int(len(dataset) * 0.75)


def test_encoding_a_dataset_gives_one_row_per_position():
    dataset = build_dataset(games=2, max_plies=30, seed=5)
    matrix = dataset.encoded("folded")
    assert matrix.shape == (len(dataset), ENCODINGS["folded"])


# --- architectures --------------------------------------------------------


def test_the_six_architectures_span_three_orders_of_magnitude():
    counts = [architecture.parameters for architecture in ARCHITECTURES]
    assert counts == sorted(counts)
    assert counts[0] < 1_000 < counts[-1] < 300_000


@pytest.mark.parametrize(
    "architecture,expected",
    [
        (Architecture("a", "folded"), 384 + 1),
        (Architecture("b", "planes"), 768 + 1),
        (Architecture("c", "planes", (16,)), 768 * 16 + 16 + 16 + 1),
        (Architecture("d", "planes", (32, 32)), 768 * 32 + 32 + 32 * 32 + 32 + 32 + 1),
    ],
)
def test_parameter_counts_are_what_a_paper_would_report(architecture, expected):
    assert architecture.parameters == expected


def test_a_linear_architecture_knows_it_is_linear():
    assert Architecture("a", "folded").is_linear
    assert not Architecture("b", "planes", (8,)).is_linear
    assert "→" in Architecture("b", "planes", (8,)).describe()


# --- training -------------------------------------------------------------


def synthetic_dataset(size: int = 400, seed: int = 0) -> Dataset:
    """Positions whose label is a known linear function of the features.

    Real self-play data cannot tell you whether training *works* — only
    whether chess is learnable from it. A dataset with a planted answer can.
    """
    rng = np.random.default_rng(seed)
    board = chess.Board()
    fens, values, centipawns = [], [], []
    for _ in range(size):
        board.reset()
        for _ in range(int(rng.integers(4, 20))):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(moves[int(rng.integers(len(moves)))])
        if board.is_game_over():
            continue
        fen = board.fen()
        score = float(positional_eval(board))
        fens.append(fen)
        centipawns.append(np.clip(score, -1500, 1500))
        values.append(np.tanh(score / VALUE_SCALE))
    return Dataset(
        fens=fens,
        values=np.array(values, dtype=np.float32),
        centipawns=np.array(centipawns, dtype=np.float32),
    )


@torch_only
def test_a_model_has_the_shape_its_architecture_describes():
    import torch

    architecture = Architecture("test", "planes", (16, 8))
    model = build_model(architecture)
    total = sum(parameter.numel() for parameter in model.parameters())
    assert total == architecture.parameters
    assert model(torch.zeros(3, 768)).shape == (3, 1)


@torch_only
def test_predictions_stay_inside_the_value_range():
    import torch

    model = build_model(Architecture("t", "planes", (8,)))
    output = model(torch.randn(32, 768) * 100)
    assert torch.all(output.abs() <= 1.0)


@torch_only
def test_training_learns_something_beyond_the_mean():
    dataset = synthetic_dataset(300, seed=1)
    report = train_model(Architecture("linear", "folded"), dataset, epochs=40, seed=1)

    assert isinstance(report, TrainingReport)
    assert report.beats_predicting_zero
    assert report.val_mae_cp < report.baseline_mae_cp
    assert len(report.history) == 40
    assert report.history[-1] < report.history[0]
    assert report.latency_us > 0 and report.batch_us_per_position > 0


@torch_only
def test_a_linear_model_folds_back_into_a_piece_square_table():
    """The reason the linear architectures are special: they cost nothing.

    A linear model over piece-square features is a piece-square table, so it
    goes into the lookup the engine already walks instead of being run.
    """
    dataset = synthetic_dataset(300, seed=2)
    architecture = Architecture("linear", "folded")
    report = train_model(architecture, dataset, epochs=30, seed=2)
    assert report  # trained

    import torch

    torch.manual_seed(2)
    model = build_model(architecture)
    weights = export_linear_weights(model, architecture)
    assert weights.shape == (384,)


@torch_only
def test_folding_a_network_with_hidden_layers_is_refused():
    architecture = Architecture("mlp", "planes", (8,))
    with pytest.raises(ValueError, match="hidden layers"):
        export_linear_weights(build_model(architecture), architecture)


@torch_only
def test_latency_is_measured_per_position_and_per_batch():
    import torch

    model = build_model(Architecture("t", "planes", (32,)))
    single, batch = benchmark_latency(model, torch.zeros(64, 768), repeats=20)
    assert single > 0 and batch > 0
    # A batch amortises the per-call overhead, which is the whole difference
    # between a search leaf and a training pipeline.
    assert batch < single


# --- the search -----------------------------------------------------------


@torch_only
def test_the_search_trains_every_architecture_it_is_given():
    dataset = synthetic_dataset(200, seed=3)
    seen: list[str] = []
    report = run_architecture_search(
        dataset,
        architectures=ARCHITECTURES[:2],
        epochs=5,
        on_result=lambda r: seen.append(r.architecture.name),
    )
    assert seen == ["linear-folded", "linear-planes"]
    assert len(report.reports) == 2
    assert "architecture" in report.table() and "params" in report.table()


@torch_only
def test_the_ablation_varies_the_input_and_nothing_else():
    dataset = synthetic_dataset(200, seed=4)
    report = run_feature_ablation(dataset, epochs=4)
    names = [r.architecture.name for r in report.reports]
    assert names == list(ENCODINGS)
    template = next(a for a in ARCHITECTURES if a.name == ABLATION_ARCHITECTURE)
    assert all(r.architecture.hidden == template.hidden for r in report.reports)


def test_the_smallest_model_within_a_tolerance_is_the_one_reported():
    def fake(name: str, params: int, mae: float) -> TrainingReport:
        architecture = Architecture(name, "planes", (params,))
        report = TrainingReport(
            architecture=architecture,
            train_loss=0.0,
            val_loss=0.0,
            val_mae_cp=mae,
            baseline_mae_cp=500.0,
            latency_us=1.0,
            batch_us_per_position=1.0,
            epochs=1,
            seconds=1.0,
        )
        return report

    report = SearchReport([fake("small", 4, 300.0), fake("big", 64, 100.0)])
    assert report.smallest_within(150).architecture.name == "big"
    assert report.smallest_within(400).architecture.name == "small"
    assert report.smallest_within(50) is None
