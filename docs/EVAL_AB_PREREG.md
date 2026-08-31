# Pre-registration: re-measuring the one change that shipped

Committed before the games.

## Why this is the next thing

`docs/SPRT_BIAS.md` showed that a number quoted from a stopped sequential test
is largely a property of the stopping boundary. The ladder's figures were
withdrawn on that basis and re-measured. **The evaluation A/Bs were run the
same way, and one of them shipped.**

`v3-rooks` — rooks on open and semi-open files — was accepted at 318 games and
reported **+44 Elo**. It is in `positional_score` and in every measurement
this project has taken since. If that number is an artifact, the engine is
carrying an evaluation term on the strength of a boundary.

## What the simulation says first

The evaluation A/Bs did not use the ladder's bracket. They used
`elo0=0, elo1=30` — a much narrower one, which forces the test to accumulate
far more evidence before it can stop. Simulating that exact configuration,
1,500 matches per point:

| true difference | P(accept H1) | games when it does | reported | bias | sd | bias ÷ sd |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 3.2% | 575 | +25 | +25 | 7 | 3.70 |
| 10 | 14.3% | 539 | +28 | +18 | 10 | 1.71 |
| 20 | 39.1% | 581 | +26 | +6 | 10 | 0.61 |
| 30 | 72.9% | 516 | +28 | −2 | 11 | 0.17 |
| 44 | 96.9% | 401 | +34 | −10 | 14 | 0.74 |
| 60 | 100.0% | 279 | +43 | −17 | 16 | 1.05 |

**This bracket was a much better choice than the ladder's.** Where `elo1=100`
made the test stop after a dozen games and report about +110 regardless,
`elo1=30` makes it run five hundred games, and across true differences of 20
to 44 the bias is under 11 Elo — smaller than the run-to-run spread.

It also runs the other way from what I expected. A test with this bracket
**under**-reports a real effect: at a true 44 it says +34, at a true 60 it says
+43.

So the observed **+44 at 318 games** is not a number to be deflated. Read
against the table it is most consistent with a **true effect of 50 to 60**, and
it is 2.7 standard deviations away from what a true zero would produce. My
suspicion when I started this — that the shipped term would turn out to be an
artifact — is not what the simulation supports, and I am recording that before
the games rather than after.

## The measurement

    python -m scripts.sprt_match --a v3-rooks --b v2 --fixed --max-games 240

240 games, fixed length, no stopping rule, 0.1s per move, the same operating
point as the original run.

**Prediction: +50, and the interval will exclude zero.** The simulation puts
the true effect at 50 to 60; 240 games gives about ±45, so an interval
excluding zero is expected but not guaranteed at the low end of that range.

* **Interval excludes zero** → the shipped term is real, and the original
  +44 was, if anything, conservative.
* **Interval contains zero** → 240 games is not enough to confirm a ~50 Elo
  effect on its own, and the honest statement becomes that the term rests on
  the original 318-game sequential result plus this one, neither decisive
  alone.
* **Point estimate near zero or negative** → the term should come out, and
  the eval and every measurement taken since would need re-labelling.

**Falsified if** the result lands below zero: the simulation says that outcome
has a probability under 2% if the true effect is anywhere near 50.

---

## Result

**600 games, fixed length: 49.8%, −2 Elo, interval [−26, +22].**

| run | games | stopping | score | Elo |
|---|---:|---|---:|---:|
| original | 318 | sequential, accepted H1 | 56.3% | **+44** |
| this one | 600 | none | 49.8% | **−2** [−26, +22] |

**The prediction failed.** It said +50 with an interval excluding zero, and
named "below zero" as the falsifying outcome. The point estimate is −2.

More usefully: **the interval excludes +44.** The number that justified
shipping this term is outside what 600 games will support.

## What this does and does not say

It does **not** say the term hurts. [−26, +22] contains zero, and reading a
negative point estimate as a regression is the exact mistake this project
corrected over Level 8.

It says the term's *claimed benefit is refuted*. The shipped figure was +44;
the measurement is −2 with a tight enough interval to rule that out.

The two runs are in tension but not flatly incompatible — z = 1.88 on the
score difference, p ≈ 0.06. Pooling them would be wrong: the first stopped on a
favourable swing and its games are not a fair sample, which is the rule
`scripts/rating_fit.py` already applies.

## The cost side, measured rather than quoted

| evaluation | nodes | time | nps |
|---|---:|---:|---:|
| v2 | 181,238 | 2.74 s | 66,197 |
| v3-rooks | 181,145 | 2.96 s | 61,297 |

The term costs **7.4% of throughput**, which is 0.111 doublings, which at the
measured −171 Elo per doubling is **−18 Elo**. So the positional gain has to be
worth about +18 just to break even, and the net measurement is −2.

That is a coherent picture rather than a puzzle: **the term is probably doing
something positional, and paying for it in speed at roughly the same rate.**

## Where that leaves the engine

The engine currently has this on, decided from a sequential result the
measurement does not reproduce. It also has **SEE pruning off**, decided
conservatively, and SEE measured **+48 [+11, +87]** over 240 fixed games with
both its runs excluding zero.

**Those two decisions are the wrong way round on the evidence available now.**
Neither is mine to change unilaterally — Level 7 is the instrument every
current number was taken with, and switching either rewrites what those numbers
describe — but the asymmetry should be stated rather than left in the code.

## What would settle the rook term

The interval is [−26, +22] on 600 games. Distinguishing "nothing" from "+20"
needs roughly 1,500, and from "+10" roughly 6,000 — the resolution floor this
project measured early and has run into repeatedly. The honest summary is that
**a term of this size is at the edge of what this setup can resolve at all**,
which is itself the argument for spending effort on throughput instead.
