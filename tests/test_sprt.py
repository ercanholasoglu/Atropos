"""Sequential testing.

The point of an SPRT is that it stops when the games have answered. These
tests check that it stops for the right reasons, in the right direction, and
that a drawish pairing costs it more evidence — which is the property that
makes it honest about engine matches, where most games are draws.
"""

from __future__ import annotations

import math
import random

import pytest

from elo.sprt import (
    DRAW,
    LOSS,
    WIN,
    Sprt,
    SprtConfig,
    Verdict,
    draw_elo_from_ratio,
    outcome_probabilities,
)

# --- the model ------------------------------------------------------------


def test_outcome_probabilities_are_a_distribution():
    for elo in (-200, -20, 0, 20, 200):
        win, draw, loss = outcome_probabilities(elo, 250)
        assert win > 0 and draw > 0 and loss > 0
        assert win + draw + loss == pytest.approx(1.0)


def test_equal_strength_is_symmetric():
    win, _, loss = outcome_probabilities(0, 250)
    assert win == pytest.approx(loss)


def test_being_better_shows_up_as_a_higher_score():
    def score(elo: float) -> float:
        win, draw, _ = outcome_probabilities(elo, 250)
        return win + draw / 2

    assert score(0) == pytest.approx(0.5)
    assert score(-50) < score(0) < score(50)


def test_a_drawish_pairing_has_fewer_decisive_games():
    """The reason draw elo matters: draws carry almost no information."""
    _, quiet_draws, _ = outcome_probabilities(0, draw_elo_from_ratio(0.8))
    _, sharp_draws, _ = outcome_probabilities(0, draw_elo_from_ratio(0.2))
    assert quiet_draws > sharp_draws


def test_draw_elo_rises_with_the_draw_rate():
    assert draw_elo_from_ratio(0.2) < draw_elo_from_ratio(0.5) < draw_elo_from_ratio(0.9)


# --- the bounds -----------------------------------------------------------


def test_the_bounds_come_from_the_error_rates():
    config = SprtConfig(alpha=0.05, beta=0.05)
    assert config.upper_bound == pytest.approx(math.log(0.95 / 0.05))
    assert config.lower_bound == pytest.approx(math.log(0.05 / 0.95))
    assert config.lower_bound < 0 < config.upper_bound


def test_tighter_error_rates_need_more_evidence():
    loose = SprtConfig(alpha=0.1, beta=0.1)
    strict = SprtConfig(alpha=0.01, beta=0.01)
    assert strict.upper_bound > loose.upper_bound


# --- accumulating ---------------------------------------------------------


def test_nothing_is_decided_before_any_games():
    test = Sprt()
    assert test.games == 0 and test.llr == 0.0
    assert test.verdict is Verdict.CONTINUE and not test.finished


def test_results_are_counted_and_scored():
    test = Sprt()
    test.record(WIN)
    test.record(DRAW)
    test.record(LOSS)
    assert (test.wins, test.draws, test.losses) == (1, 1, 1)
    assert test.games == 3 and test.score == 0.5


def test_wins_push_the_ratio_up_and_losses_down():
    winning, losing = Sprt(), Sprt()
    for _ in range(30):
        winning.record(WIN)
        losing.record(LOSS)
    assert winning.llr > 0 > losing.llr


def test_a_clear_improvement_is_accepted():
    test = Sprt(SprtConfig(elo0=0, elo1=10))
    for _ in range(200):
        if test.finished:
            break
        test.record(WIN if test.games % 3 else DRAW)
    assert test.verdict is Verdict.ACCEPT_H1
    assert test.games < 200  # it stopped early, which is the whole point


def test_a_clear_regression_is_rejected():
    test = Sprt(SprtConfig(elo0=0, elo1=10))
    for _ in range(200):
        if test.finished:
            break
        test.record(LOSS if test.games % 3 else DRAW)
    assert test.verdict is Verdict.ACCEPT_H0


def test_a_dead_heat_runs_out_of_games_rather_than_guessing():
    """Exactly on the boundary is the case no amount of evidence settles."""
    test = Sprt(SprtConfig(elo0=0, elo1=10, max_games=120))
    while not test.finished:
        test.record(DRAW)
    assert test.verdict is Verdict.EXHAUSTED
    assert test.games == 120


