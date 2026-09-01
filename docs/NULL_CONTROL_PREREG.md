# Pre-registration: does the harness return zero when there is nothing there?

Committed before the games.

## Why this was never run, and should have been

Every measurement in this project assumes the match harness is unbiased —
that colours alternate fairly, that the opening book is balanced, that seeds
do not favour one side, and that the scoring path does not tilt. **Nothing has
tested that assumption.** Fifteen thousand games have been played on an
instrument whose zero was never checked.

The question surfaced sideways. The joint fit places `L8-uniform` 49 Elo below
`L7`, and those two are functionally the same engine at a time limit: Level 8
with its adaptive clock switched off has Level 7's search, Level 7's
evaluation, and a `max_depth` of 9 against 8 that never binds because both run
out of clock at depth 3. I flagged the 49 as an anomaly and then checked its
error: **±51, comfortably containing zero.** The flag was premature.

But the underlying question is not. A null control is the cheapest possible
test of an instrument and this one has never had it.

## The measurement

**`L7` against `L7`, 600 games, fixed length, no stopping rule**, same opening
book, same colour alternation, same seeds-from-game-index as every other match
here. The two sides differ in nothing except the seed offset the harness
already applies to distinguish them.

## Prediction

**0 Elo, interval about [−28, +28].**

* **Interval contains zero** → the harness has no measurable tilt at this
  resolution, and every result taken on it keeps its meaning.
* **Interval excludes zero** → there is a bias in the harness of the same
  order as the effects this project has spent fifteen thousand games chasing,
  and **every number here needs re-examining**, starting with the ones where
  the sides were not symmetric.

**Falsified if** the result lands outside [−60, +60], which nothing in the
design allows for.

## What it can and cannot catch

It catches a systematic tilt: unequal colours, an opening book that favours
White, a scoring bug, a seeding scheme that makes one side stronger.

It cannot catch a bias that affects both arms equally — a book that is simply
unrepresentative of real chess would not show up, because both sides play it.
Nor does it validate the Elo conversion, only the score it is fed.

A null result here is not a certificate. It is the absence of the one failure
mode that would invalidate everything at once.

---

## Result

**600 games, L7 against L7: 51.50%, +10.4 Elo, interval [−17, +38].**

| | |
|---|---|
| prediction | 0 Elo, interval about [−28, +28] |
| measured | +10.4, [−17, +38] |
| contains zero | **yes** |
| falsification bounds [−60, +60] | not reached |
| raw score against 0.5000 | z = +0.73, **p = 0.46** |

W-D-L for the first-listed side: **234-150-216**.

The raw-score test is the one that matters, because it does not pass through
the Elo conversion: 51.5% against a true 50% on 600 games is less than one
standard error away. **The harness has no measurable tilt at this resolution.**

## What that licenses, and what it does not

It licenses the results. A systematic bias in colour alternation, the opening
book, the seeding or the scoring path would have shown here at the same order
of magnitude as the effects this project spent its games chasing — SEE's +50,
the ladder's +18 at the top, the evaluation terms' +10 to +25. **None of those
would survive a harness tilted by even half of what this run rules out.**

It does not license everything. The interval is ±28: a tilt of 10 or 15 Elo
would not have been caught, and the smallest effects measured here are of that
size. It also cannot see a bias that affects both arms equally — an
unrepresentative opening book is invisible to it, because both sides play the
same book.

**A null result is not a certificate.** It is the absence of the one failure
mode that would have invalidated everything at once, measured rather than
assumed.

## The mistake that produced it

This run exists because I flagged a 49-Elo gap between two engines that are
functionally identical, and checked its error afterwards rather than first:
±51, comfortably containing zero. The flag was wrong.

The question it accidentally raised was the useful part. Fifteen thousand
games had been played on an instrument whose zero had never been checked, and
nobody — including me, through this whole session of measuring everything
else — had thought to check it.
