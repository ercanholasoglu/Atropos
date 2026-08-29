# Pre-registration: measuring the ladder's gaps instead of its ordering

Committed before the first game.

## Why

`docs/SPRT_BIAS.md` established that a number quoted from an early-stopped
sequential test is approximately a constant — about +110 whether the true
difference is 0 or 100. Every Elo figure in the ladder table came from such a
run. The **verdicts** survive; each rung really is above the one below. The
**magnitudes have never been measured at all.**

`docs/RATING_FIT.md` partly filled the gap by fitting every recorded game at
once, but three of its five rung gaps carry intervals hundreds of Elo wide,
because they rest on 7 to 33 games, and Levels 1 and 2 could not be placed at
all: their only link is a 7-0-0 sweep whose likelihood has no maximum.

This replaces the sequential runs with fixed-length ones.

## Design

Every adjacent pairing, **fixed length, no stopping rule**, 0.1s per move,
same opening book and colour alternation as every other match here.

| pairing | games | why this many |
|---|---:|---|
| L2 vs L1 | 600 | 0.03 s per game — precision is free here |
| L3 vs L2 | 600 | same; also the pairing whose 7-0-0 broke the joint fit |
| L4 vs L3 | 240 | ~7 min |
| L5 vs L4 | 240 | ~7 min |
| L6 vs L5 | 240 | ~6 min |
| L7 vs L6 | 240 | ~10 min, the most expensive and the most contested |
| L8 vs L7 | 240 | ~12 min |
| **L4 vs L2** | 400 | a skip-one cross-link, cheap, to condition the lower chain |

240 games gives about ±45 Elo, which resolves any gap of the size these rungs
plausibly have. 600 on the cheap pairings costs minutes and removes the
separation problem — a rung that wins 95% of 600 games still loses some, and a
finite gap can then be fit.

The cross-link is included because the one that already existed proved to be
the most informative measurement in the project: Stockfish playing both L6 and
L7 said more about that gap than either ladder match did. The lower chain has
no such link, and `L4 vs L2` is the cheapest one that spans two rungs.

## Predictions

**The central claim, falsifiable:** every accepted pairing will measure
**lower** than its sequential figure, because that figure was produced by a
rule that reports about +110 regardless. Specifically:

| pairing | sequential said | fixed-length prediction |
|---|---:|---|
| L2 vs L1 | +361 | lower |
| L3 vs L2 | +800 | finite, and far below the ceiling |
| L4 vs L3 | +361 | lower |
| L5 vs L4 | +132 | near or below; this one ran 33 games, less bias |
| L6 vs L5 | +361 | lower |
| L7 vs L6 | +93 | **near +50**, matching the joint fit |
| L8 vs L7 | −85 | interval containing zero, as before |

**Falsified if** the pairings come back at or above their sequential figures.
That would mean the simulation in `docs/SPRT_BIAS.md` does not describe what
these runs actually did, and the simulation would be the thing to re-examine.

L7 vs L6 is the sharp test: the joint fit says +50 [−3, +103], the sequential
run said +93, and the two accounts differ by more than the fixed-length
interval will be wide.

**L8 vs L7 is not part of the central claim.** It accepted H0, a different
regime, and the prediction there is only that the interval still contains
zero — which is what the README has said since the correction.

## Afterwards

The joint fit is re-run over the new games and the ladder table is replaced:
measured gaps with intervals, in place of numbers that meant "the test stopped
here". The nominal `INITIAL_ELO` targets stay, labelled as the specification
they are.
