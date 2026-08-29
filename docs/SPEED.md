# What a doubling of speed is worth

Every optimisation in this project was reported in nodes per second, which is
not a unit anyone cares about. This converts one to the other.

The brackets, the game counts, the predictions and the falsifiable claim were
committed before the first game was played (`b84fd6e`, sharpened in
`b46d86a`). Nothing below changed them.

## The result

Level 7 against a slowed copy of itself, 240 games per pairing, 960 games.
The slowed side's Elo, negative because it lost:

| budget | games | measured | 95% interval | predicted |
|---|---:|---:|---:|---:|
| B/2 | 240 | **−159** | [−212, −113] | −60 |
| B/4 | 240 | **−417** | [−518, −349] | −120 |
| B/8 | 240 | **−636** | [−911, −532] | −180 |
| B/16 | 240 | **−830** | [−2400, −678] | −240 |

**Slope: −207 Elo per doubling of the node budget, 95% interval
[−251, −164].**

> **Read the qualification before quoting this.** A third arm (below, and
> `docs/SPEED_ARM3_PREREG.md`) shows −207 is specific to a *hard* node budget,
> which throws away the iteration it interrupts. The conversion to use is
> measured on the clock — how this engine and everything it plays actually
> stops — and it is **−158 [−182, −135], valid above about 1.6 doublings**.
> Below half a doubling the clock arm is not described by any single slope;
> `docs/SPEED_CLOCK_PREREG.md` has the rejected fit and the point that breaks
> it.

That interval is not the one the least-squares fit reports. The fit says
±5, which treats the four points as exact; their own sampling errors run from
±25 at B/2 to ±153 at B/16. Propagating those through the fit gives [−251,
−164], and that is the number to quote.

## Against the prediction

Every point is outside its predicted interval, in the same direction, by a
factor of two and a half. The prediction came from published self-play
doubling curves for classical engines, which sit near 50–70 Elo. **This engine
is about three times as sensitive to speed as that literature suggests.**

The reason is visible in what the budgets buy. At the reference budget of 5000
nodes the search reaches depth 3.0; at B/2 it reaches 2.0, at B/8 1.6. The
published curves are measured at long time controls where a doubling adds a
ply to a search that already has fifteen. Here a doubling is the difference
between seeing a three-move tactic and not seeing it. **Elo per doubling is
not a constant of an engine, it is a property of the region of the curve you
measure in**, and this measurement is at the steep end.

Linearity, the pre-registered claim, holds: the residuals are +48, −2, −14, −1
against per-point errors of ±25 to ±153. Only the B/2 point sits away from the
line, and not by more than its own error. Whatever curvature exists is smaller
than this design can see.

## The cross-check that disagreed

The same halvings were also run as *movetime* divisions, on the prediction
that the two methods are two spellings of the same slowdown.

| budget | node arm | movetime arm |
|---|---:|---:|
| B/2 | −159 [−212, −113] | −201 [−257, −153] |
| B/8 | −636 [−911, −532] | **−332 [−409, −273]** |

At B/2 they agree. At B/8 they do not overlap at all, and the movetime arm is
300 Elo stronger. **Two methods intended to be equivalent are not**, which is
the finding the cross-check existed to catch.

### Why: they are not dividing the same thing

The pre-registered guess was granularity — `SearchStats.check_interval` is
2048 nodes, so a clock cannot stop a search earlier than that inside an
iteration. Measuring what each budget actually spends shows that is part of it
and not the main part:

| arm | nominal | nodes actually searched | real division |
|---|---|---:|---:|
| nodes | B/1 | 5000 (min 5000, max 5000) | — |
| nodes | B/2 | 2500 (exact) | 1/2.0 |
| nodes | B/8 | 625 (exact) | 1/8.0 |
| movetime | B/1 | 6144 | — |
| movetime | B/2 | 3582 (min 3920, max 4096) | **1/1.7** |
| movetime | B/8 | 1485 (min 569, max 2048) | **1/4.1** |

A movetime division by eight is a node division by **four**. The clock was
never dividing the thing the experiment was varying. Two separate causes:

1. **The reference points differ.** 0.09 s buys 6144 nodes, not the 5000 the
   node arm starts from, so the movetime arm was slowed from a 23% higher
   base.
2. **The floor.** At B/8 the budget is 11 ms, and the spend runs from 569 to
   2048 nodes — the top of that range is exactly one check interval. The
   search cannot stop mid-iteration before 2048 nodes; only the
   between-iteration check stops it earlier. The nominal budget is below the
   resolution of the instrument enforcing it.

