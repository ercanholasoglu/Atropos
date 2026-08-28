# Anchoring the ladder to an outside reference

Every rating in this project is in the ladder's own nominal units. Level 5 is
called 1500 because that is what it was *named*, not because anything measured
it. The rungs are verified relative to each other — sequentially, with
intervals — so the ladder is internally consistent. It could still be
uniformly wrong by several hundred Elo, and nothing inside it would show that.

Atropos did not fix this: it has no published rating either, so calibrating
against it moved a number from one unmeasured scale to another.

## What was measured

Stockfish 18 at **fixed depth**, against **Level 7**, both sides on the
operating point every other measurement in this project used (0.1s per move
for our side; Stockfish is depth-limited, not time-limited).

Two decisions, made before any games:

**Fixed depth, not `Skill Level`.** Skill Level makes Stockfish blunder on
purpose. The levels are not evenly spaced in Elo, and the deliberate mistakes
add variance that has nothing to do with the strength being measured. A fixed
depth is a fixed, reproducible opponent.

**One reference rung, not one per depth.** The ladder's own pairings are
already sequentially verified, so anchoring a single rung anchors all of them.
Measuring each Stockfish depth against the same level keeps the estimates on
one scale instead of chaining three separate comparisons and accumulating
their errors.

A minimum of 160 games runs before the sequential stopping rule is allowed to
fire. An anchor needs an *interval*, and a test that stops at twenty games
gives one hundreds of Elo wide.

## The measurement

See `data/anchor_sf-d*_vs_L7.json` and the table in the README. Those numbers
are measured and stand on their own.

## The part that is an assumption

**Converting the measurement to absolute Elo requires a published rating for
Stockfish at these fixed depths, and this repository cannot establish one.**

That is the whole of the uncertainty, and it is not statistical — more games
will not reduce it. It has three parts:

1. **Fixed-depth Stockfish is not a rated configuration.** CCRL, CEGT and the
   other rating lists test engines at *time controls*, not at depth 1. A depth
   limit makes the engine reproducible but takes it outside every published
   list.
2. **Depth is not comparable across engines.** Stockfish's depth 1 includes a
   quiescence search and an NNUE evaluation; ours does not. Scouting put all
   three of its low depths inside a two-rung band of our ladder, which is what
   that incomparability looks like from the outside.
3. **Hardware and build matter less here than usual, but not zero.** A depth
   limit removes most of the machine-speed dependence, which is the one thing
   in this anchor's favour.

So the mapping below is stated as a *conditional*: given an assumed absolute
rating **R** for the Stockfish configuration used, the ladder's Level 7 sits at
**R − (measured Elo difference)**, with the measured interval carried through.
Substituting a better value for R corrects every number without re-running
anything.

## How to make this an actual absolute anchor

One of:

* Play a **rated** engine at a **rated time control** — a CCRL-listed engine
  at, say, 40 moves in 15 minutes — and take the rating from the list.
* Play on Lichess with the bot API, where the rating pool does the calibration
  and the result is a real, if pool-specific, number.

Both are more work than this, and both produce a number that can be quoted
without a footnote. What is here should be quoted *with* one.