def test_the_draw_estimate_waits_for_enough_games():
    """An early run of draws must not push the estimate to an extreme."""
    config = SprtConfig(initial_draw_elo=250.0, min_games_for_draw_estimate=20)
    test = Sprt(config)
    for _ in range(5):
        test.record(DRAW)
    assert test.draw_elo == 250.0

    for _ in range(20):
        test.record(DRAW)
    assert test.draw_elo != 250.0


def test_the_summary_says_where_the_test_stands():
    test = Sprt()
    test.record(WIN)
    text = test.summary()
    assert "LLR" in text and "continue" in text


# --- behaviour over simulated matches ------------------------------------


def simulate(true_elo: float, config: SprtConfig, draw_ratio: float, seed: int) -> Sprt:
    rng = random.Random(seed)
    win, draw, _ = outcome_probabilities(true_elo, draw_elo_from_ratio(draw_ratio))
    test = Sprt(config)
    while not test.finished:
        roll = rng.random()
        test.record(WIN if roll < win else (DRAW if roll < win + draw else LOSS))
    return test


def test_a_big_improvement_is_confirmed_quickly():
    test = simulate(80, SprtConfig(elo0=0, elo1=40, max_games=2000), 0.35, seed=3)
    assert test.verdict is Verdict.ACCEPT_H1
    assert test.games < 400


def test_a_worthless_change_is_rejected():
    test = simulate(0, SprtConfig(elo0=0, elo1=40, max_games=2000), 0.35, seed=5)
    assert test.verdict is Verdict.ACCEPT_H0


def test_a_wider_bracket_asks_a_coarser_question_and_answers_sooner():
    """The trade this project actually has to make: compute against precision."""
    tight = simulate(80, SprtConfig(elo0=0, elo1=10, max_games=4000), 0.35, seed=9)
    wide = simulate(80, SprtConfig(elo0=0, elo1=40, max_games=4000), 0.35, seed=9)
    assert wide.games < tight.games
    assert tight.verdict is wide.verdict is Verdict.ACCEPT_H1


def test_a_drawish_pairing_costs_more_games():
    sharp = simulate(60, SprtConfig(elo0=0, elo1=40, max_games=4000), 0.2, seed=11)
    drawish = simulate(60, SprtConfig(elo0=0, elo1=40, max_games=4000), 0.85, seed=11)
    assert drawish.games > sharp.games


@pytest.mark.slow
def test_the_false_acceptance_rate_is_near_what_was_asked_for():
    """alpha is a promise; this checks it is roughly kept."""
    config = SprtConfig(elo0=0, elo1=40, alpha=0.05, beta=0.05, max_games=1500)
    accepted = sum(
        1 for seed in range(60) if simulate(0, config, 0.35, seed).verdict is Verdict.ACCEPT_H1
    )
    assert accepted <= 6  # 5% of 60 is 3; allow for the small sample


# --- the gate accepts every kind of opponent this project has -------------


def test_engine_specs_cover_variants_levels_and_external_binaries(tmp_path):
    """One gate for every comparison: evaluations, rungs, and outside engines."""
    import sys

    from scripts.sprt_match import build
    from tournament.uci_engine import UciEngineProcess

    variant = build("v2", seed=1, movetime=0.05)
    assert variant.name == "v2"

    level = build("L4", seed=1, movetime=0.05)
    assert level.level == 4

    with pytest.raises(SystemExit, match="cannot make an engine"):
        build("nonsense", 1, 0.05)

    with pytest.raises(SystemExit, match="not implemented"):
        build("L99", 1, 0.05)


def test_a_run_can_be_resumed_from_its_state(tmp_path):
    """Anything that takes an hour gets interrupted; state is written per game."""
    from scripts.sprt_match import load, save

    path = tmp_path / "state.json"
    config = SprtConfig(elo0=0, elo1=40)

    fresh = load(path, config)
    assert fresh.games == 0

    fresh.record(WIN)
    fresh.record(DRAW)
    fresh.record(LOSS)
    save(path, fresh, {"a": "x", "b": "y"})

    resumed = load(path, config)
    assert (resumed.wins, resumed.draws, resumed.losses) == (1, 1, 1)
    assert resumed.llr == pytest.approx(fresh.llr)


