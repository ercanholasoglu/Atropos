# Pre-registration: does a result survive changing the openings?

Committed before the games.

## The limitation this addresses

The null control showed the harness has no colour, seeding or scoring tilt, and
named what it could not see: **a bias affecting both arms equally**. An
unrepresentative opening book is exactly that. Both sides play it, so it
cancels in a null control and does not cancel in any claim that generalises.

Every match in this project — the ladder, the anchor, the calibration, the
speed curve, the evaluation A/Bs, SEE — started from the same **eight mainline
openings at ply 5-6**.

## The test

Re-measure the best-established effect on a different book.

**SEE pruning**, which measured **+50 [+30, +70]** over 1,200 fixed games on the
default book, played again on **`midgame`**: eight balanced middlegame
positions built by `scripts/build_book.py`, reached by the ladder's own play
from those openings, each verified by Stockfish to sit within 60 centipawns of
level so no game starts already won. **600 games**, fixed length, no stopping
rule, everything else identical.

## Prediction

The two books differ measurably in the one property SEE acts on. Counted, not
guessed:

| book | captures per position | as a share of legal moves |
|---|---:|---:|
| default (ply 5-6) | 1.00 | 0.031 |
| midgame (ply 31-44) | 2.12 | 0.051 |

**Twice the capture density at the start.** SEE prunes captures that lose
material to the recapture, so more captures is more to prune.

That said, the effect should be modest. Games from the default book run to 160
plies and spend most of their length in middlegames anyway; what changes is the
*fraction* of each game played at high capture density, not whether such
positions occur.

**Prediction: +50 to +75, interval roughly [+30, +95].** Same effect,
plausibly somewhat larger.

* **Interval overlaps [+30, +70] substantially** → the result generalises off
  its book, and the other measurements inherit that reassurance.
* **Clearly higher** → SEE is worth more where captures are dense, which is a
  real finding about when the pruning pays, and a warning that book choice
  scales effects.
* **Clearly lower, or containing zero** → **the book was carrying the result**,
  and every effect measured in this project needs re-examining on a second
  book before it can be quoted as a property of the engine.

**Falsified if** the result lands outside [0, +120].

## What a pass would and would not establish

It would show that one well-measured effect survives one change of book. That
is a single point, not a proof of representativeness — a book that is wrong in
some third way would not be caught by comparing it to a book derived from it.

The middlegame positions were *reached from* the default openings, so the two
books are not independent. A genuinely independent book would come from human
games or another engine's play. This is the cheaper test, and its weakness is
stated here rather than discovered later.
