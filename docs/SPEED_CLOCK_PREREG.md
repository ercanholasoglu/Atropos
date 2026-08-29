# Pre-registration: strengthening the clock arm

Committed before the games it describes.

## Why this run exists

The clock arm was built as a *cross-check* on the node arm and got two points,
"to keep the cost down" (`scripts/speed_elo.py`). The third arm then showed the
node arm was measuring its own truncation overhead, and the clock arm was
promoted to the primary conversion — every downstream number in this project
now runs through **−174 Elo per real doubling [−203, −144]**.

A number carrying that much weight should not rest on two points. This adds
one, and fixes a second problem the promotion exposed.

**This is not a bracket changed after seeing data.** Nothing about which
points to add is chosen from the results: B/4 fills the gap between the two
existing points, and B/16 is excluded for a reason measured below and stated
before any game. The refit is reported whatever it produces, including if the
slope leaves [−203, −144].

## What gets added, and what does not

**B/4 — added, 240 games**, fixed length, same operating point as every other
pairing here. Its measured spend is 1999 nodes/move, which is 1.62 doublings
below the reference: squarely between the existing points at 0.63 and 2.05.

**B/16 — excluded.** The clock arm saturates, and the numbers say so:

| clock budget | nodes/move | real doublings below reference |
|---|---:|---:|
| B/1 (90.0 ms) | 6144 | 0.00 |
| B/2 (45.0 ms) | 3962 | 0.63 |
| B/4 (22.5 ms) | 1999 | 1.62 |
| B/8 (11.2 ms) | 1485 | 2.05 |
| B/16 (5.6 ms) | 1080 | 2.51 |

Halving the clock from B/8 to B/16 removes only **0.27 doublings**, because
`check_interval` is 2048 nodes and a search cannot be stopped mid-iteration
before it. Below about 11 ms the clock stops setting the budget and the check
interval does. B/16 would cost 240 games and buy almost no span, and — worse —
its point would sit at an x-value the apparatus, not the experiment, chose.

## The second problem: the x-axis is a measurement too

The node arm's x-coordinates are exact by construction: a budget of 1250 nodes
spends 1250 nodes, every time. **The clock arm's are not.** Repeating the
spend measurement five times:

| divisor | mean nodes | sd | |
|---|---:|---:|---|
| B/1 | 6144 | 0 | 0.0% |
| B/2 | 3962 | 210 | 5.3% |
| B/4 | 1999 | 68 | 3.4% |
| B/8 | 1485 | 0 | 0.0% |

The spread is real and machine-state dependent — a single earlier probe put
B/2 at 3582, outside all five of these. The published slope placed those points
as though they were exact, so its interval is narrower than it should be.

**The refit will resample both coordinates** — x from the spreads above, y from
each pairing's own sampling error — instead of only y. That will widen the
interval, and the wider one is the honest one. Stated now so the widening does
not look like a result.

## Prediction

Adding a point between two existing ones tests linearity where nothing has
tested it. On the current fit, B/4 at 1.62 doublings should score about
**−283 Elo**; at the interval's edges, between −233 and −329.

* **Inside that range** — the clock arm is linear across its usable span and
  the slope stands.
* **Clearly above −233** — the clock arm bends, the way a curve approaching
  the check-interval floor would, and a single slope is the wrong summary of
  it.

**Falsified if** B/4 lands below −329, which no account here predicts and
which would mean the two existing points are not describing the same curve.

## The test

    python -m scripts.speed_elo --arm movetime --workers 6

with `DIVISORS_MOVETIME = (2, 4, 8)`. The existing B/2 and B/8 results are
resumed untouched; only B/4 is played.

---

## Result

**B/4: 240 games, −250 Elo, interval [−313, −199].** The pre-registered
prediction was about −283, between −233 and −329. The point estimate is inside
that range and the "clearly above −233" bend criterion did not fire.

So the declared question passed. Fitting the three points then failed a test
that was not declared, and that is the finding.

### The through-origin fit is rejected

| x (doublings) | measured | line through origin | residual | ±y |
|---:|---:|---:|---:|---:|
| 0.633 (B/2) | −201 | −108 | **−92** | 26 |
| 1.620 (B/4) | −250 | −277 | +27 | 29 |
| 2.049 (B/8) | −332 | −351 | +19 | 34 |

χ² = 13.8 on 2 degrees of freedom, **p ≈ 0.001**. Allowing an intercept fits
comfortably (χ² = 1.2 on 1 dof, p = 0.27) at `Elo = −144 − 80 × doublings`.

Forcing the line through the origin was **my design choice**, and its stated
reason is in `scripts/speed_elo.py`: "zero doublings is zero Elo by
construction — the reference played against itself". The data rejects it. Two
points could not have shown that; three can.

### The misfit is one point, and it is unexplained

The whole of it is B/2, sitting 92 Elo below the line against its own ±26.
B/4 and B/8 are on it.

The obvious candidate is spend variance — the reference always searches exactly
6144 nodes while a divided clock does not — and **the data contradicts it**:

| | mean nodes | sd over 5 reps | per-position range |
|---|---:|---:|---:|
| B/1 | 6144 | 0 | 1.0× |
| B/2 | 3962 | 210 | 2.0× |
| B/4 | 1999 | 68 | 1.9× |
| B/8 | 1485 | 0 | **3.6×** |

B/8 has the widest spread of any point and sits on the line; B/2 has half that
and does not. Whatever the intercept is, it is not this. **Recorded as
unexplained** rather than fitted with the first story that sounded right.

### The prediction about the interval was wrong

The pre-registration said resampling x as well as y "will widen" the interval,
and asked that the widening not be read as a finding. It did not widen: 46 Elo
to 47. The fit is through a lever arm long enough that a 5% error on x barely
moves it. Reported because it was written down.

## What is usable

**For ≥1.6 doublings, where B/4 and B/8 agree on a line through the origin:
−158 Elo per doubling, [−182, −135].**

| claim | doublings | conversion | measured directly |
|---|---:|---:|---:|
| atropos deficit | 2.60 | **−411** [−472, −350] | ≈ −440 ✓ |
| the +39% speedup | 0.48 | +75 — **disputed region** | — |
| SEE pruning | 0.38 | +61 — **disputed region** | +48 [+11, +87] |

The atropos conversion sits inside the range the two consistent points cover
and agrees with a 480-game measurement. **The other two do not.** Both sit
below 0.5 doublings, nearer to B/2 — the one point the fit cannot account for —
than to anything that has been measured cleanly. Their numbers are quoted with
that attached rather than dropped, because a conversion in a region the
instrument does not describe is exactly the kind of number that gets repeated
without its caveat.

### What would settle it

A clock point between 0 and 0.63 doublings — B/1.25 or B/1.5 — measured the
same way. If the misfit is a property of small divisions, it will show there
too. If B/2 is simply a bad point, it will not. That is one more 240-game
pairing and it is the next thing this arm needs.