def test_saved_state_records_what_the_run_was():
    """A state file nobody can interpret is not a resumable run."""
    import json
    import tempfile

    from scripts.sprt_match import save

    with tempfile.TemporaryDirectory() as directory:
        path = __import__("pathlib").Path(directory) / "s.json"
        test = Sprt(SprtConfig(elo0=0, elo1=40))
        test.record(WIN)
        save(path, test, {"a": "candidate", "b": "baseline", "movetime": 0.1})

        stored = json.loads(path.read_text())
        assert stored["a"] == "candidate" and stored["b"] == "baseline"
        assert stored["games"] == 1 and stored["verdict"] == "continue"
        assert stored["config"]["elo1"] == 40


# --- saying what is known while the test is still running ----------------


def test_an_interval_needs_games():
    assert Sprt().score_interval() == (0.0, 1.0)


def test_the_interval_narrows_as_games_accumulate():
    def interval_width(repeats: int) -> float:
        test = Sprt(SprtConfig(max_games=10_000))
        for index in range(repeats):
            test.record(WIN if index % 2 else LOSS)
        low, high = test.score_interval()
        return high - low

    assert interval_width(400) < interval_width(100) < interval_width(30)


def test_the_interval_brackets_the_observed_score():
    test = Sprt(SprtConfig(max_games=10_000))
    for index in range(200):
        test.record(WIN if index % 4 else DRAW)
    low, high = test.score_interval()
    assert low < test.score < high


def test_a_drawn_match_is_precise_and_says_nothing():
    """All draws: the score is exactly 0.5 with no spread, and no information."""
    test = Sprt(SprtConfig(max_games=500))
    for _ in range(100):
        test.record(DRAW)
    low, high = test.score_interval()
    assert low == high == pytest.approx(0.5)
    assert not test.finished  # precision is not evidence


def test_the_elo_interval_is_reported_in_the_unit_the_question_uses():
    test = Sprt(SprtConfig(elo0=0, elo1=40, max_games=10_000))
    for index in range(300):
        test.record(WIN if index % 3 == 0 else (DRAW if index % 3 == 1 else LOSS))
    low, high = test.elo_interval()
    assert low < 0 < high  # a dead heat straddles zero


def test_the_diagnosis_explains_why_it_is_still_running():
    """'continue' is not an answer; the interval is."""
    test = Sprt(SprtConfig(elo0=0, elo1=40, max_games=10_000))
    for index in range(40):
        test.record(WIN if index % 2 else LOSS)
    assert "spans the whole bracket" in test.diagnosis()


def test_a_finished_test_reports_its_verdict_rather_than_a_diagnosis():
    test = Sprt(SprtConfig(elo0=0, elo1=10))
    while not test.finished:
        test.record(WIN if test.games % 3 else DRAW)
    assert test.diagnosis() == test.verdict.value


def test_the_summary_carries_the_interval():
    test = Sprt()
    for _ in range(20):
        test.record(DRAW)
    assert "Elo [" in test.summary()


# --- reading the ladder's state ------------------------------------------


def test_adjacent_pairs_walk_the_whole_ladder():
    from engine.levels import available_levels
    from scripts.ladder_sprt import adjacent_pairs

    pairs = adjacent_pairs()
    levels = available_levels()
    assert len(pairs) == len(levels) - 1
    assert pairs[0] == (levels[1], levels[0])
    assert all(high == low + 1 for high, low in pairs)


def test_pairs_can_be_named_explicitly():
    from scripts.ladder_sprt import parse_pairs

    assert parse_pairs("7:6,8:7") == [(7, 6), (8, 7)]
    assert len(parse_pairs("adjacent")) > 1


def test_a_pairing_with_no_state_reads_as_not_run(tmp_path, monkeypatch):
    import scripts.ladder_sprt as module

    monkeypatch.setattr(module, "state_path", lambda h, l: tmp_path / f"L{h}_{l}.json")
    assert module.load_state(7, 6, SprtConfig()) is None


def test_state_written_by_a_run_is_read_back_by_the_reporter(tmp_path, monkeypatch):
    import scripts.ladder_sprt as module
    from scripts.sprt_match import save

    path = tmp_path / "L7_6.json"
    monkeypatch.setattr(module, "state_path", lambda h, l: path)

    test = Sprt(SprtConfig(elo0=0, elo1=100))
    for _ in range(12):
        test.record(WIN)
    save(path, test, {"a": "L7", "b": "L6"})

    reloaded = module.load_state(7, 6, SprtConfig(elo0=0, elo1=100))
    assert reloaded is not None
    assert reloaded.wins == 12 and reloaded.score == 1.0


