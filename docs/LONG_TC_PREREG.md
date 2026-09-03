# Pre-registration: the long-time-control battery

Committed before any of its games. Everything numeric below was measured
first, on instrument v2, and is what the predictions are built from.

---

## 2a. Does pruning pay when it has depth to buy?

### The measurement that motivates it

Level 7 adds null-move pruning, late move reductions, history and aspiration
windows to Level 6. Every one of those is a gamble that spends accuracy to buy
**depth**. If the clock does not let the extra depth appear, the mechanism
cannot pay and the pairing measures the gamble without the payoff.

Depth reached per budget, measured on the eight book positions before writing
this:

| movetime | L6 depth | L7 depth | **L7 advantage** | L7 nodes |
|---:|---:|---:|---:|---:|
| 0.10 s | 3.00 | 3.25 | **0.25 ply** | 6,100 |
| 0.25 s | 3.38 | 4.12 | 0.74 | 13,518 |
| 0.50 s | 3.88 | 4.88 | 1.00 | 26,112 |
| **1.00 s** | **4.62** | **5.62** | **1.00 ply** | 48,384 |
| 2.00 s | 4.88 | 6.00 | 1.12 | 93,184 |

**At the operating point every measurement in this project used, Level 7's
depth advantage is a quarter of a ply.** At 1.0 s it is a full ply.

### The test

`L7 vs L6`, **300 games**, **1.0 s per move**, fixed length, no stopping rule,
default book, instrument v2.

300 rather than 240 because a game costs 58 s serial at this clock — measured,
not estimated — so 300 games is about **56 minutes** on six workers, and the
extra 60 games are nearly free relative to the block.

### Prediction

At 0.1 s the pairing measures **+41 [+3, +80]** (instrument v2).

If the techniques work through depth, quadrupling the depth advantage should
widen the gap. **Prediction: +90 to +150, interval roughly [+50, +190].**

* **Clearly above +80** → the mechanism is depth, confirmed, and every result
  this project took at 0.1 s was taken at an operating point that hides most of
  what Level 7 is.
* **Statistically indistinguishable from +41** → the techniques do not pay in
  this engine even when given the depth they were built to buy. **That is a
  valid result, not a failure**, and it would say the ladder's top rung is a
  rung by construction rather than by search quality.
* **Lower than +41** → the pruning costs more than the depth returns at longer
  clocks, which would be the most interesting outcome and the one nothing here
  predicts.

**Falsified if** the result lands outside [−50, +250].

---

## 2b. Where the slope flattens

### Why the current number is local

The speed curve was measured with a reference budget of 0.09 s, which reaches
**depth 3.0**. **−162 Elo per doubling [−198, −127] is a property of that
region**, not a constant of the engine. Published curves for strong engines
flatten at long time controls; whether this one does has never been asked.

### What is affordable, measured

Cost of reaching a fixed depth, Level 7, instrument v2:

| depth | sec/move | nodes/move | sec/game (80 moves) |
|---:|---:|---:|---:|
| 5 | 0.49 | 22,440 | 39 |
| 6 | 1.28 | 62,195 | 102 |
| 7 | 2.81 | 145,260 | 225 |
| 8 | 6.57 | 294,692 | 526 |

The cost roughly **doubles per ply**. Extrapolating one more: depth 9 is about
15 s per move, **20 minutes per game**. A single 150-game point at that
reference would take **ten hours on six workers**, and the curve needs four.

**So the depth ~9 point asked for is not run, and this says so with the number
rather than skipping it quietly.** It is not a judgement about its value; it is
sixty hours of machine time for one point.

### The design

| point | reference | L7 depth | divisors | games/point | cost |
|---|---|---:|---|---:|---|
| **A** | 0.09 s | 3.0 | B/1.5, B/2, B/4, B/8 | 240 | **already measured** |
| **B** | 1.00 s | 5.6 | B/2, B/4, B/8 | 150 | ~2.5 h |
| ~~C~~ | ~3.1 s | 7.0 | — | — | **not run, ~6 h** |

