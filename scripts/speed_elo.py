"""How much strength is a doubling of speed worth?

Every optimisation in this project was reported in nps, and nps is not the
unit anyone cares about. This converts one to the other: play the engine
against a deliberately slowed copy of itself and read off the Elo cost of
each halving.

Everything below the line was fixed before the first game was played. It is
recorded here rather than in a commit message because a bracket chosen after
seeing the numbers is not a bracket.

--- pre-registered ------------------------------------------------------

**Engine.** Level 7 on both sides. It is the strongest verified rung, it is
the one the Stockfish anchor was measured against, and — unlike Level 8 — it
has no adaptive clock, so a node budget does not silently disable a feature
that a time budget leaves running.

**Reference budget.** B = 5000 nodes per move. At the 53,758 nps measured
after the rook term shipped that is ~0.09 s per move, which is the operating
point every other match in this project used. Holding the operating point
fixed is the only reason the resulting slope can be quoted next to the other
results.

**Slowdowns.** B/2, B/4, B/8, B/16 — four halvings, each played against the
full-speed reference. Halvings rather than an even spread of nps because the
question is "Elo per doubling", and a doubling is the unit the answer is
asked in. Four of them because the span has to be wide enough to see
curvature if there is any: a straight line through two points is not
evidence of linearity.

**Predicted effects, stated before the run.** Published self-play doubling
curves for classical engines sit near 50-70 Elo per doubling and flatten at
long time controls. This engine is at the short end, so:

    B/2   about  -60 Elo
    B/4   about -120
    B/8   about -180
    B/16  about -240

**Games per pairing.** 240, fixed, no sequential stopping. The deliverable
is a *slope*, and a test that stops as soon as it can reject zero returns an
estimate biased away from zero — fine for a decision, wrong for a curve.
240 games buys roughly +/-45 Elo at 95%, which resolves every effect
predicted above and is the reason the predictions are written down: if a
measurement lands outside its predicted interval, the prediction was wrong
and that is the finding.

**Falsifiable claim.** Elo is linear in log2(budget) across this span, with
one slope. Curvature large enough to see at +/-45 Elo per point refutes it.

**Cross-check, and why it is not a formality.** The same halvings are also
run as *movetime* divisions (B/2 and B/8 only, to keep the cost down). Node
budget and clock are meant to be two spellings of the same slowdown. They
are not exactly: the node limit is tested at every node, the clock only
every 2048, so a 5000-node search can overshoot its deadline by up to 40%
while a node budget cannot overshoot at all. Prediction: the movetime arm
comes out slightly *stronger* and noticeably noisier than the node arm at
the same nominal division. If it comes out weaker, or if the gap is larger
than the granularity can explain, the two methods are not measuring the same
thing and the node figures are the ones to trust — they are the reproducible
ones.

*Refinement, added before any game was played and derived from the source
rather than from a result:* the granularity is not a small correction at the
far end. `SearchStats.check_interval` is 2048, so inside an iteration the
clock cannot stop a search before its 2048th node. At the 53,758 nps above, a
B/8 movetime budget is 0.011 s, or roughly 600 nodes — under a single check
interval. Between iterations `out_of_time()` reads the clock directly, so
iterative deepening still stops early, and the real floor is therefore set by
how far one iteration runs, not by the deadline. The sharpened prediction: the
movetime arm tracks the node arm at B/2 and pulls clearly above it at B/8,
because at B/8 the budget has fallen below the resolution of the instrument
enforcing it.

-------------------------------------------------------------------------

    python -m scripts.speed_elo --workers 6
    python -m scripts.speed_elo --arm movetime --workers 6
"""

from __future__ import annotations

import argparse
import json
import math
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from elo.calculator import elo_diff_from_score
from engine.base_engine import BaseEngine
from engine.levels import create_engine
from scripts.telemetry import TelemetryRecorder
from tournament.match import play_game
from tournament.openings import OPENING_BOOK

LEVEL = 7
BASE_NODES = 5000
BASE_MOVETIME = 0.09
DIVISORS_NODES = (2, 4, 8, 16)
DIVISORS_MOVETIME = (2, 8)
GAMES_PER_PAIRING = 240
PREDICTED = {2: -60.0, 4: -120.0, 8: -180.0, 16: -240.0}


def build(arm: str, divisor: int, seed: int) -> BaseEngine:
    """Level 7 slowed by ``divisor``, by one method or the other.

    The unused budget is left at ``None`` on purpose. Setting both would make
    whichever bound happened to bind first the real experiment, and which one
    that is would change with machine load.
    """
    if arm == "nodes":
        engine = create_engine(LEVEL, seed=seed, time_limit=None)
        engine.node_limit = BASE_NODES // divisor
    else:
        engine = create_engine(LEVEL, seed=seed, time_limit=BASE_MOVETIME / divisor)
    engine.name = f"L{LEVEL}-{arm}-div{divisor}"
    return engine