def test_the_driver_walks_pairings_cheapest_first(monkeypatch, tmp_path):
    """Lower rungs are hundreds of Elo apart and decide in a couple of dozen
    games, so a short budget returns real verdicts instead of six half-finished
    tests."""
    import scripts.ladder_sprt as module

    monkeypatch.setattr(module, "state_path", lambda h, l: tmp_path / f"L{h}_{l}.json")
    order: list[tuple[int, int]] = []

    def fake_play(high, low, test, args, deadline, recorder=None):
        order.append((high, low))
        for _ in range(3):
            test.record(WIN)
        return 3

    monkeypatch.setattr(module, "play_pairing", fake_play)

    class Args:
        pairs = "5:4,2:1,3:2"
        elo0, elo1, max_games = 0.0, 100.0, 600
        movetime, max_plies = 0.05, 40
        minutes_total = 1.0
        report_only = False

    module.run_pairings(Args(), SprtConfig(elo0=0, elo1=100, max_games=600))
    assert order == [(2, 1), (3, 2), (5, 4)]


def test_a_decided_pairing_is_not_replayed(monkeypatch, tmp_path, capsys):
    import scripts.ladder_sprt as module
    from scripts.sprt_match import save

    path = tmp_path / "L2_1.json"
    monkeypatch.setattr(module, "state_path", lambda h, l: path)

    decided = Sprt(SprtConfig(elo0=0, elo1=100))
    while not decided.finished:
        decided.record(WIN)
    save(path, decided, {"a": "L2", "b": "L1"})

    monkeypatch.setattr(
        module, "play_pairing", lambda *a, **k: pytest.fail("should not replay a decided pairing")
    )

    class Args:
        pairs = "2:1"
        elo0, elo1, max_games = 0.0, 100.0, 600
        movetime, max_plies = 0.05, 40
        minutes_total = 1.0

    module.run_pairings(Args(), SprtConfig(elo0=0, elo1=100, max_games=600))
    assert "already" in capsys.readouterr().out


# --- playing games in parallel -------------------------------------------


def test_a_game_can_be_played_from_plain_data():
    """The pool has to pickle what it is handed, so a job is a tuple.

    Nodes come back with the score because a run has to report what its answer
    cost, and that is not reconstructable once the run is over.
    """
    from scripts.sprt_match import play_one

    score, nodes, pgn = play_one(("L1", "L1", 0, 0.02, 20, "default"))
    assert score in (0.0, 0.5, 1.0)
    assert nodes >= 0
    assert pgn.startswith("[Event ")


def test_the_same_job_index_replays_the_same_game():
    """Seeds move with the index, so a resumed or parallel run does not
    silently repeat or skip games."""
    from scripts.sprt_match import play_one

    first = play_one(("L2", "L1", 3, 0.02, 20, "default"))
    again = play_one(("L2", "L1", 3, 0.02, 20, "default"))
    assert first == again


def test_parallel_and_serial_cover_the_same_game_indices():
    """A batch of six is games n..n+5 — no gaps, no repeats."""
    workers = 6
    played = 0
    indices: list[int] = []
    for _ in range(3):
        indices.extend(played + offset for offset in range(workers))
        played += workers
    assert indices == list(range(18))


# --- what a run cost, recorded while it happens --------------------------


def test_telemetry_records_cost_and_provenance(tmp_path):
    """It cannot be reconstructed afterwards, which is the whole point."""
    from scripts.telemetry import TelemetryRecorder

    with TelemetryRecorder("probe", {"a": "x"}, tmp_path) as recorder:
        recorder.add_nodes(1000)
        recorder.add_games(2)
        sum(i * i for i in range(200_000))

    import json

    saved = json.loads(recorder.path.read_text())
    assert saved["tool"] == "probe"
    assert saved["nodes"] == 1000 and saved["games"] == 2
    assert saved["wall_seconds"] > 0 and saved["cpu_seconds"] > 0
    assert saved["peak_rss_mb_largest_process"] > 0
    assert saved["parameters"] == {"a": "x"}
    assert "cpu_count" in saved["machine"]


