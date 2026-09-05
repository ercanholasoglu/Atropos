# The speed curve's third point

Results for `docs/SPEED_C_PREREG.md`, which was committed before any of these
games were played.

## The point

Reference **12.0 s per move**, which reaches depth **7.75** (measured before the
run, and recorded in the pre-registration).

| divisor | budget | doublings | games | Elo for the slowed side | se |
|---|---|---:|---:|---|---:|
| B/2 | 6.00 s | 1.0 | 60 | −94.9 [−195.8, −7.9] | 47.9 |
| B/8 | 1.50 s | 3.0 | 100 | −168.4 [−254.7, −98.1] | 40.0 |

Through-origin fit: **−58.9 ± 12.8 Elo per doubling**, interval [−84.1, −33.8].
χ² = 0.61 on 1 degree of freedom — the linearity check the second divisor was
there to perform **holds**. (It was rejected at point A, where clock granularity
distorted the real speed ratios; at these budgets that effect is negligible, as
predicted.)

## The curve, three points

| point | reference | depth | Elo per doubling | se |
|---|---|---:|---:|---:|
| A | 0.09 s | 3.00 | −171.0 | 11.5 |
| B | 1.00 s | 5.60 | −129.0 | 11.2 |
| **C** | **12.0 s** | **7.75** | **−58.9** | **12.8** |

| separation | difference | σ |
|---|---:|---:|
| A vs B | −42.0 ± 16.1 | 2.6 |
| **B vs C** | **−70.1 ± 17.0** | **4.1** |
| A vs C | −112.1 ± 17.2 | 6.5 |

**B vs C is the first adjacent pair on this curve that resolves.** A vs B never
did — it was the 1.6σ that `docs/LONG_TC_PREREG.md` had to report as
unresolved. The flattening is now established, not suggested.

## Against what was registered

| registered claim | outcome |
|---|---|
| shallower at depth 7.75 than at depth 3.0 | **confirmed, 6.5σ** |
| the slope lies in [−70, −120] | **missed** — −58.9, shallower than the band |
| not distinguishable from −171 → curve is flat | rejected at 6.5σ |
| shallower than −60 → faster than either model | point estimate is here, **interval does not exclude the band** |
| steeper than −171 | no |

The direction was right and the magnitude band was not. −58.9 sits just past the
shallow edge of the registered band, and its interval [−84.1, −33.8] still
covers −70 to −84, so *how much* shallower is not resolved. Recorded as a miss
rather than rounded into the band.

**A second registered number was also wrong.** The pre-registration declared a
slope standard error of 9.0 from 100 games at the longest lever, scaled from
point B's realised precision. The realised error is **12.8**. Games at a 12 s
clock are noisier than games at 1 s, and the scaling did not anticipate that.

**What the pre-registration got right was the negative claim.** It said no
outcome would falsify either model, and none did: fitted to all three points,
linear gives χ² = 1.86 and exponential χ² = 4.02, both on 1 degree of freedom.
Neither is rejected.

The decline *looks* like it is accelerating — −16.2 Elo per doubling per ply
between A and B, −32.6 between B and C — but that difference is **+16.5 ± 10.0,
or 1.64σ, and does not resolve**. It is consistent with a steepening curve and
equally consistent with a constant one. No verdict.

## What a doubling buys, measured

The integral needs to know how much depth a doubling of clock actually adds.
From the six budgets timed before the run:

    depth = 5.379 + 0.714 × log₂(seconds per move)

| movetime | measured depth | fitted |
|---:|---:|---:|
| 0.09 s | 2.75 | 2.90 |
| 1.00 s | 5.50 | 5.38 |
| 1.50 s | 6.00 | 5.80 |
| 3.00 s | 6.50 | 6.51 |
| 6.00 s | 7.25 | 7.23 |
| 12.00 s | 7.75 | 7.94 |

**A doubling buys 0.714 ply**, not the 0.85 that a first pass at this
calculation assumed. The difference matters: a smaller figure keeps the engine
in the steep part of the curve for longer, and raises the integral.

## The answer to the substrate question

8.5 doublings, integrating the fitted slope as the depth rises with it, which
takes the engine from depth 3.0 to **depth 9.07**:

| model | before point C (two anchors) | **after point C** |
|---|---:|---:|
| linear | 1,955 [1,428, 2,482] | **911** [789, 1,032] |
| exponential | 1,016 [817, 1,240] | **968** [843, 1,110] |

**Across both models: 939 Elo, 95% interval [806, 1,086].**

This is what the third point was for, and it is not what it was commissioned
for. It did not choose between the two models — the pre-registration said in
advance that it could not, and it could not. What it did was **make the choice
stop mattering**: the two models disagreed by a factor of two before it and by
6% after, with overlapping intervals.

The other thing it bought is that most of the answer is now measured rather than
extrapolated. Of the 939 Elo, **814–827 falls inside the range where the curve
has been measured** (depth 3.0 to 7.75, 6.65 doublings); only about 1.85
doublings, roughly 125 Elo, is extrapolation. Anchored on A and B alone, 4.4
plies of the answer were beyond any measurement.

One caution on the linear fit: extended, it reaches zero at depth 10.69, which
is only 1.6 plies past the end of the extrapolation. A curve that says extra
speed becomes worth exactly nothing at depth 10.7 is not credible as physics;
it is credible as a straight line fitted over a range where the truth is a
decaying curve. The exponential's 968 is the more plausible of the two for that
reason, and the honest quote is the range that contains both.

## Still open

**Point A is quoted at two values in this repository** — −171 [−194, −149] in
`docs/SPEED.md` and −162 [−198, −127] in `docs/LONG_TC_PREREG.md` — and the
underlying real-doubling data needed to refit it is not in
`data/speed_elo_movetime.json`, which stores nominal doublings only. Everything
above uses −171; under −162 the A vs C separation is 5.5σ instead of 6.5σ and
the integrals move by less than their own intervals. Logged, not resolved.

Reproduce:

    python -m scripts.speed_elo --arm movetime --base-movetime 12.0 \
        --divisors 8 --only 8 --games 100 --workers 6 --out data/speed_elo_pointC.json
    python -m scripts.speed_elo --arm movetime --base-movetime 12.0 \
        --divisors 2 --only 2 --games 60 --workers 6 --out data/speed_elo_pointC_b2.json