### What is left over after correcting for that

Put both arms on nodes actually searched and let the node arm's curve predict
the movetime arm:

| movetime budget | nodes | curve predicts | measured | 95% interval |
|---|---:|---:|---:|---:|
| B/2 | 3582 | −161 | −201 | [−257, −153] — consistent |
| B/8 | 1485 | −425 | −332 | [−409, −273] — **outside, by 16** |

B/2 is explained; B/8 leaves about 90 Elo unaccounted for. A third arm was
built to find out why, and it found something better than the answer it was
looking for.

### The third arm, and what it overturned

The arm: a node budget enforced **only between iterations** — no clock at all,
so nothing about timing can be involved. Pre-registered in
`docs/SPEED_ARM3_PREREG.md` with two predicted outcomes 92 Elo apart.

**It landed outside both**, at −165 [−213, −122] where the predictions were
−349 and −257. The pre-registration's falsification clause fired: re-examine
the curve.

The re-examination needed no games:

| budget | enforcement | nodes spent | depth reached |
|---|---|---:|---:|
| 5000 | hard | 5000 | 3.00 |
| 2000 | soft | 3422 | 3.00 |
| 5000 | soft | 13567 | 4.00 |

**A hard budget of 5000 nodes reaches a depth that a soft budget reaches on
3422** — it spends 46% more nodes for the same search, because it is
interrupted part-way through an iteration and that iteration is discarded.
This is true at every rung of the original experiment, not just at the
reference.

So −207 was measuring two things at once: what a node is worth, and what it
costs to be truncated. Separating them:

| enforcement | Elo per real doubling | 95% interval |
|---|---:|---:|
| hard node limit (4 points) | −207 | [−251, −164] |
| **clock** (3 points; above 1.6 doublings) | **−158** | [−182, −135] |
| soft node limit (1 point) | −98 | [−126, −69] |

A third clock point was added afterwards, and it rejected the through-origin
fit those numbers assume (χ² = 13.8 on 2 dof, p ≈ 0.001). The whole misfit is
the B/2 point; B/4 and B/8 lie on the line quoted above. The clock row is
therefore restricted to the region those two cover.

Hard and soft do not overlap. The clock sits between them and is not separable
from the hard arm. What is established is that **how the budget is enforced is
a first-order variable in this measurement**, demonstrated between the
extremes — not a precise ordering of all three.

The earlier "two candidate mechanisms" framing in this document was wrong and
is corrected in the pre-registration: a budget enforced at iteration
boundaries *necessarily* spends a variable number of nodes, so "variable
budget" and "stops at a boundary" were one mechanism named twice. That came
out of building the apparatus, not out of the data.

## What this means for the rest of the project

Converted on the **clock** arm, in the region where it is described by a line
(≥1.6 doublings, −158 [−182, −135]):

| claim | doublings | conversion | measured directly |
|---|---:|---:|---:|
| atropos vs this engine | 2.60 | **−411** [−472, −350] | ≈ −440 ✓ |
| the +39% speedup | 0.48 | +75 — **outside that region** | — |
| SEE pruning | 0.38 | +61 — **outside that region** | +48 [+11, +87] |

The atropos row is the check worth having, and it is the one that lands inside
the measured region: −411 against a 480-game gauntlet reading of about −440.
Feature parity loses to throughput, and the size of the loss is now predicted
by an independent measurement to within its error.

**The other two rows sit below half a doubling, in the stretch of the clock
arm that no fit describes** — nearer to B/2, the point that breaks the
through-origin model, than to anything measured cleanly. They are quoted with
that attached rather than dropped, because a conversion taken from a region
the instrument does not cover is precisely the number that gets repeated
without its caveat. Closing it needs one more pairing at B/1.25 or B/1.5.

The +39% speedup is therefore worth **somewhere around +75 Elo** and not the
+29 an unmeasured rule of thumb suggested — but the interval on that is wider
than the arithmetic implies, and the honest summary is "clearly worth more
than the rule of thumb, size not pinned down".

## Reproducing

    python -m scripts.speed_elo --arm nodes --workers 6
    python -m scripts.speed_elo --arm movetime --workers 6

Both resume; `--minutes N` bounds a chunk. Data in
`data/speed_elo_nodes.json` and `data/speed_elo_movetime.json`, with run
telemetry (wall, CPU, nodes, peak RSS, commit) under `data/telemetry/`.