def play_one(job: tuple[str, int, int, int]) -> tuple[float, int]:
    """One game, scored for the *full-speed* side. Module level so it pickles."""
    arm, divisor, index, max_plies = job

    opening = OPENING_BOOK[(index // 2) % len(OPENING_BOOK)]
    fast_is_white = index % 2 == 0
    fast = build(arm, 1, seed=1000 + index)
    slow = build(arm, divisor, seed=2000 + index)
    white, black = (fast, slow) if fast_is_white else (slow, fast)

    record = play_game(
        white, black, start_fen=opening.fen, max_plies=max_plies, opening=opening.name
    )
    white_score = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}[record.result]
    return (white_score if fast_is_white else 1 - white_score), record.nodes


def interval(score: float, games: int) -> tuple[float, float]:
    """95% interval on the Elo difference, from the interval on the score.

    Normal approximation on the score and then through the same inverse the
    point estimate uses, so the ends are on the same scale as the middle.
    """
    if games == 0:
        return (float("-inf"), float("inf"))
    se = math.sqrt(max(score * (1 - score), 1e-9) / games)
    lo = min(max(score - 1.96 * se, 1e-6), 1 - 1e-6)
    hi = min(max(score + 1.96 * se, 1e-6), 1 - 1e-6)
    return elo_diff_from_score(lo), elo_diff_from_score(hi)


def run_pairing(arm: str, divisor: int, args, recorder: TelemetryRecorder) -> dict:
    jobs = [(arm, divisor, i, args.max_plies) for i in range(args.games)]
    total = 0.0
    played = 0
    print(f"full speed vs 1/{divisor} ({arm})", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for score, nodes in pool.map(play_one, jobs):
            total += score
            played += 1
            recorder.add_games(1)
            recorder.add_nodes(nodes)
            if played % 40 == 0:
                lo, hi = interval(total / played, played)
                print(
                    f"  {played:4d} games  {total / played:6.1%}  "
                    f"{elo_diff_from_score(total / played):+7.1f} Elo  [{lo:+.0f}, {hi:+.0f}]",
                    flush=True,
                )

    score = total / played
    lo, hi = interval(score, played)
    # Reported from the slowed engine's side: the question is what slowing it
    # down cost, so the sign should be negative when it lost.
    return {
        "arm": arm,
        "divisor": divisor,
        "doublings": math.log2(divisor),
        "games": played,
        "score_for_full_speed": score,
        "elo_for_slowed": -elo_diff_from_score(score),
        "interval_for_slowed": [-hi, -lo],
        "predicted_elo_for_slowed": PREDICTED[divisor],
        "budget_nodes": BASE_NODES // divisor if arm == "nodes" else None,
        "budget_seconds": None if arm == "nodes" else BASE_MOVETIME / divisor,
    }


def slope(rows: list[dict]) -> dict:
    """Least squares through (doublings, Elo), forced through the origin.

    Through the origin because zero doublings is zero Elo by construction —
    the reference played against itself — and spending a degree of freedom on
    an intercept that is known would only widen the slope's interval.
    """
    xs = [r["doublings"] for r in rows]
    ys = [r["elo_for_slowed"] for r in rows]
    sxx = sum(x * x for x in xs)
    b = sum(x * y for x, y in zip(xs, ys)) / sxx if sxx else 0.0
    resid = [y - b * x for x, y in zip(xs, ys)]
    dof = max(len(xs) - 1, 1)
    se = math.sqrt(sum(r * r for r in resid) / dof / sxx) if sxx else float("inf")
    return {
        "elo_per_doubling": b,
        "standard_error": se,
        "interval": [b - 1.96 * se, b + 1.96 * se],
        "residuals": resid,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("nodes", "movetime"), default="nodes")
    parser.add_argument("--games", type=int, default=GAMES_PER_PAIRING)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--max-plies", type=int, default=200)
    args = parser.parse_args()

    divisors = DIVISORS_NODES if args.arm == "nodes" else DIVISORS_MOVETIME
    out = Path(f"data/speed_elo_{args.arm}.json")

    with TelemetryRecorder(
        "speed_elo",
        {
            "arm": args.arm,
            "level": LEVEL,
            "base_nodes": BASE_NODES,
            "base_movetime": BASE_MOVETIME,
            "divisors": list(divisors),
            "games_per_pairing": args.games,
            "workers": args.workers,
            "max_plies": args.max_plies,
        },
    ) as recorder:
        rows = [run_pairing(args.arm, d, args, recorder) for d in divisors]
        fit = slope(rows)
        result = {"pairings": rows, "fit": fit}
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=1))
        recorder.snapshot(result)

    print()
    print(f"{'budget':>10}  {'games':>6}  {'measured':>18}  {'predicted':>10}")
    print("-" * 52)
    for row in rows:
        lo, hi = row["interval_for_slowed"]
        print(
            f"{'1/' + str(row['divisor']):>10}  {row['games']:6d}  "
            f"{row['elo_for_slowed']:+7.1f} [{lo:+.0f},{hi:+.0f}]  "
            f"{row['predicted_elo_for_slowed']:+10.0f}"
        )
    print("-" * 52)
    lo, hi = fit["interval"]
    print(f"slope: {fit['elo_per_doubling']:+.1f} Elo per doubling  [{lo:+.1f}, {hi:+.1f}]")
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
