# Pre-registration: what does self-play buy, per game?

Committed before any training run. The costs below were measured first.

## The point that exists, and why it is not a measurement

One TDLeaf run is on record: **10,000 self-play games, scoring 53.1% against
the hand-written piece-square tables — over sixteen games.** Sixteen games is
an interval of roughly ±100 Elo. It is consistent with the learned tables being
a hundred Elo better and with their being a hundred worse.

It also carries `commit: null`: it predates run telemetry and cannot be tied to
the code that produced it. **All four points are trained fresh** rather than
reusing it, so the curve is one experiment rather than three plus an artefact.

## Design

| | |
|---|---|
| training sizes | **1,000 / 3,000 / 10,000 / 30,000** self-play games |
| seed | **the same for all four**, so the curve isolates training amount rather than mixing it with run-to-run variation. They are therefore not independent samples, which is the right trade for a curve and the wrong one for an error bar on any single point. |
| measured against | the hand-written tables, the thing the learner would have to beat to be worth using |
| match | **1,000 games per point**, fixed length, no stopping rule, 0.2 s per move |
| recorded per point | CPU-seconds, positions seen, wall-clock, **and** the strength it bought |

### Cost, measured rather than guessed

* Training: the recorded 10k run took **2,055 s**. Linear in games, 44,000
  games is about **150 minutes**.
* Evaluation: **1.8 s per game** serial, measured. 1,000 games per point on six
  workers is about 6 minutes; four points, **25 minutes**.

1,000 match games rather than 240 because they turned out to cost almost
nothing — ±22 Elo per point instead of ±45, for twenty extra minutes across the
whole curve. The expensive half is the training, and no amount of match games
changes that.

## Predictions

**The shape: Elo rises roughly linearly in log2(training games).**

**The slope: +40 to +80 Elo per doubling of training data.**

Reasoning, such as it is: TD methods on piece-square tables learn material fast
and placement slowly, and the learner starts from material-only, so almost all
of the remaining distance is placement. A doubling of experience buying a
tenth of the gap is the order the published work suggests.

Per point, taking the 53.1% at 10k as a weak prior and the slope above:

| training games | predicted Elo vs the tables |
|---:|---|
| 1,000 | −250 to −100 |
| 3,000 | −150 to −40 |
| 10,000 | −60 to +60 |
| 30,000 | −20 to +140 |

* **Slope inside +40 to +80** → the mechanism scales as expected, and the
  extrapolation to "how many games to beat the tables by a clear margin" is
  worth quoting.
* **Slope near zero** → self-play stops paying at this scale, which would be
  the most useful outcome: it puts a ceiling on the approach without needing
  the 300,000-game run to find it.
* **Slope above +80** → learning is cheaper than expected and the extrapolation
  is optimistic in this engine's favour, which needs checking against a fifth
  point before being believed.

**Falsified if** the fitted slope lands outside **[0, +150]** Elo per doubling.
A negative slope would mean more self-play makes it worse, which nothing here
predicts and which would point at the learner rather than the curve.

## The output

Elo against training games, with the cost of each point, and a slope that
answers the question the whole thing exists for: **how many self-play games
would it take to beat the hand-written tables outright, and how many CPU-hours
is that?**

That number is an extrapolation and will be labelled as one. The curve is
measured over 1k to 30k; anything said about 300k is arithmetic on a trend, not
a measurement, and the difference matters here more than usual because the
whole point is to decide whether to spend the machine time.

---

# Result

## The curve

| training games | match games | score vs tables | Elo | 95% interval | training |
|---:|---:|---:|---:|---:|---:|
| 1,000 | 1,000 | 41.9% | −57 | [−79, −36] | 253 s |
| 3,000 | 1,000 | 51.5% | **+10** | [−11, +32] | 718 s |
| 10,000 | 1,000 | 41.0% | −63 | [−85, −42] | 2,656 s |
| 30,000 | 1,000 | 24.8% | **−193** | [−219, −169] | 6,936 s |

**The prediction is falsified.** The fitted slope is **−27 [−33, −21] Elo per
doubling** — negative, and outside the [0, +150] falsification bound declared
in advance.

It is also worse than a wrong slope: **a line does not describe this at all.**
χ² = 76.5 on 2 dof, with residuals up to 5.4σ. The curve is non-monotonic —
it peaks at 3,000 games and falls away — so quoting *any* slope would be
inventing a shape the data does not have.

**More self-play makes this learner worse**, and the best point is the third
smallest.

## Why: measured, then tested by intervention

The weights say what happened. Mean table value per piece:

| | pawn | knight | bishop | rook | queen |
|---|---:|---:|---:|---:|---:|
| start | 100 | 320 | 330 | 500 | 900 |
| 1k | 89 | 317 | 328 | 499 | 900 |
| 10k | 65 | 287 | 309 | 490 | 896 |
| **30k** | **58** | **226** | **268** | **459** | 883 |
| hand-written | 110 | 307 | 328 | 501 | 897 |

Material decays monotonically with training. Meanwhile the spread *within*
each table inflates — the queen's standard deviation goes 14 → 58 against the
hand-written tables' 7.3. **The learner is trading material knowledge for
placement magnitude**, and by 30,000 games it believes a pawn is worth 58,
a 42% error in the most basic quantity in chess.

That was an inference, so it was tested rather than asserted. **Every placement
pattern the 30k run learned was kept; only each piece's table mean was restored
to its starting value.** One thing changed, everything else held.

| | Elo vs tables |
|---|---:|
| 30k as trained | −193 [−219, −169] |
| **30k, material restored** | **−122** [−146, −100] |
| 1k (the least-trained model) | −57 [−79, −36] |

**Restoring material recovers +71 ± 18 Elo, four standard errors.** The
mechanism is real and it is causal — one variable was changed under control.

**And it is only half the story.** The repaired model is still −65 ± 16 below
the 1,000-game one, also four standard errors. Of the 136 Elo lost between 1k
and 30k, **71 is material decay and 65 is the placement pattern itself.** The
second half is attributed by elimination rather than by intervention, which is
weaker evidence than the first, and is labelled that way.

## What this answers, and what it refuses to

The deliverable was an extrapolation: how many self-play games to beat the
hand-written tables, and at what cost.

**There is no such number, and that is the finding.** The curve does not rise;
it peaks at 3,000 games, at +10 [−11, +32] — an interval containing zero, so
even the peak is *not shown to beat the tables*. Extrapolating a trend that
turns down would be arithmetic on a shape the data contradicts.

The pre-registration named a slope near zero as the most useful outcome,
because it would put a ceiling on the approach without a 300,000-game run. The
actual result is sharper and cheaper than that: **there is no ceiling to find,
because the curve turns down at 3,000 games — 12 minutes of training.**

What the 44,000 games bought was the knowledge that the remaining 256,000 would
have been wasted, and a measured reason why: **TDLeaf here has nothing holding
material in place, so it drifts, and the drift costs more than the placement it
learns is worth.** Anchoring the piece values — freezing them, or regularising
toward them — is the change this result argues for, and it is a change to the
learner rather than to the budget.
