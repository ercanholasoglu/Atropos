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