def test_telemetry_writes_even_when_the_run_fails():
    """An interrupted experiment costs the same CPU as one that finished."""
    import json
    import tempfile
    from pathlib import Path

    from scripts.telemetry import TelemetryRecorder

    with tempfile.TemporaryDirectory() as directory:
        recorder = TelemetryRecorder("probe", {}, Path(directory))
        try:
            with recorder:
                recorder.add_games(1)
                raise RuntimeError("interrupted")
        except RuntimeError:
            pass
        saved = json.loads(recorder.path.read_text())
        assert saved["games"] == 1
        assert any("interrupted" in note for note in saved["notes"])


def test_an_unknown_commit_is_null_not_a_guess():
    """A record that cannot name its commit must not appear to name one."""
    from scripts.audit_records import commit_of

    assert commit_of({"commit": "abc1234"}) == "abc1234"
    assert commit_of({"commit": None}) is None
    assert commit_of({"commit": "   "}) is None
    assert commit_of({}) is None


def test_the_audit_separates_traced_records_from_untraced(tmp_path):
    import json
    import sys

    from scripts.audit_records import main

    (tmp_path / "traced.json").write_text(json.dumps({"commit": "deadbee", "games": 1}))
    (tmp_path / "untraced.json").write_text(json.dumps({"games": 2}))

    argv = sys.argv
    sys.argv = ["audit_records", "--data", str(tmp_path), "--write"]
    try:
        assert main() == 0
    finally:
        sys.argv = argv

    stamped = json.loads((tmp_path / "untraced.json").read_text())
    assert stamped["commit"] is None
    assert stamped["provenance"] == "commit unknown"
    assert json.loads((tmp_path / "traced.json").read_text())["commit"] == "deadbee"


def test_the_book_is_part_of_the_job():
    """Which openings a game starts from travels with the job, not as state.

    A pool worker is a fresh process with no memory of what the run chose, so
    a book selected on the command line has to be handed to it explicitly. It
    was not, until --book was added, and these two calls would otherwise play
    the same game from different positions without saying so.
    """
    from scripts.sprt_match import play_one

    default = play_one(("L2", "L1", 1, 0.02, 20, "default"))
    midgame = play_one(("L2", "L1", 1, 0.02, 20, "midgame"))
    # Same engines, same index, different starting position: the node counts
    # have no reason to match, and if they do the book was ignored.
    assert default[1] != midgame[1]


def test_an_unknown_book_fails_loudly():
    from tournament.openings import load_book

    with pytest.raises(SystemExit):
        load_book("no-such-book")


def test_a_saved_game_round_trips_through_a_pgn_reader(tmp_path):
    """Games are written so they can be replayed, not just counted.

    An engine's own PGN writer agreeing with itself proves nothing; this
    parses what was written with a reader that had no part in producing it,
    and plays every move back onto a board.
    """
    import io

    import chess.pgn

    from scripts.sprt_match import play_one, save_pgn

    target = tmp_path / "games.pgn"
    for index in range(3):
        _, _, pgn = play_one(("L2", "L1", index, 0.02, 20, "default"))
        save_pgn(target, pgn)

    handle = io.StringIO(target.read_text())
    played = 0
    while (game := chess.pgn.read_game(handle)) is not None:
        board = game.board()
        for move in game.mainline_moves():
            assert move in board.legal_moves
            board.push(move)
        played += 1
    assert played == 3


def test_saving_is_opt_in_and_appends(tmp_path):
    """No path means no file; a second call adds to the first.

    Appending matters because a run that stops half way keeps the games it
    already played, the same way its tally does.
    """
    from scripts.sprt_match import save_pgn

    save_pgn(None, '[Event "x"]\n\n1. e4 *')  # must not raise or create anything
    assert not list(tmp_path.iterdir())

    target = tmp_path / "nested" / "games.pgn"
    save_pgn(target, '[Event "one"]\n\n1. e4 *')
    save_pgn(target, '[Event "two"]\n\n1. d4 *')
    assert target.read_text().count("[Event") == 2


def test_an_empty_game_is_not_written(tmp_path):
    from scripts.sprt_match import save_pgn

    target = tmp_path / "games.pgn"
    save_pgn(target, "")
    assert not target.exists()
