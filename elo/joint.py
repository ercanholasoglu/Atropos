"""Fit every engine's rating at once, from every game they played.

The ladder's rungs were verified one adjacent pair at a time, which answers
"is this rung above that one" and nothing else. It leaves the scale
unconstrained in two ways: a chain of pairwise gaps accumulates the error of
every link, and it ignores measurements that connect rungs *without* being
adjacent — an outside engine that played both Level 6 and Level 7 says
something about the gap between them that neither ladder match does.

This fits all of it simultaneously. One rating per engine, one shared draw
parameter, maximum likelihood over every recorded game.

**The model.** Rao-Kupper, the same three-outcome model `elo.sprt` uses:
with rating difference ``d`` and draw parameter ``delta``,

    P(win)  = 1 / (1 + 10 ** (-(d - delta) / 400))
    P(loss) = 1 / (1 + 10 ** ( (d + delta) / 400))
    P(draw) = 1 - P(win) - P(loss)

**The gauge.** Ratings are differences; the likelihood is unchanged if every
rating shifts by the same amount. One engine is therefore held at zero and
everything is reported relative to it. Which one is a presentation choice and
changes no gap.

**What it cannot do.** A pairing with no losses and no draws pushes its gap to
infinity, and no amount of fitting rescues that — 7-0-0 is consistent with
"better by 200" and with "better by 2000". Such a link is reported as a
one-sided bound and the engines it isolates are fit separately, rather than
being given a number the data does not contain.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

SCALE = 400.0 / math.log(10.0)  # convert Elo to natural-log units


@dataclass(frozen=True)
class Pairing:
    """One head-to-head record: ``a`` scored these results against ``b``."""

    a: str
    b: str
    wins: int
    draws: int
    losses: int
    source: str = ""

    @property
    def games(self) -> int:
        return self.wins + self.draws + self.losses


@dataclass
class JointFit:
    """Ratings relative to ``gauge``, with standard errors."""

    ratings: dict[str, float]
    stderr: dict[str, float]
    draw_elo: float
    gauge: str
    log_likelihood: float
    pairings: list[Pairing] = field(default_factory=list)

    def interval(self, name: str, z: float = 1.96) -> tuple[float, float]:
        r, s = self.ratings[name], self.stderr[name]
        return (r - z * s, r + z * s)

    def gap(self, high: str, low: str) -> tuple[float, float, float]:
        """``high - low`` with a standard error that respects their covariance.

        Returned as ``(estimate, lower, upper)``. The covariance term is not
        available from diagonal errors alone, so this is the conservative
        version: errors added in quadrature, which overstates the width when
        the two ratings are positively correlated — as adjacent rungs are.
        """
        d = self.ratings[high] - self.ratings[low]
        s = math.hypot(self.stderr[high], self.stderr[low])
        return d, d - 1.96 * s, d + 1.96 * s


def _probs(diff: np.ndarray, delta: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Win, draw and loss probabilities for the side with the ``diff`` advantage."""
    pw = 1.0 / (1.0 + np.exp(-(diff - delta) / SCALE))
    pl = 1.0 / (1.0 + np.exp((diff + delta) / SCALE))
    pd = np.clip(1.0 - pw - pl, 1e-12, 1.0)
    return np.clip(pw, 1e-12, 1.0), pd, np.clip(pl, 1e-12, 1.0)


def separated(pairings: list[Pairing]) -> list[Pairing]:
    """Pairings whose gap the data bounds on one side only.

    A clean sweep — no losses and no draws, or no wins and no draws — has its
    maximum likelihood at infinity. Nothing downstream can fix that, so these
    are found before fitting rather than discovered as a diverging optimiser.
    """
    return [p for p in pairings if (p.draws == 0 and (p.losses == 0 or p.wins == 0))]


def one_sided_bound(wins: int, games: int, confidence: float = 0.95) -> float:
    """Lower bound on the Elo gap implied by a clean sweep.

    The largest gap ``g`` for which observing this many wins still has
    probability at least ``1 - confidence``; below it the sweep would be
    surprising. Solved directly because a sweep of ``n`` games has likelihood
    ``p ** n``.
    """
    if wins != games or games == 0:
        raise ValueError("only defined for a clean sweep")
    p = (1.0 - confidence) ** (1.0 / games)
    return -SCALE * math.log(1.0 / p - 1.0)


