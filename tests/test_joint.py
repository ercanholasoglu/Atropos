"""The joint rating fit, checked against answers known in advance."""

from __future__ import annotations

import math
import random

import pytest

from elo.joint import (
    Pairing,
    components,
    fit,
    one_sided_bound,
    separated,
)

SCALE = 400 / math.log(10)


def simulate(diff: float, draw_elo: float, games: int, rng: random.Random) -> tuple[int, int, int]:
    """Play ``games`` under the model the fit assumes."""
    pw = 1 / (1 + math.exp(-(diff - draw_elo) / SCALE))
    pl = 1 / (1 + math.exp((diff + draw_elo) / SCALE))
    w = d = ll = 0
    for _ in range(games):
        r = rng.random()
        if r < pw:
            w += 1
        elif r < pw + pl:
            ll += 1
        else:
            d += 1
    return w, d, ll


def test_recovers_a_known_scale() -> None:
    """With enough games the fit returns the ratings the data was generated from."""
    rng = random.Random(11)
    truth = {"A": 0.0, "B": -150.0, "C": -320.0}
    edges = [("A", "B"), ("B", "C"), ("A", "C")]
    pairings = [Pairing(a, b, *simulate(truth[a] - truth[b], 250.0, 4000, rng)) for a, b in edges]
    result = fit(pairings, gauge="A", draw_elo=250.0)
    for name, want in truth.items():
        assert abs(result.ratings[name] - want) < 25, f"{name}: {result.ratings[name]:.0f}"


def test_recovers_the_draw_parameter() -> None:
    """Left free, the draw parameter comes back near the one used to generate."""
    rng = random.Random(3)
    pairings = [
        Pairing("A", "B", *simulate(120.0, 180.0, 6000, rng)),
        Pairing("B", "C", *simulate(90.0, 180.0, 6000, rng)),
    ]
    result = fit(pairings, gauge="A", draw_elo=None)
    assert abs(result.draw_elo - 180.0) < 30, result.draw_elo


def test_gauge_choice_does_not_change_a_gap() -> None:
    """Ratings are differences; which engine sits at zero is presentation."""
    rng = random.Random(5)
    pairings = [
        Pairing("A", "B", *simulate(140.0, 200.0, 2000, rng)),
        Pairing("B", "C", *simulate(110.0, 200.0, 2000, rng)),
    ]
    a = fit(pairings, gauge="A", draw_elo=200.0)
    b = fit(pairings, gauge="C", draw_elo=200.0)
    assert abs(a.gap("A", "C")[0] - b.gap("A", "C")[0]) < 1.0


def test_clean_sweeps_are_flagged_not_fitted() -> None:
    """A pairing with no losses and no draws has its maximum at infinity."""
    sweep = Pairing("A", "B", 7, 0, 0)
    ordinary = Pairing("B", "C", 10, 5, 5)
    flagged = separated([sweep, ordinary])
    assert flagged == [sweep]


def test_a_sweep_disconnects_what_it_alone_links() -> None:
    """Engines reachable only through a sweep are not on the same scale."""
    groups = components(
        [Pairing("A", "B", 7, 0, 0), Pairing("B", "C", 10, 5, 5), Pairing("C", "D", 8, 4, 8)]
    )
    biggest = max(groups, key=len)
    assert biggest == {"B", "C", "D"}
    assert {"A"} in groups


def test_one_sided_bound_grows_with_the_sweep() -> None:
    """More wins in a row bound the gap further from zero."""
    assert one_sided_bound(3, 3) < one_sided_bound(7, 7) < one_sided_bound(20, 20)
    assert one_sided_bound(7, 7) > 0


def test_one_sided_bound_rejects_a_non_sweep() -> None:
    with pytest.raises(ValueError):
        one_sided_bound(6, 7)


def test_pairing_counts_its_games() -> None:
    assert Pairing("A", "B", 3, 2, 1).games == 6