Three divisors at point B rather than four: B/1.5 contributed least at point A
(0.33 doublings, the shortest lever) and costs the same as the others.

150 games gives about ±58 Elo per point, which resolves a slope difference of
the size in question — v1 measured −171 and −162 at the same region, so a
flattening worth detecting is tens of Elo per doubling, not single digits.

### Prediction

**The slope flattens: −100 to −140 Elo per doubling at reference depth 5.6,
against −162 [−198, −127] at depth 3.0.**

The reasoning is the same one this project has already measured once. At depth
3 a doubling is the difference between seeing a three-move tactic and not; at
depth 5.6 it buys a ply on a search that already has five, which is worth less.
That is exactly why the original prediction of 50–70 Elo per doubling (from
published long-time-control curves) missed by 2.5× at depth 3.

* **Clearly shallower than −127** → the curve flattens with depth, and "Elo per
  doubling" has to be quoted with the depth it was measured at, everywhere.
* **Indistinguishable from point A** → the slope is flat across this range and
  −162 can be quoted plainly.
* **Steeper** → nothing here predicts it, and it would mean depth is worth
  *more* as it grows, which contradicts every published curve.

**Falsified if** point B lands outside [−250, −30].

### The output

Elo per doubling against reference depth, two points, with the third named and
priced rather than pretended. That is the measured answer to "what would a
substrate change be worth" — a faster engine moves along this curve, and the
curve says how much that is worth where it would land.

---

# Results

## 2a — the mechanism is depth, confirmed

**300 games at 1.0 s: 67.17%, +124 Elo, interval [+84, +168].** W-D-L
159-85-56.

Every criterion fixed in advance:

| criterion | declared | measured |
|---|---|---|
| point estimate | +90 to +150 | **+124** |
| interval | roughly [+50, +190] | [+84, +168] |
| must exclude the 0.1 s figure of +41 | — | **excluded** |
| falsification | outside [−50, +250] | not approached |

The estimate was stable from 84 games onward (+84, +116, +115, +120, +124)
while the interval tightened, which is the shape of a real effect rather than
the thin end of noise — the same contrast this project drew between SEE and
`passers-rooks`.

### What it says

Level 7's depth advantage over Level 6 goes from **0.25 ply at 0.1 s to 1.00
ply at 1.0 s**, and the measured gap goes from **+41 [+3, +80] to +124 [+84,
+168]** — roughly three times. Null-move pruning and late move reductions
work through depth, and given depth to buy, they pay.

### What it costs the rest of the project

This is bigger than one pairing. **Every match in this repository was played at
0.1 s**, and at that clock Level 7's defining techniques are barely engaged.
The ladder's top rung looked marginal — under instrument v1 it was +18
[−18, +53], not distinguishable from zero — and the reason was the operating
point, not the engine.

That does not invalidate the earlier numbers. They are correct for the clock
they were measured at, and every comparison drawn between them is between
engines measured at the same clock. What it changes is what they generalise
to: **a result at 0.1 s is a result about search that has not been given room
to work**, and the ladder's spacing, the anchor and the atropos calibration all
inherit that.

It also sharpens something already in the README, which noted that Level 7's
advantage was clock-dependent from a 16-game comparison at 0.3 s and 1.5 s.
That observation was right and under-powered. This is the same finding at 300
games with an interval.

## 2b — the slope, measured a second time

**450 games, reference 1.0 s (depth ~5.6): −129 Elo per doubling,
interval [−151, −107].** χ² = 2.1 on 2 dof, p ≈ 0.71.

| budget | games | nodes | doublings | Elo | ±y | ±x |
|---|---:|---:|---:|---:|---:|---:|
| B/2 | 150 | 31,795 | 0.985 | −115 | 30 | 0.009 |
| B/4 | 150 | 16,589 | 1.923 | −297 | 40 | 0.012 |
| B/8 | 150 | 8,325 | 2.918 | −346 | 44 | 0.021 |

