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
