"""How much does this project's own stopping rule overstate an effect?

A sequential test stops the moment the evidence crosses a boundary. Crossing
happens on a favourable run of results, so the estimate at the stopping point
is not the estimate the same games would have produced had they all been
played. That is a known property of sequential testing and it is not a bug —
but every "Elo" this project quoted from an SPRT carries it, and the size was
never measured.

This measures it, exactly, by running the *actual* stopping rule against
simulated matches whose true difference is known. No engine games are needed:
the question is about the rule, not about chess.

The design is fixed here before running:

* **True differences** 0 to 200 Elo in steps, covering every ladder rung
  pairing and every evaluation A/B this project ran.
* **The rule as used**: ``elo0=0, elo1=100, alpha=beta=0.05, max_games=600``,
  the configuration in every `sprt_match` and `ladder_sprt` invocation.
* **Draws modelled** with the same Rao-Kupper form the test itself assumes,
  at the pool's fitted 188 Elo (`docs/RATING_FIT.md`) rather than the 250
  default, so the simulation matches the games rather than the config.
* **Batched stopping too.** Real runs played `workers` games per batch and
  could overshoot the boundary by up to `workers - 1`. Both exact and
  batched-by-6 are reported, because the difference between them is a
  property of how the runs were driven rather than of the test.

**What would count as showing bias:** the mean estimate among runs that
accepted H1, minus the true difference, being consistently positive by more
than the Monte Carlo error. **What would count as showing none:** that
difference straddling zero across the range.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from elo.calculator import elo_diff_from_score
from elo.sprt import Sprt, SprtConfig, Verdict

SCALE = 400.0 / math.log(10.0)
DRAW_ELO = 188.0
TRUE_ELOS = (0.0, 25.0, 50.0, 75.0, 100.0, 150.0, 200.0)


def outcome(diff: float, draw_elo: float, rng: random.Random) -> float:
    """One game's score for the stronger side, under the model the test assumes."""
    pw = 1.0 / (1.0 + math.exp(-(diff - draw_elo) / SCALE))
    pl = 1.0 / (1.0 + math.exp((diff + draw_elo) / SCALE))
    r = rng.random()
    if r < pw:
        return 1.0
    if r < pw + pl:
        return 0.0
    return 0.5


def one_run(diff: float, config: SprtConfig, batch: int, rng: random.Random) -> dict:
    """Play until the rule stops, then report what the rule would have said."""
    test = Sprt(config)
    while not test.finished:
        for _ in range(batch):
            test.record(outcome(diff, DRAW_ELO, rng))
            if batch == 1 and test.finished:
                break
    return {
        "games": test.games,
        "estimate": elo_diff_from_score(test.score) if test.games else 0.0,
        "verdict": test.verdict.value,
        "accepted_h1": test.verdict is Verdict.ACCEPT_H1,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=4000)
    parser.add_argument("--batch", type=int, default=6, help="games per batch, as run")
    parser.add_argument("--out", default="data/sprt_bias.json")
    args = parser.parse_args()

    config = SprtConfig(elo0=0.0, elo1=100.0, max_games=600, initial_draw_elo=DRAW_ELO)
    rows = []
    print(f"{args.trials} simulated matches per point, draw_elo {DRAW_ELO:.0f}\n")
    print(
        f"{'true':>6} {'batch':>6} {'P(accept H1)':>13} {'games':>7} "
        f"{'estimate|H1':>12} {'bias':>8} {'+/-':>6}"
    )
    print("-" * 66)

    for batch in (1, args.batch):
        for true in TRUE_ELOS:
            rng = random.Random(hash((true, batch)) & 0xFFFF)
            runs = [one_run(true, config, batch, rng) for _ in range(args.trials)]
            accepted = [r for r in runs if r["accepted_h1"]]
            share = len(accepted) / len(runs)
            mean_games = sum(r["games"] for r in runs) / len(runs)
            if accepted:
                est = sum(r["estimate"] for r in accepted) / len(accepted)
                var = sum((r["estimate"] - est) ** 2 for r in accepted) / max(len(accepted) - 1, 1)
                se = math.sqrt(var / len(accepted))
                bias = est - true
            else:
                est = bias = float("nan")
                se = float("nan")
            rows.append(
                {
                    "true_elo": true,
                    "batch": batch,
                    "p_accept_h1": share,
                    "mean_games": mean_games,
                    "estimate_given_h1": est,
                    "bias": bias,
                    "monte_carlo_se": se,
                }
            )
            print(
                f"{true:>6.0f} {batch:>6} {share:>13.1%} {mean_games:>7.0f} "
                f"{est:>12.0f} {bias:>+8.0f} {se:>6.1f}"
            )
        print()

    Path(args.out).write_text(
        json.dumps(
            {
                "trials": args.trials,
                "draw_elo": DRAW_ELO,
                "config": {"elo0": 0.0, "elo1": 100.0, "max_games": 600},
                "rows": rows,
            },
            indent=1,
        )
    )
    print(f"written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