def components(pairings: list[Pairing]) -> list[set[str]]:
    """Connected groups of engines, ignoring links that are separated."""
    usable = [p for p in pairings if p not in separated(pairings)]
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for p in pairings:
        find(p.a), find(p.b)
    for p in usable:
        ra, rb = find(p.a), find(p.b)
        if ra != rb:
            parent[ra] = rb

    groups: dict[str, set[str]] = {}
    for name in list(parent):
        groups.setdefault(find(name), set()).add(name)
    return sorted(groups.values(), key=len, reverse=True)


def fit(
    pairings: list[Pairing],
    gauge: str | None = None,
    draw_elo: float | None = None,
    iterations: int = 200,
) -> JointFit:
    """Maximum-likelihood ratings for every engine in ``pairings``.

    ``draw_elo`` fixes the draw parameter instead of fitting it, which is what
    a set of pairings with very few draws needs — the drawishness of the pool
    is then an assumption rather than a number invented from three drawn games.
    """
    names = sorted({n for p in pairings for n in (p.a, p.b)})
    if gauge is None:
        gauge = max(names, key=lambda n: sum(p.games for p in pairings if n in (p.a, p.b)))
    if gauge not in names:
        raise ValueError(f"gauge {gauge!r} played no games in this set")

    index = {n: i for i, n in enumerate(names)}
    ia = np.array([index[p.a] for p in pairings])
    ib = np.array([index[p.b] for p in pairings])
    w = np.array([p.wins for p in pairings], dtype=float)
    d = np.array([p.draws for p in pairings], dtype=float)
    ll = np.array([p.losses for p in pairings], dtype=float)

    fit_draw = draw_elo is None
    n = len(names)
    theta = np.zeros(n + 1)
    theta[n] = 250.0 if draw_elo is None else float(draw_elo)

    def negative_ll(t: np.ndarray) -> float:
        pw, pd, pl = _probs(t[ia] - t[ib], t[n])
        return -float(w @ np.log(pw) + d @ np.log(pd) + ll @ np.log(pl))

    free = [i for i in range(n) if names[i] != gauge]
    if fit_draw:
        free.append(n)
    free_idx = np.array(free)

    # Newton with a numerical Hessian. The parameter count is a dozen or so,
    # which makes finite differences cheaper to get right than hand-derived
    # second derivatives, and the objective is smooth.
    step = 1e-3
    for _ in range(iterations):
        base = negative_ll(theta)
        grad = np.zeros(len(free_idx))
        for k, i in enumerate(free_idx):
            t = theta.copy()
            t[i] += step
            up = negative_ll(t)
            t[i] -= 2 * step
            grad[k] = (up - negative_ll(t)) / (2 * step)

        hess = np.zeros((len(free_idx), len(free_idx)))
        for k, i in enumerate(free_idx):
            for m, j in enumerate(free_idx):
                if m < k:
                    continue
                t = theta.copy()
                t[i] += step
                t[j] += step
                pp = negative_ll(t)
                t[j] -= 2 * step
                pm = negative_ll(t)
                t[i] -= 2 * step
                mm = negative_ll(t)
                t[j] += 2 * step
                mp = negative_ll(t)
                hess[k, m] = hess[m, k] = (pp - pm - mp + mm) / (4 * step * step)

        try:
            delta = np.linalg.solve(hess + np.eye(len(free_idx)) * 1e-6, grad)
        except np.linalg.LinAlgError:  # pragma: no cover - singular is a data problem
            break

        # Damped, because a Newton step from a poor start can overshoot into a
        # region where the likelihood is worse.
        scale = 1.0
        for _ in range(30):
            trial = theta.copy()
            trial[free_idx] -= scale * delta
            if negative_ll(trial) <= base:
                theta = trial
                break
            scale /= 2
        else:
            break
        if np.max(np.abs(scale * delta)) < 1e-6:
            break

    covariance = np.linalg.inv(hess + np.eye(len(free_idx)) * 1e-9)
    errors = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
    stderr = {gauge: 0.0}
    for k, i in enumerate(free_idx):
        if i < n:
            stderr[names[i]] = float(errors[k])

    return JointFit(
        ratings={names[i]: float(theta[i] - theta[index[gauge]]) for i in range(n)},
        stderr=stderr,
        draw_elo=float(theta[n]),
        gauge=gauge,
        log_likelihood=-negative_ll(theta),
        pairings=list(pairings),
    )
