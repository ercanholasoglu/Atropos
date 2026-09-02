# Where SEE actually helps

SEE pruning is the best-established result in this project — +50 [+30, +70]
over 1,200 games, +62 [+34, +91] on a second book, and +66 [+46, +86] again
under instrument v2. All of that is a count of who won. **None of it says
where.**

This is the same 1,200 games replayed with the evaluation logged term by term
and every game kept: **134,317 moves**, 63 MB of component records, 2 MB of
PGN. `data/games/see_1200.pgn` and `see_1200_components.jsonl`.

## The pairing, and a mistake corrected before it cost anything

The obvious command was `L7-see vs L7`. Under instrument v2 that measures
nothing: SEE is the default now, so `L7-see` and `L7` are the same engine.
`L7-v1` is not the answer either — it also puts the rook term back, which
measures the whole v2 cut rather than the one change.

`L7-nosee` was added for this: SEE off, everything else as v2 has it. Verified
before the run — both engines return 505 on the same test position, and differ
only in the flag.

**Result: 1,200 games, 59.38%, +66 Elo [+46, +86]**, consistent with the
+50 [+30, +70] measured before the cut.

## What the logs say

Averaged over every logged move:

| | depth | nodes | ms | nps |
|---|---:|---:|---:|---:|
| SEE | **3.99** | 7,098 | 114.3 | 62,077 |
| no-SEE | 3.83 | 7,277 | 112.7 | 64,550 |

SEE reaches **0.16 ply deeper on the same clock** while computing slightly
slower per node — the pruning costs something to evaluate and returns more than
it costs. That is the whole mechanism in two numbers, and it took logging the
games to see it.

### It is not spread evenly

| phase | SEE depth | no-SEE | gain | moves |
|---|---:|---:|---:|---:|
| opening | 3.09 | 2.73 | **+0.36** | 46,150 |
| middlegame | 3.63 | 3.41 | +0.22 | 28,533 |
| endgame | 4.85 | 4.89 | **−0.04** | 59,634 |

**In the endgame SEE buys nothing at all.** Nearly half the logged moves are
endgame moves, and across all of them the depth difference is within noise of
zero.

### And the reason is the thing it prunes

Grouping positions by how many captures are available in them:

| captures available | SEE depth | no-SEE | gain | positions |
|---:|---:|---:|---:|---:|
| 0 | 4.83 | 4.77 | +0.05 | 9,837 |
| 1 | 4.02 | 3.98 | +0.04 | 8,585 |
| 2 | 3.60 | 3.33 | +0.27 | 6,590 |
| 3 | 3.33 | 2.97 | +0.37 | 3,877 |
| 4 | 3.36 | 2.98 | +0.38 | 2,824 |
| 5 | 3.25 | 2.80 | +0.45 | 1,149 |
| 6+ | 3.11 | 2.48 | **+0.63** | 717 |

**+0.095 ply per additional capture available, correlation +0.96 across seven
buckets.**

A rule that skips captures losing material to the recapture should do nothing
where there are no captures and more where there are many. It does exactly
that, monotonically, over 33,000 sampled positions. The endgame result follows
from the same fact rather than being a separate one: endgames have fewer pieces
and therefore fewer captures.

## What this is and is not

**It is a mechanism confirmed by its own signature.** The prediction that SEE's
benefit scales with capture density was not made in advance — it is read off
the data — so the correlation is a description of what happened, not a test
that could have failed. What makes it more than a story is that the pattern is
monotonic across seven independent buckets and the mechanism was specified in
the code long before the log existed.

**It is not an Elo attribution.** Depth gained is not the same as games won,
and this does not decompose the +66 into per-phase contributions. Doing that
would need matches restricted to each phase, which is a different experiment.

**The obvious next question it makes askable:** if SEE does nothing in the
endgame and costs throughput to compute, switching it off below some phase
threshold should be free or better. That is a one-line change and a
600-game measurement, and it exists as a question only because the games were
kept.

---

## Correction: "no depth gain" is not "no work saved"

The section above ends by proposing an experiment — gate SEE off below some
phase, since it buys no depth in the endgame and costs throughput to compute.
**That experiment should not be run, and the reason is a measurement that took
thirty seconds and reverses the premise.**

Searching the endgame positions from these very games, at fixed depth 4, with
and without SEE:

| positions | SEE | nodes | seconds | nps |
|---|---|---:|---:|---:|
| endgame (phase ≤ 9) | on | 176,557 | 2.51 | 70,328 |
| endgame | **off** | 207,643 | 2.83 | 73,243 |
| non-endgame | on | 404,279 | 7.75 | 52,167 |
| non-endgame | **off** | 663,624 | 11.89 | 55,823 |

**Turning SEE off in the endgame searches 17.6% more nodes and takes 12.9%
longer.** It saves real work there. Gating it off would make the endgame
*slower* — about −28 Elo in those positions, or −12 Elo over a whole game at
the 44% of moves that are endgame moves.

### Why the match logs said otherwise

They did not, quite. They said the *depth* gain is −0.04 ply, and depth is
quantised. Each additional ply costs roughly 2.6× the previous one, measured
earlier: depth 5 is 0.49 s per move and depth 6 is 1.28 s. **A 12.9% time
saving is nowhere near the cost of one more ply**, so it buys real work and
zero whole plies, and shows up in a depth average as nothing.

The capture-density correlation in the previous section stands — SEE's *depth*
gain does track capture density, monotonically, +0.96. What does not follow,
and what I inferred anyway, is that no depth gain means no benefit.

### What this changes about the earlier section

The phase table stays: SEE gains +0.36 ply in the opening, +0.22 in the
middlegame, −0.04 in the endgame. **The conclusion drawn from its last row is
withdrawn.** SEE is doing useful work in endgames; the work is just too small
to cross a ply boundary.

It also sharpens the non-endgame figure. On real middlegame positions from
these games, SEE saves **53.4% of the time to a given depth** — far more than
the 23.3% measured on the eight book positions, which are quiet openings with
one capture available on average. The book understated the effect because the
book is not where the effect lives.

**Cost of finding this out: one deterministic measurement instead of 600
games.** The proposal in the previous section survived exactly as long as it
took to check its premise, which is the cheapest possible place for a bad
experiment to die.
