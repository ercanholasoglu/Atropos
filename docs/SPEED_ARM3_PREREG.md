# Pre-registration: is the movetime bonus about the clock, or about where a search may stop?

Committed before any game of this arm was played.

## The open question this closes

`docs/SPEED.md` reported that a node budget and a clock, intended as two
spellings of the same slowdown, gave different strength — and that after
correcting for the nodes each actually spends, the movetime arm was still
about **+92 Elo** above what the node curve predicts for its node count. Two
candidate mechanisms were named there, and the document said the design did
not separate them.

## A correction to that document, made before running anything

The two candidates were **not independent, and naming them as alternatives was
a mistake.** They were:

1. a varying budget spent adaptively is worth more than a fixed one;
2. a node limit truncates mid-iteration and discards partial work, where a
   clock checked between iterations stops at a boundary.

Building the third arm shows why these are one thing. A budget enforced only
at iteration boundaries *necessarily* spends a variable number of nodes,
because iterations are not the same size. Stopping at a boundary is what
*creates* the variability. There is no arm that has one property without the
other, so no experiment could have adjudicated between them as posed.

This is recorded rather than quietly fixed: the original framing was wrong,
and the fix came from trying to build the apparatus, not from the data.

## The question that can be answered

**Is the bonus a property of the clock, or of being allowed to stop only at an
iteration boundary?**

The third arm removes the clock entirely and keeps the boundary-stopping:

* `L7-soft400` — node budget 400, enforced only between iterations. Measured
  spend **1556 nodes/move (min 569, max 3209)**, against the movetime B/8
  arm's 1485 (min 569, max 2048). The minimums agree exactly.
* Opponent: `L7-nodes5000` — the node arm's own reference, 5000 nodes,
  enforced at every node. No clock on either side.

Budgets of 300, 400 and 500 all produce the same 1556-node spend, because
iteration boundaries quantise it. That is the mechanism visible directly, and
it is why the exact budget is not a tuned parameter.

## Prediction

The node curve (−207 Elo per doubling) at 1556 nodes against a 5000-node
reference is 1.68 doublings: **−349 Elo**.

* **If the bonus is about boundary-stopping**, this arm scores about
  **−257** (−349 + 92).
* **If the bonus is clock-specific** — timing jitter, scheduler noise,
  something about wall-clock enforcement — this arm scores about **−349**.

The two are 92 Elo apart. 240 games buys about ±45, so this separates them at
roughly two standard errors: enough to distinguish, not enough to be
comfortable. Stated now so the result is not read as more precise than it is.

**Falsified if** the arm lands outside both, in which case neither account
survives and the node curve itself is the thing to re-examine.

## The test

    python -m scripts.sprt_match --a L7-soft400 --b L7-nodes5000 \
        --fixed --max-games 240

240 games, fixed length, no stopping rule — the deliverable is a magnitude,
and a sequential test biases the estimate away from zero. Same opening book,
same colour alternation as every other pairing here.
