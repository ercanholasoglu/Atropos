import itertools

import pytest

from elo.database import EloDatabase
from elo.tracker import EloTracker
from engine.levels import Level1Random, create_engine
from tournament.base import Standing, Tournament, TournamentResult
from tournament.gauntlet import GauntletTournament
from tournament.openings import book
from tournament.round_robin import RoundRobinTournament
from tournament.swiss import SwissTournament

SHORT = dict(openings=book(2), max_plies=30)


def randoms(count: int) -> list[Level1Random]:
    """Cheap, distinguishable engines — the games themselves do not matter."""
    engines = []
    for index in range(count):
        engine = Level1Random(seed=index)
        engine.name = f"R{index}"
        engines.append(engine)
    return engines


# --- standings ------------------------------------------------------------


def test_standing_counts_results():
    standing = Standing(name="A", level=1)
    standing.record(1.0)
    standing.record(0.5)
    standing.record(0.0)
    assert (standing.wins, standing.draws, standing.losses) == (1, 1, 1)
    assert standing.points == 1.5
    assert standing.score_pct == 0.5


def test_a_bye_is_a_point_but_not_a_win():
    standing = Standing(name="A", level=1)
    standing.record_bye()
    assert standing.points == 1.0
    assert standing.wins == 0 and standing.played == 1


def test_score_pct_of_an_unplayed_engine_is_zero():
    assert Standing(name="A", level=1).score_pct == 0.0


def test_elo_change_is_the_difference():
    standing = Standing(name="A", level=1, elo_before=1500, elo_after=1530)
    assert standing.elo_change == 30


# --- shared behaviour -----------------------------------------------------


def test_a_tournament_needs_two_engines():
    with pytest.raises(ValueError):
        RoundRobinTournament(randoms(1))


def test_tournament_is_abstract():
    with pytest.raises(TypeError):
        Tournament(randoms(2))  # type: ignore[abstract]


def test_progress_hook_sees_every_game_with_a_running_count():
    seen = []
    tournament = RoundRobinTournament(
        randoms(3),
        games_per_pair=2,
        on_game=lambda done, total, rec: seen.append((done, total)),
        **SHORT,
    )
    tournament.run()
    assert seen == [(i, 6) for i in range(1, 7)]


def test_result_table_renders():
    result = RoundRobinTournament(randoms(2), games_per_pair=2, **SHORT).run()
    table = result.table()
    assert "engine" in table and "R0" in table and "R1" in table


def test_empty_result_table_does_not_crash():
    assert "engine" in TournamentResult(format="x").table()


# --- round robin ----------------------------------------------------------


@pytest.mark.parametrize("count,per_pair", [(2, 2), (3, 2), (4, 1), (5, 4)])
def test_round_robin_schedules_every_pair(count, per_pair):
    engines = randoms(count)
    tournament = RoundRobinTournament(engines, games_per_pair=per_pair, **SHORT)
    pairings = tournament.generate_pairings()

    assert len(pairings) == tournament.total_games == count * (count - 1) // 2 * per_pair
    met = {frozenset({p.white.name, p.black.name}) for p in pairings}
    assert met == {frozenset({a.name, b.name}) for a, b in itertools.combinations(engines, 2)}


def test_round_robin_alternates_colours_within_a_pair():
    pairings = RoundRobinTournament(randoms(2), games_per_pair=4, **SHORT).generate_pairings()
    whites = [p.white.name for p in pairings]
    assert whites == ["R0", "R1", "R0", "R1"]


def test_round_robin_rejects_a_zero_game_schedule():
    with pytest.raises(ValueError):
        RoundRobinTournament(randoms(3), games_per_pair=0)


def test_round_robin_totals_add_up():
    result = RoundRobinTournament(randoms(4), games_per_pair=2, **SHORT).run()
    assert result.played == 12
    assert sum(s.played for s in result.standings) == 24  # two engines per game
    assert sum(s.points for s in result.standings) == pytest.approx(12.0)


def test_standings_come_back_sorted():
    result = RoundRobinTournament(
        [create_engine(2, seed=1), create_engine(1, seed=2)],
        games_per_pair=4,
        openings=book(2),
        max_plies=120,
    ).run()
    assert result.standings[0].name == "L2-Material"
    assert result.standings[0].points >= result.standings[1].points


# --- gauntlet -------------------------------------------------------------


def test_gauntlet_only_schedules_the_test_engine():
    test_engine, *opponents = randoms(4)
    tournament = GauntletTournament(test_engine, opponents, games_per_opponent=2, **SHORT)
    pairings = tournament.generate_pairings()

    assert len(pairings) == 6
    assert all(test_engine.name in (p.white.name, p.black.name) for p in pairings)
    # Opponents never meet each other.
    assert not any(
        p.white.name != test_engine.name and p.black.name != test_engine.name for p in pairings
    )


