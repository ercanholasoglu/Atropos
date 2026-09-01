"""What switching SEE pruning on would do to every number already published.

The flag is off. The measurement says it is worth **+50 Elo [+30, +70]**, the
largest confirmed effect in this project, and the reason it stays off is not
the effect — it is that Level 7 is the instrument the anchor, the calibration
gauntlet, the ladder fit and the speed curve were all taken with. Switching it
on does not invalidate those numbers; it makes them describe an engine that no
longer exists.

That is a real cost and it deserves to be a table rather than a worry. This
computes it. Every figure below is derived from measurements already recorded,
not from new games:

* the joint fit places `L7-see` on the same scale as everything else
  (`scripts/rating_fit.py`), so the shift is read off directly rather than
  assumed to be the A/B's +50;
* the ladder gaps, the anchor and the calibration all move by that shift
  wherever Level 7 is one side of the comparison, and not at all where it is
  not.

    python -m scripts.see_impact
"""

from __future__ import annotations

import json
from pathlib import Path

FIT = Path("data/rating_fit.json")


def load_shift() -> tuple[float, float]:
    """How much stronger the fit says L7-see is than L7, with its error."""
    fit = json.loads(FIT.read_text())
    see = fit["ratings"]["L7-see"]
    ref = fit["ratings"]["L7"]
    return (
        see["relative_to_gauge"] - ref["relative_to_gauge"],
        (see["stderr"] ** 2 + ref["stderr"] ** 2) ** 0.5,
    )


def main() -> int:
    shift, err = load_shift()
    print(f"Joint fit places L7-see {shift:+.0f} +/- {err:.0f} Elo above L7.")
    print(f"The direct A/B over 1,200 fixed games says +50 [+30, +70].")
    print(
        f"Two routes, {abs(shift - 50):.0f} Elo apart, from overlapping but "
        f"not identical games.\n"
    )

    print("What moves, and what does not\n")
    print(f"{'measurement':<38} {'now':>12} {'if SEE is on':>14}")
    print("-" * 68)

    rows = [
        ("ladder gap L6 -> L7", "+19", f"{19 + shift:+.0f}", True),
        ("ladder gap L7 -> L8", "-35", f"{-35 - shift:+.0f}", True),
        ("Stockfish d1 vs L7", "-17", f"{-17 - shift:+.0f}", True),
        ("Stockfish d2 vs L7", "+61", f"{61 - shift:+.0f}", True),
        ("Stockfish d3 vs L7", "+72", f"{72 - shift:+.0f}", True),
        ("atropos vs L7 (0.3s gauntlet)", "11.7%", "lower, unmeasured", True),
        ("ladder gaps below L6", "unchanged", "unchanged", False),
        ("speed curve, -171 Elo/doubling", "unchanged", "re-measure", True),
        ("evaluation A/Bs (all on Level 6)", "unchanged", "unchanged", False),
        ("tactical suite, benchmark", "unchanged", "re-baseline", True),
    ]
    for name, now, after, affected in rows:
        mark = "  <-" if affected else ""
        print(f"{name:<38} {now:>12} {after:>14}{mark}")

    print()
    print("Reading it:")
    print("  * The ladder's top two gaps change sign in interest, not in kind.")
    print(f"    L6->L7 goes from +19 [-17, +55] -- not distinguishable from zero --")
    print(f"    to about {19 + shift:+.0f}, which would be a real rung again.")
    print("  * Every Stockfish anchor row moves by the same amount, so the")
    print("    *mapping* to absolute Elo shifts but its uncertainty does not:")
    print("    R(d) was never known and still would not be.")
    print("  * The speed curve was measured on Level 7 without SEE and is the")
    print("    one thing that needs re-running rather than re-labelling, because")
    print("    SEE changes which nodes the search visits, not just how fast.")
    print("  * Nothing below Level 6 moves at all, and neither do the")
    print("    evaluation A/Bs -- they were all run on Level 6.")
    print()
    print("Cost of switching: one flag, and re-running the speed curve")
    print("(about 960 games) plus a new bench baseline. Everything else is")
    print("re-labelling numbers that stay valid for the engine they measured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
