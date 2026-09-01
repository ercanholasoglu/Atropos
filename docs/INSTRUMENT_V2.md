# Instrument v2: one cut, and what it moved

Two switches were thrown in a single commit (`alet-v2`): **SEE pruning on,
rook-on-open-file term out**. One cut rather than two, because changing them
separately means two re-anchorings and an undefined instrument in between.

Nothing was deleted. `positional_score_rooks` keeps the v1 evaluation, the v1
records live in `data/v1/`, and every number taken before the tag stays valid
for the engine it measured.

## The blast radius, measured rather than reasoned about

| levels | affected by | verified |
|---|---|---|
| L1–L4 | neither | **bit-identical** — the benchmark reports all 24 positions visiting the same nodes |
| L5 | the rook term only | node counts move slightly |
| L6–L8 | both | L7 searches **38% fewer nodes** at the same depth |

So the lower ladder needed no re-measurement, and the effort went where the
engine actually changed.

## What the cut did, measured directly

`L7-v2` against a rebuilt `L7-v1` — same process, same book, both instruments
in one match. The reconstruction was verified exact before any game: on a
position with a rook on an open file, v1 evaluates 530 and v2 evaluates 505,
matching `positional_score_rooks` and `positional_score` respectively.

**600 games: 61.33%, +80 Elo, interval [+52, +109].**

Against what `scripts/see_impact.py` predicted before the cut:

| prediction | value | inside the measured interval? |
|---|---:|---|
| joint fit | +62 | **yes** |
| direct SEE A/B | +50 | no |
| SEE plus removing the rook term | +48 to +64 | overlapping, both point estimates below |

**The cut is worth more than the sum of its parts as separately measured.**
That is a finding, not a rounding: SEE was measured on Level 7 carrying the
rook term, and the rook term was measured on Level 6's search, so the
combination on Level 7 had never been played until now.

## The ladder under v2

Every affected pairing, 240 fixed games, no stopping rule:

| pairing | instrument v1 | **instrument v2** |
|---|---:|---:|
| L5 vs L4 | +149 [+103, +200] | **+160** [+125, +206] |
| L6 vs L5 | +527 [+443, +682] | **+651** [+644, +1190] |
| L7 vs L6 | +18 [−18, +53] | **+41** [+3, +80] |
| L8 vs L7 | −32 [−75, +11] | **0** [−36, +36] |

**L7 over L6 is now clear of zero**, where under v1 it was not. The L5→L6 jump
grew, which is the two changes stacking in the same direction: L5 lost the rook
term while L6 gained SEE.

## The disagreement, and the mechanism behind it

The Stockfish anchor, re-run clean under v2, says something else.

| | v1 | v2 |
|---|---:|---:|
| SF-d1 vs L7 | −17 [−48, +13] | −9 [−44, +27] |
| SF-d2 vs L7 | +61 [+23, +100] | +85 [+52, +121] |
| SF-d3 vs L7 | +72 [+41, +104] | +48 [+20, +77] |
| SF-d1 vs L6 | −21 [−52, +9] | −32 [−69, +4] |

Pooling the three depths, the anchor says Level 7 changed by **+1 ± 14**. The
direct measurement says **+80**. The two routes differ by **78 ± 24, or 3.3σ.**

Two things are wrong with the anchor, and only one of them is fixable.

**First: it is internally incoherent.** d1 and d2 imply Level 7 got weaker, d3
implies it got stronger. None of the three shifts is significant on its own
(0.3σ to 0.9σ). An instrument whose three readings disagree about the sign is
not measuring the change.

**Second, and more interesting: the conversion ignores draws, and these
pairings draw two games in three.** Simulated, at a true gap of 100 Elo:

| draw rate | what a score-only conversion reports |
|---:|---:|
| 0% | +100 |
| 49% | +74 |
| **67%** | **+52** |
| 80% | +34 |

The anchor pairings draw 56–68% of the time, so **every figure it has ever
published is compressed by roughly a factor of two.** Re-reading them with a
draw model: d1 goes −17 → −32, d2 +61 → +81, d3 +72 → +136.

That corrects the magnitudes and **does not fix the incoherence** — the implied
Level 7 changes become −20, −57 and +63, still scattered across the sign. At
162 games with that draw rate the anchor's resolution is worse than the change
it was asked to see.

**The direct measurement is the better instrument for this question**, and the
anchor's job is absolute placement rather than difference detection. Its
compression is now recorded in `docs/ANCHOR.md`.

## Against an external engine, nothing moved

atropos, 480 games at 0.3s:

| | v1 | v2 |
|---|---:|---:|
| vs L4 | 74.6% | 72.1% |
| vs L5 | 61.3% | 62.9% |
| vs L6 | 11.2% | 14.6% |
| vs L7 | 11.7% | 9.2% |
| **performance rating** | **1518** | **1518** |

Identical, and it should not be over-read either way: 120 games per rung is
±9% on the score, about ±65 Elo, and the gauntlet runs at 0.3s where the cut
was measured at 0.1s. **This instrument cannot see an 80-Elo change**, so its
agreement with v1 is not evidence against the direct measurement.

## The speed curve, re-measured

Required because SEE changes *which* nodes the search visits, so the v1 curve
described a different engine. Clock arm, four points, 960 games, spends
re-measured over five repetitions each:

| budget | nodes | doublings | Elo | ±y | ±x |
|---|---:|---:|---:|---:|---:|
| B/1.5 | 3,836 | 0.332 | −89 | 23 | 0.110 |
| B/2 | 3,139 | 0.621 | −144 | 24 | 0.141 |
| B/4 | 1,951 | 1.307 | −228 | 28 | 0.115 |
| B/8 | 1,342 | 1.846 | −205 | 27 | 0.307 |

**−162 Elo per doubling, interval [−198, −127]**, χ² = 6.1 on 3 dof with both
error sources carried, as v1 learned to do.

Against **v1's −171 [−194, −149]**: the intervals overlap almost entirely.
**The conversion did not move.** The engine got faster in absolute terms — the
reference now spends 4,827 nodes per move against v1's 6,144 for the same
clock, because SEE prunes — but what a doubling of budget is *worth* is
unchanged.

That is worth stating plainly: **the speed→Elo conversion survived a change to
the search it converts for.** It was not obvious that it would.