def test_gauntlet_alternates_colours_per_opponent():
    test_engine, *opponents = randoms(3)
    pairings = GauntletTournament(
        test_engine, opponents, games_per_opponent=2, **SHORT
    ).generate_pairings()
    assert pairings[0].white.name == test_engine.name
    assert pairings[1].black.name == test_engine.name


def test_gauntlet_needs_opponents_and_games():
    with pytest.raises(ValueError):
        GauntletTournament(randoms(1)[0], [])
    with pytest.raises(ValueError):
        GauntletTournament(randoms(1)[0], randoms(2), games_per_opponent=0)


def test_gauntlet_rating_estimate_tracks_the_score():
    """A clean sweep of the ladder should be rated above the ladder."""
    test_engine = create_engine(4, seed=1)
    opponents = [create_engine(1, seed=2), create_engine(2, seed=3)]
    tournament = GauntletTournament(
        test_engine, opponents, games_per_opponent=2, openings=book(2), max_plies=120
    )
    result = tournament.run()
    estimate = tournament.estimate_rating(result)
    assert estimate > max(o.elo for o in opponents)


# --- swiss ----------------------------------------------------------------


def test_swiss_plays_the_rounds_it_promised():
    tournament = SwissTournament(randoms(4), rounds=3, **SHORT)
    assert tournament.total_games == 6
    result = tournament.run()
    assert result.played == 6
    assert result.rounds == 3


def test_swiss_avoids_rematches_while_it_can():
    """Four engines over three rounds is exactly one full round-robin."""
    tournament = SwissTournament(randoms(4), rounds=3, **SHORT)
    result = tournament.run()
    pairs = [frozenset({g.white, g.black}) for g in result.games]
    assert len(set(pairs)) == len(pairs) == 6


def test_swiss_gives_an_odd_field_a_bye_each_round():
    tournament = SwissTournament(randoms(5), rounds=2, **SHORT)
    assert tournament.total_games == 4
    result = tournament.run()
    assert result.played == 4
    assert sum(s.byes for s in result.standings) == 2
    # Nobody sits out twice while others have not sat out at all.
    assert all(s.byes <= 1 for s in result.standings)


def test_swiss_balances_colours():
    """No engine may drift more than one game of White ahead of its Blacks.

    Two is the limit Swiss rules tolerate; one is what the balance-plus-
    alternation rule should actually deliver on an even field.
    """
    tournament = SwissTournament(randoms(4), rounds=4, **SHORT)
    result = tournament.run()
    balance = {name: 0 for name in tournament.standings}
    for record in result.games:
        balance[record.white] += 1
        balance[record.black] -= 1
    assert all(abs(value) <= 1 for value in balance.values()), balance


def test_swiss_needs_at_least_one_round():
    with pytest.raises(ValueError):
        SwissTournament(randoms(4), rounds=0)


def test_swiss_pairs_the_leaders_together():
    """After a round, the winners should meet each other, not the losers."""
    tournament = SwissTournament(randoms(4), rounds=2, **SHORT)
    rounds = tournament.rounds_of_pairings()
    first = next(rounds)
    for pairing in first:
        tournament.standings[pairing.white.name].record(1.0)
        tournament.standings[pairing.black.name].record(0.0)
    winners = {p.white.name for p in first}

    second = next(rounds)
    top_pairing = second[0]
    assert {top_pairing.white.name, top_pairing.black.name} == winners


# --- rating integration ---------------------------------------------------


def test_a_tournament_feeds_the_rating_tracker():
    db = EloDatabase(":memory:")
    tracker = EloTracker(db)
    engines = [create_engine(2, seed=1), create_engine(1, seed=2)]

    result = RoundRobinTournament(
        engines, games_per_pair=4, tracker=tracker, openings=book(2), max_plies=120
    ).run()

    assert db.game_count() == result.played
    assert db.get_rating("L2-Material") > db.get_rating("L1-Random")
    # The table's Elo column and the database agree.
    for standing in result.standings:
        assert standing.elo_after == pytest.approx(db.get_rating(standing.name))
    assert any(s.elo_change != 0 for s in result.standings)
    db.close()


def test_engines_carry_their_new_rating_out_of_the_tournament():
    db = EloDatabase(":memory:")
    tracker = EloTracker(db)
    stronger, weaker = create_engine(2, seed=1), create_engine(1, seed=2)
    RoundRobinTournament(
        [stronger, weaker], games_per_pair=2, tracker=tracker, openings=book(2), max_plies=120
    ).run()
    assert stronger.elo != 600 or weaker.elo != 200
    assert stronger.games_played == 2
    db.close()
