"""Bit width -> collision -> Elo, part (b) of `docs/ZOBRIST_PREREG.md`.

Reads the four fixed-length matches against the full key and fits each with
the Rao-Kupper three-outcome model, because these pairings draw 25-37% and a
score-only conversion compresses the number it reports. See `docs/RATING_FIT.md`.
"""

from __future__ import annotations

import json
from pathlib import Path

from elo.calculator import elo_diff_from_score
from elo.joint import Pairing, fit

WIDTHS = (16, 24, 32, 48)
# Fixed in the pre-registration, before any game was played.
REGISTERED = {16: "<= -200", 24: "-30 to -150", 32: "-20 to +10", 48: "-10 to +10"}
# Fixed in `docs/ZOBRIST.md` after part (a), still before any game.
DETERMINISTIC = {16: "clearly worse", 24: "0 at 400 games", 32: "exactly 0", 48: "exactly 0"}


def main() -> int:
    collisions = json.load(open("data/zobrist/d5_1.json"))
    per_width = {r["width"]: r for r in collisions["rows"]}
    distinct = collisions["distinct"]

    print(f"collision counts from perft(5), {distinct:,} distinct positions\n")
    print(
        f"{'width':>6} {'collisions':>12} {'per million':>12} {'games':>7} "
        f"{'W-D-L':>15} {'Elo':>8} {'95% interval':>18} {'registered':>13} {'deterministic':>15}"
    )
    print("-" * 122)
    records = {w: json.load(open(f"data/fixed_L7-key{w}_vs_L7.json")) for w in WIDTHS}

    # The draw parameter is fitted per arm where the arm has draws to fit it
    # from. The 16-bit arm draws 7 games in 402 and drives it to -2397, which
    # is not a drawishness estimate but a singular Hessian; that arm gets the
    # value the others agree on, and the report says so.
    free = {}
    for w in WIDTHS:
        d = records[w]
        if d["draws"] / d["games"] > 0.1:
            free[w] = fit(
                [Pairing(d["a"], d["b"], d["wins"], d["draws"], d["losses"], "x")], gauge="L7"
            ).draw_elo
    pooled = sum(free.values()) / len(free)
    print(f"draw parameter fitted per arm: {', '.join(f'{w}b {v:.0f}' for w, v in free.items())}")
    print(f"pooled {pooled:.0f}, used fixed for any arm too decisive to fit its own\n")

    rows = []
    for w in WIDTHS:
        d = records[w]
        p = Pairing(d["a"], d["b"], d["wins"], d["draws"], d["losses"], f"key{w}")
        fixed = w not in free
        result = fit([p], gauge="L7", draw_elo=pooled if fixed else None)
        est, lo, hi = result.gap(d["a"], "L7")
        c = per_width[w]
        rows.append(
            {
                "width": w,
                "collisions": c["collisions"],
                "per_million": c["per_million"],
                "games": d["games"],
                "wins": d["wins"],
                "draws": d["draws"],
                "losses": d["losses"],
                "elo": est,
                "interval": [lo, hi],
                "score_only_elo": elo_diff_from_score(d["score"]),
                "draw_elo": result.draw_elo,
                "draw_elo_fixed": fixed,
                "draw_rate": d["draws"] / d["games"],
                "registered": REGISTERED[w],
            }
        )
        print(
            f"{w:>6} {c['collisions']:>12,} {c['per_million']:>12,.0f} {d['games']:>7} "
            f"{d['wins']:>4}-{d['draws']:>3}-{d['losses']:>3}    {est:>8.0f} "
            f"[{lo:>+6.0f}, {hi:>+6.0f}]{'*' if fixed else ' '} {REGISTERED[w]:>13} "
            f"{DETERMINISTIC[w]:>15}"
        )
    print("\n* draw parameter fixed, not fitted: this arm has too few draws to fit one.")

    print("\nzero inside the interval? (no verdict where it is)")
    for r in rows:
        lo, hi = r["interval"]
        print(f"  {r['width']:>2} bits: {'yes — no verdict' if lo <= 0 <= hi else 'no'}")

    Path("data/zobrist_curve.json").write_text(
        json.dumps({"distinct_positions": distinct, "rows": rows}, indent=1)
    )
    print("\nwritten to data/zobrist_curve.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
