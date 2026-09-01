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


def test_measured_elo_matches_the_recorded_fit() -> None:
    """The constants and the fit output must not drift apart.

    ``MEASURED_ELO`` is a copy of what ``scripts/rating_fit.py`` produced. A
    copy that quietly stops matching its source is worse than no copy, so this
    reads the recorded run and compares.
    """
    import json
    from pathlib import Path

    from engine.utils.constants import MEASURED_ELO

    recorded = json.loads(Path("data/rating_fit.json").read_text())
    gauge_offset = recorded["gauge_nominal"]
    for level, (rating, stderr) in MEASURED_ELO.items():
        entry = recorded["ratings"].get(f"L{level}")
        assert entry is not None, f"L{level} is not in the recorded fit"
        assert abs(entry["relative_to_gauge"] + gauge_offset - rating) < 1.5, (
            f"L{level}: MEASURED_ELO says {rating}, the recorded fit says "
            f"{entry['relative_to_gauge'] + gauge_offset:.0f}. Adding games moves the "
            f"fit; re-run `python -m scripts.rating_fit` and update MEASURED_ELO."
        )
        assert abs(entry["stderr"] - stderr) < 1.5, level


def test_the_measured_scale_disagrees_with_the_nominal_one() -> None:
    """The finding itself, asserted so it cannot be quietly undone.

    If someone later edits either table into agreement, this fails and asks why
    rather than letting the ladder go back to claiming an even 300 per rung.
    """
    from engine.utils.constants import INITIAL_ELO, MEASURED_ELO

    # 400 then six 300s. This assertion caught a claim made repeatedly in the
    # documentation -- that the rungs are "300 apart" -- which is true of six
    # of the seven gaps and not of the first.
    nominal_gaps = [INITIAL_ELO[n + 1] - INITIAL_ELO[n] for n in range(1, 8)]
    assert nominal_gaps == [400, 300, 300, 300, 300, 300, 300]

    measured_gaps = [MEASURED_ELO[n + 1][0] - MEASURED_ELO[n][0] for n in range(1, 8)]
    assert measured_gaps != nominal_gaps
    # The top two transitions are the ones that are not there at all.
    assert measured_gaps[5] < 100, "L6->L7 was measured at about +19"
    assert measured_gaps[6] < 0, "L7->L8 was measured slightly negative"
