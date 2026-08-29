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

---

## Result

Every adjacent pairing replayed at fixed length, 1,960 games.

| pairing | seq games | sequential said | fixed games | **measured** | 95% interval |
|---|---:|---:|---:|---:|---:|
| L2 vs L1 | 9 | +361 | 600 | **+420** | [+375, +479] |
| L3 vs L2 | 7 | +800 | 600 | **+684** | [+603, +833] |
| L4 vs L3 | 9 | +361 | 240 | **+390** | [+326, +482] |
| L5 vs L4 | 33 | +132 | 240 | **+149** | [+103, +200] |
| L6 vs L5 | 9 | +361 | 240 | **+527** | [+443, +682] |
| L7 vs L6 | 65 | +93 | 240 | **+22** | [−22, +66] |
| L8 vs L7 | 25 | −85 | 240 | **−25** | [−69, +19] |
| L4 vs L2 | — | — | 402 | +800 (at the ceiling) | 399-3-0 |

## The central prediction was wrong

It said **every accepted pairing would measure lower** than its sequential
figure. Four of the six measured **higher**. The prediction is falsified as
stated.

The failure is mine and not the simulation's. `docs/SPRT_BIAS.md` reports the
bias reversing above a true difference of about 100 — +28 at a true 50, −11 at
150, −17 at 200 — and I wrote the prediction as a blanket claim without
carrying my own table into it. Extending the simulation to the gaps the ladder
turned out to have:

| true difference | mean games to stop | reported given H1 | bias | **bias ÷ its own sd** |
|---:|---:|---:|---:|---:|
| 22 | 96 | +88 | **+66** | **1.54** |
| 149 | 41 | +139 | −10 | 0.18 |
| 390 | 14 | +368 | −22 | 0.17 |
| 420 | 14 | +400 | −20 | 0.14 |
| 527 | 12 | +507 | −20 | 0.12 |

That last column is the point. **For a small gap the bias dominates: it is one
and a half times the run-to-run spread, so the number is reliably wrong. For a
large gap the bias is nearly nothing but the spread is 133 to 168 Elo, because
the test stops after twelve to fourteen games.** Both make the reported figure
useless; the reasons are opposite.

Against that, the observed shifts behave:

| pairing | shift observed | simulation's bias | within noise? |
|---|---:|---:|---|
| L7 vs L6 | **+71** | **+66** | no — 1.7σ, this is the bias |
| L5 vs L4 | −17 | −10 | yes |
| L4 vs L3 | −29 | −22 | yes |
| L2 vs L1 | −59 | −20 | yes, 0.4σ |
| L6 vs L5 | −166 | −20 | yes, 1.0σ |

The one pairing where the shift is not noise is the one the whole exercise was
about, and there the simulation predicted +66 against +71 observed.

## The finding

**L7 vs L6 measures +22, interval [−22, +66].** At 0.1s per move, Level 7 is
not distinguishable from Level 6.

This is the fourth independent route to that answer, after the joint fit
(+50 [−3, +103]), the Stockfish cross-link (4 Elo apart), and the bias
simulation. The ladder's sequential run reported +93 and accepted "at least
100 Elo better".

It is also consistent with something the README has said all along: Level 7's
advantage is clock-dependent. At 0.1s both levels reach the same depth, so
pruning that buys depth buys nothing. The new measurement makes that sharper —
at this time control the gap is not merely small, it is not resolved from zero.

**L8 vs L7 measures −25, interval [−69, +19].** The interval still contains
zero, now on 240 games rather than 25. The correction stands: Level 8 is not
shown to be worse, and not shown to be better.

## The ladder, measured

Re-fitting every 0.1s game jointly — 5,375 games, fixed-length records
replacing the sequential ones for every pairing that has both — places all
eight rungs for the first time. The 7-0-0 sweep that made Levels 1 and 2
unplaceable is gone: 600 games produce losses, and a finite gap can be fit.

| gap | measured | 95% interval | nominal |
|---|---:|---:|---:|
| L1 → L2 | +444 | [+229, +660] | 300 |
| L2 → L3 | +703 | [+505, +902] | 300 — outside |
| L3 → L4 | +427 | [+251, +604] | 300 |
| L4 → L5 | +193 | [+33, +352] | 300 |
| L5 → L6 | +660 | [+546, +773] | 300 — outside |
| L6 → L7 | **+19** | **[−17, +55]** | 300 — outside |
| L7 → L8 | −35 | [−79, +9] | 300 — outside |

Four of seven gaps have 300 outside their interval. The real ladder rises
steeply at the bottom, flattens at Level 4, jumps again where quiescence and
the transposition table arrive, and then **stops**.
