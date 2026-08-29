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

---

## Result

**240 games, 27.9%, −165 Elo, interval [−213, −122].**

| account | predicted | inside the interval? |
|---|---:|---|
| clock-specific | −349 | no |
| boundary-stopping | −257 | no |
| measured | **−165** | — |

**Both pre-registered predictions failed, in the same direction.** The
falsification criterion committed above fires: neither account survives, and
the thing to re-examine is the node curve.

## Re-examining it

The soft arm plays 184 Elo better than the curve says its node count is worth.
The reason is measurable without playing anything:

| budget | enforcement | nodes spent | depth reached |
|---|---|---:|---:|
| 5000 | hard | 5000 | 3.00 |
| 2000 | soft | 3422 | 3.00 |
| 3000 | soft | 5419 | 3.38 |
| 5000 | soft | 13567 | 4.00 |

**The hard-limited reference burns 5000 nodes to reach a depth a soft budget
reaches on 3422** — 46% more nodes for the same search. A hard limit stops
part-way through an iteration and throws that iteration away, so a fixed
fraction of every hard budget is spent on work that is discarded.

That is true at every rung of the original experiment, not only at the
reference. So the −207 Elo per doubling was measuring two things at once: what
a node is worth, and what it costs to be truncated mid-iteration.

## What this does to the headline number

| how the budget is enforced | Elo per real doubling | 95% interval |
|---|---:|---:|
| hard node limit (4 points) | −207 | [−251, −164] |
| clock (2 points, at the doublings it actually delivered) | **−174** | [−203, −144] |
| soft node limit (1 point) | −98 | [−126, −69] |

The soft and hard intervals do not overlap; the clock sits between them and is
not separable from the hard arm. So what is established is that **enforcement
is a first-order variable in this measurement** — demonstrated between the
extremes — not a precise ordering of all three. The soft row is a single
pairing and its interval is that point's own error, not a fit.

**For converting a real speed change to Elo, the clock arm is the one to use**,
because stopping on a clock is what this engine and every engine it plays
actually does. A hard node budget is an experimental instrument, not a mode
anything runs in.

## The downstream numbers, recomputed

| claim | on the hard arm | on the clock arm | measured directly |
|---|---:|---:|---:|
| +39% speedup | +98 | **+83** [+69, +97] | — |
| atropos vs this engine (2.6 doublings) | −537 | **−451** [−375, −528] | ≈ −440 |
| SEE pruning (0.38 doublings) | +79 | **+67** [+55, +78] | +48 [+11, +87] |

The atropos row is the useful one: the clock arm predicts −451 against a
gauntlet measurement of about −440, where the hard arm predicted −537. An
independent check the hard arm was failing quietly.

The SEE row moves from +79 to +67, which is now comfortably inside the +48
[+11, +87] that was measured. The pre-registered SEE prediction was drawn from
the wrong arm; the conclusion recorded there — a null result on the magnitude
question — does not change, because +67 sits inside that interval too.
