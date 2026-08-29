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