### Against what was written down

| criterion | declared | outcome |
|---|---|---|
| point estimate | −100 to −140 | **−129 — inside** |
| falsification | outside [−250, −30] | not approached |
| "clearly shallower than −127" → flattening | — | **not met**: the interval contains −127 |
| "indistinguishable from point A" → flat | — | **this is the one that applies** |

**The prediction's number was right and its discrimination was not.** −129
against −162 is a difference of **+33 ± 21, or 1.56σ**, which does not resolve.
By the criterion fixed in advance, the honest reading is the second row: **the
slope is not distinguishable between reference depth 3.0 and reference depth
5.6.**

It moved in the predicted direction, and that is worth exactly as much as the
direction of a 1.6σ shift is worth — which is to say it is consistent with
flattening and equally consistent with a flat curve. Separating −129 from −162
needs roughly four times these games, about six hours at this clock, and the
question does not justify it: for every conversion this project actually makes,
the two numbers give answers within 20%.

### The part that was not predicted, and is better than the result

**The deep-reference measurement is far better conditioned than the shallow
one.** Compare the x-errors: 0.009 to 0.021 doublings here, against 0.11 to
0.31 at the 0.09 s reference.

The reason is the check interval. At 0.09 s the budgets were 1,300 to 4,800
nodes, close enough to the 2,048-node clock-check granularity that what each
budget actually bought wobbled by 5% between repetitions and the divisors did
not deliver clean doublings — 0.33, 0.62, 1.31, 1.85 where 0.58, 1, 2, 3 were
asked for. At 1.0 s the budgets are 8,000 to 63,000 nodes, far above that
floor, and the divisors land on **0.985, 1.923, 2.918**.

The consequence is visible in the fit. At the shallow reference a
through-origin line was rejected and one point sat 3.6σ out until the error
bars were corrected; here χ² is 2.1 on 2 dof with no point beyond 1.2σ.

**A measurement taken at the operating point this project has always used is
fighting its own instrument's granularity.** That is a second, independent
reason — alongside 2a's depth finding — that 0.1 s was the wrong clock to have
measured everything at.

### What this gives the substrate question

Elo per doubling against reference depth:

| reference | depth | Elo per doubling | 95% interval |
|---|---:|---:|---:|
| 0.09 s | 3.0 | −162 | [−198, −127] |
| 1.00 s | 5.6 | −129 | [−151, −107] |
| ~3.1 s | 7.0 | **not run** | ~6 h |
| — | 9.0 | **not run** | ~60 h |

Two points, consistent with each other, and no evidence of curvature between
them. **A substrate change that made this engine k times faster would be worth
roughly 130 to 160 Elo per doubling anywhere in the range measured** — and the
honest form of that answer is a range with two endpoints rather than a single
slope, because the two measurements do not separate.

## A third point, measured for a different reason

`tests/test_engine.py` gates L7 against L6 at 0.2 s, and the gate was failing
about half the time. Fixing its threshold needed the true score at *that* time
control, so the pairing was measured there too: **240 fixed-length games,
118-55-67, score 0.606, +79 Elo [+38, +121]** (`data/fixed_L7_vs_L6_02s.json`).

| movetime | Elo | 95% interval |
|---|---:|---|
| 0.1 s | +41 | [+3, +80] |
| 0.2 s | **+79** | [+38, +121] |
| 1.0 s | +124 | [+84, +168] |

Three points, rising monotonically, each interval overlapping its neighbour and
the 0.1 s and 1.0 s ends separated. Nothing here resolves the shape of the
curve — adjacent points do not separate — but the direction that 2a established
holds at a third budget: the further this engine gets from 0.1 s, the more L7's
techniques are worth. The measurement that has been quoted throughout this
project was taken at the operating point where they are worth least.
