# Pre-registration: the point that decides whether B/2 was a bad point

Committed before the games it describes. This is the pairing
`docs/SPEED_CLOCK_PREREG.md` named as the next thing the clock arm needs.

## The question

Three clock points rejected a line through the origin (χ² = 13.8 on 2 dof,
p ≈ 0.001). The entire misfit is **B/2**, sitting 92 Elo below the line while
B/4 and B/8 sit on it. A line with an intercept fits comfortably
(`Elo = −144 − 80x`), but an intercept means the slowed side pays a fixed
penalty the moment its clock is divided at all — which nothing here explains,
and the obvious candidate (spend variance) is contradicted by B/8 having the
widest spread and lying on the line.

Two readings remain, and they differ in what the whole arm means:

* **B/2 is one bad point.** The clock arm is a line through the origin at
  about −158, and one measurement missed.
* **There is a real offset.** Dividing the clock costs something fixed on top
  of the nodes it removes, and the "Elo per doubling" summary is wrong for
  small changes — which is exactly where the +39% speedup and SEE conversions
  sit.

## The point that separates them

**B/1.5 — clock 60 ms.** Measured spend **4754 nodes/move (sd 142 over five
repetitions, range 4096–6144)**, which is **0.370 doublings** below the
reference. That lands between the origin and B/2 at 0.61, where the two
readings are furthest apart.

Why not the alternatives, decided before running and from measurement:

| divisor | ms | nodes | doublings | |
|---|---:|---:|---:|---|
| B/1.25 | 72.0 | 5972 | 0.041 | too close to the reference to carry information |
| **B/1.5** | **60.0** | **4754** | **0.370** | **chosen** |
| B/1.75 | 51.4 | 4069 | 0.594 | a duplicate of B/2 at 0.610 |

## Prediction

At 0.370 doublings:

* **line through the origin (−158):** −58 Elo
* **offset model (−144 − 80x):** −174 Elo

**115 Elo apart.** 240 games gives about ±45, so this separates them at better
than two standard errors — a real test rather than a gesture.

**Falsified if** the point lands outside both, below −219 or above −13, in
which case neither reading survives and the clock arm is not described by any
straight line at all.

## Consequences, fixed now

* **Near −58** → B/2 was a bad point. −158 [−182, −135] applies across the
  arm, the speedup converts to about +75 and SEE to about +61, and the caveats
  currently attached to both come off.
* **Near −174** → the offset is real. A single Elo-per-doubling figure is
  wrong for small speed changes, the speedup and SEE conversions are
  unusable as stated, and every downstream number under about one doubling has
  to be re-derived or withdrawn.

Both outcomes change what this project claims, which is the point of running
it.

## The test

    python -m scripts.speed_elo --arm movetime --workers 6

with `DIVISORS_MOVETIME = (1.5, 2, 4, 8)`. The three existing pairings resume
untouched; only B/1.5 is played. 240 games, fixed length, no stopping rule,
same operating point and opening book as every other pairing here.

---

## Result

**B/1.5: 240 games, −82.6 Elo, interval [−129, −38].**

| reading | predicted | inside the interval? |
|---|---:|---|
| line through the origin | −58 | **yes** |
| offset model | −174 | no |

**The offset model is rejected.** Dividing the clock does not cost a fixed
penalty on top of the nodes it removes, and the caveat currently attached to
every sub-doubling conversion is not justified by an offset.

### Refitting with four points

Spends re-measured in one pass so all four x-values come from the same
machine state:

| divisor | nodes | doublings | Elo | ± | residual vs the 4-point line |
|---|---:|---:|---:|---:|---:|
| B/1.5 | 4809 | 0.341 | −82.6 | 23 | −1.0σ |
| **B/2** | 4005 | 0.605 | −200.6 | 26 | **−3.6σ** |
| B/4 | 1999 | 1.608 | −250.0 | 29 | +1.0σ |
| B/8 | 1485 | 2.037 | −331.5 | 34 | +0.7σ |

A line through the origin is still rejected on all four (χ² = 15.6 on 3 dof)
and **the entire misfit is still B/2**, now flanked on both sides by points
that fit. Dropping it: **−162 Elo per doubling [−185, −139], χ² = 1.5 on 2
dof** — an unremarkable fit.

### What is not settled

**Three points make a clean line and one point is 3.6σ away, and I do not know
why.** The reading that the arm is linear through the origin now rests on
calling B/2 anomalous, and "it is the point that does not fit" is not a reason
to drop a measurement. A 3.6σ outlier in four points is also too improbable to
wave through as chance.

