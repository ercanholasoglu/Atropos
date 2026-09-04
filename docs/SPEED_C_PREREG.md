# Pre-registration: a third point on the speed curve

Written before any game of it was played. Every number below either comes from
a measurement already in the repository or from a deterministic timing run
recorded here.

## What is being asked

Two points exist. Two points cannot tell a linearly decaying slope from an
exponentially damped one, so a third is commissioned at reference depth ~8–9,
with each model's prediction fixed in advance and a statement of which outcome
falsifies which.

## Measured before the run

Cost of a fixed depth, Level 7, instrument v2, four middlegame positions:

| depth | sec/move | nodes/move | × previous |
|---:|---:|---:|---:|
| 5 | 0.56 | 32,849 | — |
| 6 | 1.30 | 70,633 | 2.32 |
| 7 | 3.83 | 228,932 | 2.95 |
| 8 | 7.87 | 447,917 | 2.05 |

Depth reached at a clock budget, which is what the arm actually uses:

| movetime | mean depth | depths seen |
|---:|---:|---|
| 0.09 s | 2.75 | 3, 2, 3, 3 |
| 1.00 s | 5.50 | 6, 4, 6, 6 |
| 1.50 s | 6.00 | 6, 5, 6, 7 |
| 3.00 s | 6.50 | 7, 6, 6, 7 |
| 6.00 s | 7.25 | 8, 6, 7, 8 |
| 12.00 s | 7.75 | 8, 7, 8, 8 |

The 0.09 s and 1.00 s rows reproduce the reference depths of the two existing
points (3.0 and 5.6), which is the check that this timing method is the same
one those points were taken with.

## The anchors, and a discrepancy in them

| point | reference | depth | Elo per real doubling | source |
|---|---|---:|---|---|
| A | 0.09 s | 3.0 | **−171** [−194, −149] | `docs/SPEED.md` |
| A′ | 0.09 s | 3.0 | −162 [−198, −127] | `docs/LONG_TC_PREREG.md` |
| B | 1.00 s | 5.6 | **−129** [−151, −107] | `docs/LONG_TC_PREREG.md`, 450 games |

**Point A is quoted at two different values in this repository.** −171 is the
headline in `SPEED.md`; −162 is what `LONG_TC_PREREG.md` compared against, and
the 1.56σ non-separation reported there depends on using −162's wider interval.
This is recorded as a defect to fix, not silently resolved. Everything below is
computed under −171 with −162 as a sensitivity; the conclusion does not change
between them.

Under −171, A and B differ by **−42 ± 16.1, or 2.62σ**. Under −162, by
+33 ± 21.3, or 1.55σ. So whether the slope changes with depth at all is itself
either marginal or unresolved, depending on which value of A is used.

## The discrimination asked for cannot be made, and here is the arithmetic

Fitting both models through A and B and evaluating at the reference depth 12 s
reaches (7.75):

| model | prediction at depth 7.75 |
|---|---:|
| linear decay | **−94.3** |
| exponential decay | **−102.2** |
| **separation** | **7.9 Elo** |

Propagating the anchors' own uncertainty into each model by Monte Carlo
(200,000 draws):

| model | prediction | 95% interval |
|---|---:|---|
| linear | −94.3 ± 22.7 | [−139, −50] |
| exponential | −103.1 ± 17.4 | [−140, −72] |

**The models are 7.9 Elo apart and each is known to ±23.** The ratio of
separation to model uncertainty is 0.35. This is not a sample-size problem: no
number of games at point C fixes it, because the uncertainty is upstream, in
the two anchors the models are fitted from.

Nor is there a deeper reference that would work. The two curves stay within
~22 Elo of each other at depth 10 and only reach ~38 Elo apart at depth 12, and
depth 12 costs 33× depth 8 per move — hundreds of hours for one point.

**So the registered answer to "which outcome falsifies which model" is: no
outcome does.** Recording that before spending is the point of writing this
down first.

## What the third point does buy, and it is not nothing

**1. Whether the flattening continues at all.** Point C's predicted value
(≈ −94 to −103) sits about 70 Elo from point A's −171. With 100 games at the
longest lever the slope's standard error is 9.0, and A's is 11.5, so that
difference lands near 5σ. *This* is resolvable, and it is the question point B
was too close to A to settle.

**2. It halves the extrapolation.** The Python→Rust question asks for 8.5
doublings, which at the measured cost of ~2.4× per ply is about 7 plies, from
depth 3 to depth 10. Anchored on A and B, 4.4 of those plies are extrapolation
beyond anything measured. With C at 7.75, 2.25 plies are.

**3. It constrains both models rather than choosing between them,** which is
what shrinks the integrated answer below.

## The integrated answer, computed in advance under both models

8.5 doublings from the current operating point, integrating the slope as the
depth rises with it:

| anchor A | linear | exponential |
|---|---:|---:|
| −171 | **1,955** Elo [1,428, 2,482] | **1,016** Elo [817, 1,240] |
| −162 | 1,771 [1,003, 2,538] | 1,033 [822, 1,280] |

**Locally the models differ by 8 Elo; integrated over the substrate change they
differ by about 940.** That is the whole difficulty of this question in one
line, and it is why a point at depth 8 cannot settle it: the models agree where
they can be measured and disagree where they cannot.

What can be said without choosing: **the substrate change is worth of the order
of a thousand Elo at minimum**, which is larger than every other result in this
project combined, and its upper end is not pinned down.

## The design and its declared cost

| divisor | budget | expected depth | doublings | games |
|---|---|---:|---:|---:|
| B/8 | 1.50 s | 6.00 | 3.0 | **100** |
| B/2 | 6.00 s | 7.25 | 1.0 | **60** |

Reference **B = 12.0 s per move**, expected depth 7.75.

Cost, at ~79 moves per side per game: B/8 games cost 79 × 13.5 s = 1,066 s
each, B/2 games 79 × 18.0 s = 1,422 s each. Total **191,920 CPU-seconds =
53.3 CPU-hours ≈ 8.9 hours on six workers.**

Depth 9 was considered and is not run: ~19 s per move puts a B/8 game at
1,690 s, and 160 games at that reference is 15 hours, for an extra ply that
moves both model predictions by about 8 Elo — below what any of this resolves.
The previous pre-registration declined depth 9 at sixty hours; this declines it
at fifteen, with a better reason than cost.

Two divisors rather than one because the through-origin fit was *rejected* at
point A (χ² = 13.8 on 2 dof). It held at point B (χ² = 2.1 on 2 dof, p = 0.71),
and clock granularity — the cause at point A — is negligible at these budgets,
so it is expected to hold here. B/2 is the check that it does.

## What is registered as a falsifiable claim

Since the model discrimination is not available, the claim registered is the
one that is:

**The slope at reference depth 7.75 is shallower than at depth 3.0, and lies
between −70 and −120 Elo per real doubling.**

* **Inside [−70, −120]** → the flattening is confirmed and continues, and every
  "Elo per doubling" in this repository must carry the depth it was measured at.
* **Not distinguishable from −171** → the curve is flat across depth 3 to 7.75,
  and the flattening suggested by B was noise. Both existing points may then be
  quoted as one number.
* **Shallower than −60** → flattening faster than either model, and the
  integrated Rust estimate is an overestimate at both ends of the table above.
* **Steeper than −171** → nothing here predicts it and it would mean depth is
  worth *more* the more of it you have, which no published curve shows.

Resolution: 100 games at B/8 gives a slope standard error of 9.0, so the
measured interval will be about ±18. That separates −94 from −171 decisively
and cannot separate −94 from −102, as established above.
