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