So the conversion below is stated **conditional on B/2 being anomalous**, and
the next run tests exactly that rather than assuming it.

## Follow-up, declared before it runs

**Replay B/2 with 240 games the first run did not play.** Game indices choose
the opening and both seeds, so a re-run from zero would replay the same games
and prove only that the code is deterministic; the replication is offset by
1000.

* **Near −98** (the line's value at 0.605 doublings) → the first B/2 was a
  fluke, the arm is linear through the origin at −162, and every conversion
  can be quoted without qualification.
* **Near −201** → it reproduces, it is a real feature of that operating point,
  and the arm is *not* a single line. What lives at B/2 then becomes the
  question, and no conversion near 0.6 doublings can be trusted until it is
  answered.

103 Elo apart, ±45 at 240 games.

    python -m scripts.speed_elo --arm movetime --only 2 --index-offset 1000 \
        --out data/speed_elo_movetime_b2_replication.json

---

## Replication result

**B/2 replayed, 240 games the first run did not play: −115.5 Elo
[−162, −69].** Against the two declared outcomes:

| | predicted | inside? |
|---|---:|---|
| the first B/2 was a fluke | −98 | **yes** |
| it reproduces | −201 | no |

But the more useful number is the comparison between the two runs of the same
pairing:

| run | games | score | Elo | 95% interval |
|---|---:|---:|---:|---:|
| original | 240 | 0.760 | −201 | [−252, −149] |
| replication | 240 | 0.660 | −116 | [−162, −69] |
| **pooled** | **480** | 0.710 | **−156** | **[−190, −122]** |

**They differ at z = 2.43, p = 0.015.** Two runs of an identical pairing, and
the intervals barely touch. That is the finding, and it is about the
instrument rather than about B/2.

## What was actually wrong: the error bars, not the point

Refitting with the pooled B/2 leaves it 2.8σ off and the through-origin fit
still rejected (χ² = 10.9 on 3 dof, p ≈ 0.03). So pooling alone does not
rescue it.

The cause was already measured and already written down — in the previous
pre-registration, which reported that the clock arm's spend drifts run to run
(B/2: 3962 ± 210 nodes, 5.3%) and said in as many words that "the published
slope placed those points as though they were exact, so its interval is
narrower than it should be."

**I then applied that correction to the wrong quantity.** It went into a
resampling of the slope estimate, where it changed the interval by 1 Elo, and
not into the per-point errors — which is where it matters, because a
goodness-of-fit test compares residuals *to those errors*. A point whose
budget drifts by 5.3% has an extra ±13 Elo of uncertainty that no binomial
error bar contains.

Converting each point's measured spend drift into Elo through the slope and
adding it in quadrature:

| x | binomial | spend drift | combined | residual |
|---:|---:|---:|---:|---:|
| 0.341 | ±23 | ±7 | ±24 | −1.0σ |
| 0.605 | ±18 | ±13 | ±22 | −2.3σ |
| 1.608 | ±29 | ±9 | ±30 | +0.9σ |
| 2.037 | ±34 | ±0 | ±34 | +0.5σ |

**χ² = 7.4 on 3 dof, p ≈ 0.12. Nothing is rejected and nothing is discarded.**

## The answer

**−171 Elo per doubling, 95% interval [−194, −149]**, from all four clock
points with no exclusions, across 0.34 to 2.04 doublings.

The earlier "−158, valid only above 1.6 doublings" was the same data with one
point thrown out for not fitting error bars that were too small. The
restriction comes off; so does the caveat on every sub-doubling conversion.

| claim | doublings | conversion | measured directly |
|---|---:|---:|---:|
| atropos deficit | 2.60 | **−445** [−504, −386] | ≈ −440 ✓ |
| the +39% speedup | 0.48 | **+81** [+71, +92] | — |
| SEE pruning | 0.38 | **+66** [+57, +74] | +48 [+11, +87] ✓ |

Both independently measured checks now agree with the curve.

## What this cost, and what it bought

Four extra pairings — B/4, B/1.5, the B/2 replication, and the soft-node arm —
about 960 games, to end up 13 Elo per doubling from where two points started.

The number barely moved. What moved is what can be said about it: it now
rests on four points that agree, with the run-to-run drift of the apparatus
inside the error bars rather than masquerading as an outlier. The two-point
version could not have detected any of that, and would have kept quoting a
figure whose fit had never been tested.
