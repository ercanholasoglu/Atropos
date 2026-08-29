"""Fit the whole ladder at once, from every game played at 0.1s per move.

    python -m scripts.rating_fit

Only 0.1s pairings are pooled. The calibration gauntlets ran at 0.3s, and an
engine's rating is not the same number at two time controls — mixing them
would produce a scale that describes neither.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

from elo.joint import Pairing, components, fit, one_sided_bound, separated
from engine.utils.constants import INITIAL_ELO

MOVETIME = 0.1
# Engines that exist to test one feature against its own absence. They are
# real players and belong in the fit, but they are not rungs.
NOT_RUNGS = {"L7-see", "L8-uniform", "L7-soft400", "L7-nodes5000"}


def collect(movetime: float = MOVETIME) -> list[Pairing]:
    """Every head-to-head record at this time control.

    Where a pairing was played both sequentially and at fixed length, only the
    fixed-length record is used. A sequential run stops on a favourable swing,
    so its games are not a fair sample of the matchup — pooling them with an
    unbiased set would carry the bias into the fit rather than cancel it. See
    ``docs/SPRT_BIAS.md``.
    """
    found: list[Pairing] = []
    superseded: set[tuple[str, str]] = set()
    for path in sorted(glob.glob("data/fixed_*.json")):
        d = json.load(open(path))
        if d.get("movetime") != movetime or "a" not in d:
            continue
        superseded.add((d["a"], d["b"]))
        found.append(Pairing(d["a"], d["b"], d["wins"], d["draws"], d["losses"], Path(path).name))
    for path in sorted(glob.glob("data/sprt_*.json")):
        d = json.load(open(path))
        if d.get("movetime") != movetime or "a" not in d:
            continue
        # The sequential SEE run and its fixed-length replication are the same
        # pairing; only the fixed one is pooled, because a run stopped by a
        # sequential rule is biased away from zero.
        if path.endswith("sprt_L7-see_vs_L7.json"):
            continue
        if (d["a"], d["b"]) in superseded:
            continue
        found.append(Pairing(d["a"], d["b"], d["wins"], d["draws"], d["losses"], Path(path).name))
    for path in sorted(glob.glob("data/anchor_sf-d*.json")):
        d = json.load(open(path))
        if d.get("movetime") != movetime:
            continue
        found.append(
            Pairing(
                f"sf-d{d['depth']}",
                f"L{d['level']}",
                d["wins"],
                d["draws"],
                d["losses"],
                Path(path).name,
            )
        )
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gauge", default="L7")
    parser.add_argument(
        "--draw-elo",
        type=float,
        default=None,
        help="fix the draw parameter; default is to fit it from the games",
    )
    parser.add_argument("--out", default="data/rating_fit.json")
    args = parser.parse_args()

    pairings = collect()
    print(
        f"{len(pairings)} pairings at {MOVETIME}s per move, "
        f"{sum(p.games for p in pairings)} games\n"
    )

    bad = separated(pairings)
    groups = components(pairings)
    main_group = next(g for g in groups if args.gauge in g)
    usable = [p for p in pairings if p.a in main_group and p.b in main_group and p not in bad]

    result = fit(usable, gauge=args.gauge, draw_elo=args.draw_elo)

    # One shared draw parameter is the model's weakest assumption here, and
    # whether it holds is visible without any fitting.
    rates = sorted(usable, key=lambda p: p.draws / p.games)
    lowest, highest = rates[0], rates[-1]
    spread = highest.draws / highest.games - lowest.draws / lowest.games
    print(
        f"draw parameter: {result.draw_elo:.0f} Elo"
        f"{' (fixed)' if args.draw_elo is not None else ' (fitted)'}"
    )
    print(
        f"draw rates in this pool run {lowest.draws / lowest.games:.0%} to "
        f"{highest.draws / highest.games:.0%}  ({lowest.a} vs {lowest.b} .. "
        f"{highest.a} vs {highest.b})"
    )
    if spread > 0.35:
        print(
            "  ^ one shared draw parameter does not describe a spread that wide;\n"
            "    treat any gap whose interval depends on it as unresolved."
        )
    print()

    print(f"{'engine':<14} {'measured':>10} {'+/-':>6}  {'nominal':>8}  {'label error':>12}")
    print("-" * 58)
    rungs = sorted(
        (n for n in result.ratings if n.startswith("L") and n not in NOT_RUNGS),
        key=lambda n: int(n[1:]),
    )
    anchor_nominal = INITIAL_ELO[int(args.gauge[1:])]
    rows = []
    for name in rungs:
        level = int(name[1:])
        measured = result.ratings[name] + anchor_nominal
        nominal = INITIAL_ELO[level]
        rows.append((name, level, result.ratings[name], result.stderr[name], measured, nominal))
        print(
            f"{name:<14} {measured:>10.0f} {result.stderr[name]:>6.0f}  "
            f"{nominal:>8}  {measured - nominal:>+12.0f}"
        )

    others = [n for n in result.ratings if n not in rungs]
    if others:
        print()
        for name in sorted(others):
            print(
                f"{name:<14} {result.ratings[name] + anchor_nominal:>10.0f} "
                f"{result.stderr[name]:>6.0f}  {'—':>8}  {'—':>12}"
            )

    print(f"\nrung-to-rung gaps (nominal is 300 for every one):")
    print(f"{'gap':<12} {'measured':>10} {'95% interval':>20}")
    print("-" * 44)
    gaps = []
    for lo, hi in zip(rungs, rungs[1:]):
        est, l, h = result.gap(hi, lo)
        gaps.append((lo, hi, est, l, h))
        flag = "" if l <= 300 <= h else "   <- 300 outside"
        print(f"{lo}->{hi:<7} {est:>10.0f}   [{l:>+6.0f}, {h:>+6.0f}]{flag}")

    if bad:
        print("\nlinks the data bounds on one side only:")
        for p in bad:
            side = "wins" if p.losses == 0 else "losses"
            bound = one_sided_bound(max(p.wins, p.losses), p.games)
            direction = "+" if p.losses == 0 else "-"
            print(
                f"  {p.a} vs {p.b}: {p.wins}-{p.draws}-{p.losses} — all {side}. "
                f"Gap is {direction}{bound:.0f} Elo or more; no upper bound."
            )
        excluded = sorted(set().union(*(g for g in groups if args.gauge not in g)) or set())
        if excluded:
            print(f"  so {', '.join(excluded)} are not on this scale at all.")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(
            {
                "movetime": MOVETIME,
                "gauge": args.gauge,
                "gauge_nominal": anchor_nominal,
                "draw_elo": args.draw_elo,
                "log_likelihood": result.log_likelihood,
                "games": sum(p.games for p in usable),
                "ratings": {
                    n: {
                        "relative_to_gauge": result.ratings[n],
                        "stderr": result.stderr[n],
                    }
                    for n in result.ratings
                },
                "gaps": [
                    {"from": lo, "to": hi, "elo": e, "interval": [l, h]} for lo, hi, e, l, h in gaps
                ],
                "one_sided": [
                    {
                        "a": p.a,
                        "b": p.b,
                        "wins": p.wins,
                        "draws": p.draws,
                        "losses": p.losses,
                        "bound": one_sided_bound(max(p.wins, p.losses), p.games),
                    }
                    for p in bad
                ],
            },
            indent=1,
        )
    )
    print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
