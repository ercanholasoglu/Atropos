# Pre-registration: were the rejected terms actually rejected?

Committed before the games.

## The half of the bias I had not looked at

`docs/SPRT_BIAS.md` measured what a sequential test reports when it **accepts
H1**, and that was enough to withdraw the ladder's numbers and re-measure the
one change that shipped. It says nothing about the other verdict. Three
evaluation terms in this project were **rejected** on an accepted H0.

Simulating the rejection side, same method, 1,200 matches per point:

**Evaluation A/B bracket, `elo0=0, elo1=40`:**

| true difference | P(accept H0) | games | reported | bias | bias ÷ sd |
|---:|---:|---:|---:|---:|---:|
| −40 | 100.0% | 161 | −32 | +8 | 0.44 |
| −20 | 99.8% | 235 | −20 | +0 | 0.01 |
| 0 | 90.1% | 379 | −9 | −9 | 0.67 |
| **+20** | **41.3%** | 464 | **−5** | **−25** | **2.10** |
| +40 | 3.9% | 335 | −10 | −50 | 4.24 |

**Ladder bracket, `elo0=0, elo1=100`:**

| true difference | P(accept H0) | games | reported | bias | bias ÷ sd |
|---:|---:|---:|---:|---:|---:|
| −50 | 99.8% | 42 | −49 | +1 | 0.03 |
| 0 | 96.5% | 77 | −20 | −20 | 0.56 |
| **+50** | **53.3%** | 140 | **−3** | **−53** | **1.58** |

**A genuinely positive change is rejected often, and reports about zero when it
is.** At the ladder's bracket a real +50 Elo improvement is thrown out more than
half the time. At the A/B bracket a real +20 is thrown out two times in five.

The rejections in this project are as unreliable as the acceptances were, for
the same reason and in the mirror direction.

## What that implicates

| record | games | reported | verdict | bracket | status |
|---|---:|---:|---|---:|---|
| `v3-shelter vs v2` | 359 | −2 | accept H0 | 40 | **suspect** |
| `v3-passers vs v2` | 714 | +11 | continue | 30 | **fine** |
| `L8-uniform vs L8` | 54 | −13 | continue | 100 | fine, but tiny |
| `L8 vs L7` | 25 | −85 | accept H0 | 100 | already re-measured |

**`v3-passers` needs nothing.** It never stopped — it ran to its game limit
without crossing a boundary — and an estimate from a test that did not stop
carries no stopping bias. Its +11 [−12, +34] is a fair reading of 714 games and
stays as it is. The same goes for `L8-uniform`, on far fewer games.

**`v3-shelter` is the one to check.** It reported −2 and was rejected. Against
the table above, −2 at 359 games is what a true difference of **0 to +20**
produces when this bracket rejects it. The rejection did not distinguish "does
nothing" from "worth +20", and the term — king shelter — was dropped on it.

## The measurement

    python -m scripts.sprt_match --a v3-shelter --b v2 --fixed --max-games 600

600 games, fixed length, no stopping rule, 0.1s per move, same operating point
as the original.

**Prediction: between −15 and +25, most likely near +5 to +10**, from reading
the observed −2 back through the table. 600 games gives about ±29.

* **Interval excludes zero on the positive side** → the term was rejected
  wrongly and belongs back in the discussion.
* **Interval contains zero** → the rejection stands as "not shown to help",
  which is what it should have said in the first place rather than "rejected".
* **Point estimate clearly negative, interval excluding zero** → the original
  verdict was right for the wrong reason.

**Falsified if** it lands outside [−60, +60], which nothing in the simulation
or the original 359 games makes likely.

## The wording that has to change either way

Independent of the result: `docs/DURUM.md` and the README describe these terms
as *rejected*. On this evidence "rejected" is too strong for anything tested at
these brackets. **"Not shown to help" is what an accepted H0 means**, and the
distinction is the same one this project already had to make about Level 8.
