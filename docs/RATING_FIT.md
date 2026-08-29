# Fitting the whole ladder at once

Every rating in this project came from one pairing at a time. That answers
"is this rung above that one" and leaves two things on the table: a chain of
pairwise gaps accumulates the error of every link, and it throws away
measurements that connect rungs *without* being adjacent.

There is one of those. **Stockfish at fixed depth 1 played both Level 6 and
Level 7**, 162 games each, and what it says about the gap between them is
independent of the ladder match that also measures it.

`elo/joint.py` fits every engine's rating simultaneously by maximum
likelihood over every game recorded at 0.1s per move — 2,730 games across 17
pairings. Rao-Kupper three-outcome model, one shared draw parameter, one
engine held at zero as a gauge.

## The one number this was worth running for

| how the L7-over-L6 gap is computed | Elo |
|---|---:|
| score only, draws ignored — what this project used | **+93** |
| the same 65 games, with a draw model fitted to them | +100 |
| every 0.1s game jointly, Stockfish included | **+50** [−3, +103] |

The model change does almost nothing. **The move comes from the cross-link.**

| | W-D-L | score | Elo |
|---|---:|---:|---:|
| Stockfish d1 vs L7 | 22-110-30 | 47.5% | −17 |
| Stockfish d1 vs L6 | 21-110-31 | 46.9% | −21 |

An outsider that played both puts them **4 Elo apart**. The ladder's own match
says 93. Pooling all of it lands at 50, with an interval that **includes
zero**.

So the top rung transition — the one pairing in the ladder that needed 65
games to settle, and the one whose result depends on the clock — is not
resolved after all. It was resolved against *one* opponent. A second opponent
that played both sides disagrees, and the disagreement is larger than either
measurement's error bar.

## What the fit does not settle, and why

**A single draw parameter does not describe this pool.** The draw rates run
from 0% to 68%:

| pairing | games | draws | rate |
|---|---:|---:|---:|
| sf-d1 vs L6 / L7 | 162 | 110 | 68% |
| sf-d3 vs L7 | 162 | 105 | 65% |
| sf-d2 vs L7 | 162 | 78 | 48% |
| L7 vs L6 | 65 | 16 | 25% |
| L8 vs L7 | 25 | 3 | 12% |
| L6 vs L5 | 9 | 0 | 0% |

Fixed-depth Stockfish plays extremely consistently and draws two games in
three; the ladder's own pairings draw a quarter or fewer. One parameter
averaging over that is misspecified, and the script says so on every run.

That matters most for **Level 8**. The joint fit reports L7→L8 as −143
[−290, +3], and it would be easy to read that as finally confirming the
"Level 8 is a regression" claim this project withdrew. **It does not, and it
should not be used that way.** Fitted to its own 25 games the number is −86,
essentially the −85 the score-only method gave; the shift to −143 comes from
imposing a pooled draw parameter of 188 on a pairing whose own draw rate
implies about 45. The interval still contains zero either way.

Level 8 remains what the correction in the README said it was: **not shown to
be worse, not shown to be better.**

## The rung the data cannot place

**L3 vs L2 was 7-0-0.** No losses, no draws, so the likelihood rises without
bound as the gap grows, and the maximum is at infinity. Seven straight wins
are consistent with "better by 200" and with "better by 2000".

That single link is the only path from L1 and L2 to the rest of the ladder,
so those two rungs are **not on this scale at all**. What can be said is one
sided: the gap is **+109 Elo or more** at 95%, with no upper bound.

This is not a defect in the fit. It is seven games being asked to do a job
that needs more than seven games, and the fit refusing to invent the rest.

## The measured scale

Gauge: L7, placed at its nominal 2100 so the column is readable. **That 2100
is a label, not a measurement** — the scale has no absolute zero (see
`docs/ANCHOR.md`), so only the gaps below carry meaning.

| rung | measured | ± | nominal | difference |
|---|---:|---:|---:|---:|
| L3 | 936 | 241 | 900 | +36 |
| L4 | 1348 | 197 | 1200 | +148 |
| L5 | 1521 | 188 | 1500 | +21 |
| L6 | 2050 | 27 | 1800 | **+250** |
| L7 | 2100 | — | 2100 | gauge |
| L8 | 1957 | 75 | 2400 | **−443** |

| non-rungs | measured | ± |
|---|---:|---:|
| Stockfish d1 | 2052 | 22 |
| Stockfish d2 | 2179 | 26 |
| Stockfish d3 | 2184 | 24 |
| L7 + SEE pruning | 2174 | 23 |
| L8 without its adaptive clock | 1935 | 90 |

L7-with-SEE lands 74 Elo above L7, against the 48 [+11, +87] measured
directly in 240 games — an independent route to the same answer, from a fit
that also had to accommodate every other pairing.

| gap | measured | 95% interval | nominal |
|---|---:|---:|---:|
| L3 → L4 | +412 | [−198, +1022] | 300 |
| L4 → L5 | +173 | [−360, +707] | 300 |
| L5 → L6 | +529 | [+157, +901] | 300 |
| L6 → L7 | **+50** | [−3, +103] | 300 — outside |
| L7 → L8 | −143 | [−290, +3] | 300 — outside |

Three of the five gaps have intervals hundreds of Elo wide, because they rest
on 7 to 33 games. The ladder was verified with a sequential test that stops as
soon as it can answer "is this one above that one", and that is all those
games can support. **An ordering is cheap; a scale is not.**

## Running it

    python -m scripts.rating_fit
    python -m scripts.rating_fit --gauge L6 --draw-elo 250

Only 0.1s pairings are pooled. The calibration gauntlets ran at 0.3s and an
engine's rating is not the same number at two time controls; mixing them would
produce a scale describing neither.
