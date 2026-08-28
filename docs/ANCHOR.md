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

Stockfish 18, fixed depth, against **Level 7** (nominal 2100), 0.1 s per move
on our side, 162 games each. `data/anchor_sf-d*_vs_L7.json`.

| opponent | games | score for Stockfish | Elo vs L7 | 95% interval | SPRT |
|---|---:|---:|---:|---:|---|
| Stockfish depth 1 | 162 | 47.5% | -17 | [-48, +13] | accept H0 |
| Stockfish depth 2 | 162 | 58.6% | +61 | [+23, +100] | accept H1 |
| Stockfish depth 3 | 162 | 60.2% | +72 | [+41, +104] | accept H1 |

Read plainly: **depth 1 is Level 7's equal** — the interval spans zero, so
there is no verdict either way — and depths 2 and 3 are above it by something
in the region of 60-70 Elo. Depths 2 and 3 are *not* distinguishable from each
other; their intervals overlap almost completely, and nothing here says the
third ply bought anything.

The whole span from depth 1 to depth 3 is about 90 Elo. That is much flatter
than a ply of search is worth in a normal engine, and the reason is the one
the scouting run already showed: Stockfish's "depth 1" is not a one-ply
search. It carries a full quiescence search and an NNUE evaluation underneath
it, so most of its strength is already present at the first ply and the next
two add comparatively little. **A depth number from one engine does not name
the same amount of work as the same number from another**, which is exactly
why these three points cluster instead of spreading.

## The check that was worth more than the anchor

One extra pairing: the *same* opponent, depth 1, against **Level 6** (nominal
1800). If the ladder's own units are meaningful, an outside ruler placed
against two rungs 300 nominal Elo apart should read 300 Elo apart.

| opponent | games | score | Elo vs rung | 95% interval |
|---|---:|---:|---:|---:|
| Stockfish depth 1 vs **L7** | 162 | 47.5% | -17 | [-48, +13] |
| Stockfish depth 1 vs **L6** | 162 | 46.9% | -21 | [-52, +9] |

Differencing the two: **L7 - L6 = -4 Elo**, standard error 22,
95% interval **[-47, +39]**.

The nominal gap is **300**. That is 14 standard errors outside the
measured interval. The external ruler does not find the gap the labels claim.

This is not the outside instrument disagreeing with the inside one. The
ladder's own head-to-head says the same thing and always did:
`data/sprt_L7_vs_L6.json` is 65 games at the same 0.1 s, **+93 Elo, interval
[+21, +174]** — also nowhere near 300. The two measurements overlap in the
region of +20 to +40 Elo, and the honest summary is that the gap between the
top two rungs is somewhere between nothing and a few tens of Elo.

**Where the 300 came from.** Nowhere. `INITIAL_ELO` assigns 200/600/900/1200/
1500/1800/2100/2400 at construction, and those numbers have never been
anything but names. Every rung-to-rung SPRT in this project ran with the
bracket `elo0=0, elo1=100`, so "accept H1" on a rung pairing means *the gap
looks more like 100 than like 0* — it was never a test of 300 and cannot be
read as confirming one. The ladder is ordered, and that ordering is verified.
Its spacing is not.

**What this does to the anchor.** It makes the offset the smaller problem. A
ladder that is uniformly wrong by a constant can be fixed by one external
number; a ladder whose spacing is compressed relative to its labels cannot,
because there is no single constant to apply. So the mapping below is stated
for **Level 7 only**, the rung actually measured, and no rung's nominal number
should be carried into an absolute claim without being measured the same way.

## The mapping

Given an assumed absolute rating **R(d)** for Stockfish 18 at fixed depth *d*
on this hardware, Level 7's absolute rating is:

| from | Level 7 absolute | statistical uncertainty |
|---|---|---|
| depth 1 | R(1) +17 | +/-30 |
| depth 2 | R(2) -61 | +/-39 |
| depth 3 | R(3) -72 | +/-31 |

The three rows are consistent with each other only if R(2) and R(3) sit about
60-70 Elo above R(1), which is a claim about Stockfish, not about this engine,
and this repository has not measured it.

**R(d) is unknown, and the uncertainty on it is not the +/-30 in that table.**
Those are the statistical part, and more games would shrink them. The part
that dominates is the one no amount of play here can reduce, and it is set out
below.

## The part that is an assumption

**Converting the measurement to absolute Elo requires a published rating for
Stockfish at these fixed depths, and this repository cannot establish one.**

This is the dominant term, and unlike the intervals above it is not
statistical — more games will not reduce it. It has three parts:

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
