# Pre-registration: SEE pruning in quiescence

Written and committed before any game was played. The prediction below comes
from a measurement (`docs/SPEED.md`) rather than from a rule of thumb, which
makes it specific enough to be wrong.

## The change

`engine/search/see.py` implements static exchange evaluation. Quiescence
skips captures whose SEE is negative — captures that lose material to the
recapture — while not in check. Off by default (`use_see_pruning=False`), so
the shipped ladder is unchanged until this resolves.

Atropos lists static exchange evaluation under Phase 17. It was the one item
on that roadmap with no Python counterpart.

## What is already measured

Level 7, fixed **depth 4**, the 8 book positions, SEE pruning off then on:

| | nodes | wall | nps | best move |
|---|---:|---:|---:|---|
| off | 111,705 | 2.02 s | 55,264 | — |
| on | 84,149 | 1.55 s | 54,247 | same in 8/8 |

**24.7% fewer nodes, 23.3% less wall time**, and SEE itself costs about 2% of
throughput to compute — the saving is net of that. The same move came out of
every position, which is what a pruning rule that only removes losing lines
should do, though eight positions cannot establish that in general.

## The prediction

A 23.3% reduction in time-to-depth is **0.38 doublings** of effective budget.
At the measured −207 Elo per doubling [−251, −164]:

> **+79 Elo, and the speed curve's own uncertainty puts that between +63 and
> +96.**

This is an *upper* estimate, and deliberately stated as one. The speed curve
was measured by changing the budget with the search algorithm held identical.
SEE pruning also changes *which* nodes are searched, so the total is the
throughput gain minus whatever accuracy the pruning costs. Two outcomes are
therefore interesting rather than one:

* **Near +79** — the pruning is free; it removes only lines that did not
  matter.
* **Clearly under +63** — the throughput gain is real but the rule is
  discarding something. The gap between the measured result and +79 is then
  the price of the pruning, and it is a number nothing else in this project
  can produce.

**Falsified if** the result lands at or below 0. That would mean a 23% speed
gain bought nothing, which would contradict the speed curve rather than this
change, and would make the curve the thing to re-examine.

## The test

    python -m scripts.sprt_match --a L7-see --b L7 --elo1 100

Bracket `elo0=0, elo1=100`, chosen before the run: the predicted effect is +79,
which sits inside it, and the resolution table says an effect of that size
settles in a few hundred games. 0.1 s per move, both sides, the standard
operating point. No stopping rule other than the sequential test itself.

Committed before the first game.

---

## Addendum, written after the sequential test and before the fixed one

The SPRT accepted H1 at 120 games: **+73 Elo, interval [+20, +130]**.

The point estimate is close to the predicted +79, and it is tempting to stop
there. The interval says not to. It is 110 Elo wide, and it contains both
outcomes the pre-registration set out to tell apart — "near +79, the pruning
is free" and "clearly under +63, the pruning is discarding something". **The
sequential test answered the question it was built for (is this better than
nothing) and cannot answer the one that was actually interesting.**

That is not a flaw in the test; it is what a stopping rule does. It stops as
soon as the evidence rejects H0, which leaves the estimate biased away from
zero and the interval as wide as it is allowed to be. The same reasoning is
already committed in `scripts/speed_elo.py`, which is why the speed curve was
measured at fixed length.

So: a **second, separate** measurement, declared here before it runs.

* **240 games, fixed length, no stopping rule** (`--fixed`). 240 buys roughly
  ±45 Elo, which does separate +79 from +20.
* **A fresh state file.** The 120 games above were played under a stopping
  rule; pooling them with a fixed-length block would carry that bias into the
  result. They are reported separately and not combined.
* Same operating point, same bracket, same engines. Nothing else changes.

**What each outcome means, fixed now:** an interval that contains +79 and
excludes +20 supports "the pruning is free". One that excludes +63 says the
rule costs accuracy, and the distance below +79 is the price. One that still
spans both is a null result on the magnitude question, and I will report it as
that rather than lean on the point estimate.

---

## Result

| run | games | score | Elo | 95% interval | stopping |
|---|---:|---:|---:|---:|---|
| sequential | 120 | 60.4% | +73 | [+20, +130] | SPRT, accepted H1 |
| **fixed** | **240** | **56.9%** | **+48** | **[+11, +87]** | none |

### Against the criteria fixed in advance

* *Contains +79 and excludes +20* → **no.** The interval reaches +87, so +79
  is inside it, but it also reaches down to +11.
* *Excludes +63* → **no.**
* *Spans both* → **yes.**

**So this is a null result on the magnitude question, and the criterion
committed above says to report it as one rather than lean on the point
estimate. That is what this is.**

What is established, by both runs independently, is that SEE pruning is
**better than not having it**: both intervals exclude zero. What is not
established is how much better. +48 is the best estimate available and it
comes with an interval running from +11 to +87 — a factor of eight. The
prediction of +79 sits at the top edge: not refuted, not supported.

### The one thing worth noticing

