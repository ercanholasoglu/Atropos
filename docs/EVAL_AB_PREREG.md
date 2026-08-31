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