The sequential run said +73. The fixed run said +48. That is the direction the
stopping-rule bias predicts — a test that stops the moment it can reject H0
stops on a favourable fluctuation, and its estimate is pushed away from zero.

**It does not demonstrate the bias.** The two intervals overlap across most of
their length, so a difference of 25 Elo between them is exactly what two
samples of this size would produce by chance. The direction is consistent with
the bias; the data cannot separate it from noise. Recorded because it is the
kind of agreement that is easy to over-read.

### What the throughput result does say

The deterministic measurement is not in doubt and does not depend on any of
the above: **24.7% fewer nodes, 23.3% less wall time, same move in all 8 book
positions.** Those were counted, not sampled. The uncertainty is entirely in
converting them to Elo.

### Shipping decision: not taken here

The flag stays off by default. The measurement supports switching it on — the
effect is positive in both runs — but Level 7 is the rung the Stockfish anchor
and the atropos gauntlet were both measured against, this week. Turning it on
changes the instrument that every current number was taken with, and those
numbers would then describe a ladder that no longer exists.

That is a decision about what the ladder is *for*, not a question the data
answers. If it is switched on, `docs/ANCHOR.md`, the calibration table and the
ladder SPRTs all need re-labelling as pre-SEE, the same way 1514 and 1538 are
labelled to evaluation v2.

---

## Extension to 1,200 games, declared before playing them

SEE is the largest positive effect this project has measured and it is sitting
behind a flag, switched off, because 240 games left it at **+48 [+11, +87]** —
an interval too wide to decide on. Everything else that was open has since been
measured; this is the one live number left, so it gets the games.

**Target: 1,200 total, fixed length, no stopping rule**, continuing from game
index 240 so nothing is replayed. That gives about ±20.

### Two predictions, from different places

**From the mechanism.** The deterministic measurement — 23.3% less wall time to
the same depth, counted not sampled — is 0.383 doublings, which at the measured
−171 Elo per doubling is **+65**. That is the throughput component alone and
ignores whatever the pruning costs in accuracy, so it is an upper estimate.

**From the sample.** 240 games said +48.

**Prediction: between +40 and +60, interval roughly [+30, +70].** The two
accounts bracket it, and the gap between +65 and the eventual number is the
price of the pruning — a figure nothing else here can produce.

* **Interval clear of zero and near +50** → SEE is real, its size is known, and
  the case for switching it on rests on a measurement rather than an argument.
* **Interval clear of zero but well under +40** → the pruning costs more
  accuracy than the throughput measurement suggests, and the gap is the finding.
* **Interval contains zero** → 240 games was the thin end of noise, as happened
  with `passers-rooks`, and SEE joins the list of things not shown to help.

**Falsified if** the result lands outside [+10, +90].

**No extension beyond 1,200.** If that does not resolve it, the answer is the
resolution floor again, and the flag stays off on the grounds that an
unmeasurable change should not alter the instrument every other number was
taken with.

### Result

**1,200 games, fixed length: 57.1%, +50 Elo, interval [+30, +70].**

| against | value | |
|---|---:|---|
| declared range | +40 to +60 | **point estimate +50** |
| declared interval | roughly [+30, +70] | **[+30, +70]** |
| mechanism, throughput only | +65 | inside |
| the 240-game sample | +48 | inside |
| falsification | outside [+10, +90] | not falsified |

The prediction holds on every criterion it was written with, which has not
happened often here. Six of the thirteen pre-registrations in this project
failed; this is not one of them.

### The number the mechanism could not give

The deterministic measurement said SEE removes 23.3% of the wall time to a
given depth, worth **+65** at the measured conversion — throughput alone,
before whatever the pruning costs in accuracy. The match says **+50**.

**The difference, +15 Elo, is the price of the pruning.** It is what discarding
captures that lose material to the recapture costs in lines that turn out to
matter. Nothing else in this project can produce that figure: it needs a
deterministic count and a played measurement of the same change, and it is the
gap between them.

That the price is small — under a quarter of the gain — is what a rule that
only drops provably losing captures ought to look like.

### Behaviour, against the other candidate

`passers-rooks` measured +26 [+1, +51] at 600 games and **+12 [−8, +31]** at
1,200: it fell as games accumulated, and the interval swallowed zero.
SEE measured +48 at 240, +46 at 636, **+50 at 1,200**: it did not move, and the
interval tightened away from zero.

Those are what a real effect and the thin end of noise look like when you keep
playing, and the only reason they can be told apart is that both were run at
fixed length. A sequential test would have stopped both early and reported
something near +110 for each.

### The decision this was run to inform

SEE is now **the only change measured in this project with a tight interval
clear of zero on the positive side**: +50 [+30, +70] over 1,200 games, with an
independent mechanistic account agreeing to within 15 Elo.

It remains **off**, and that is still not mine to change. Level 7 is the
instrument every current number was taken with, and switching it on rewrites
what those numbers describe — the anchor, the calibration gauntlet, the ladder
fit and the speed curve all measured a Level 7 without it. What has changed is
that the case is no longer an argument. It is a measurement, and it is the
strongest one here.
