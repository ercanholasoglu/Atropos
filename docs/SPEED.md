# What a doubling of speed is worth

Every optimisation in this project was reported in nodes per second, which is
not a unit anyone cares about. This converts one to the other.

The brackets, the game counts, the predictions and the falsifiable claim were
committed before the first game was played (`b84fd6e`, sharpened in
`b46d86a`). Nothing below changed them.

## The result

Level 7 against a slowed copy of itself, 240 games per pairing, 960 games.
The slowed side's Elo, negative because it lost:

| budget | games | measured | 95% interval | predicted |
|---|---:|---:|---:|---:|
| B/2 | 240 | **−159** | [−212, −113] | −60 |
| B/4 | 240 | **−417** | [−518, −349] | −120 |
| B/8 | 240 | **−636** | [−911, −532] | −180 |
| B/16 | 240 | **−830** | [−2400, −678] | −240 |

**Slope: −207 Elo per doubling of the node budget, 95% interval
[−251, −164].**

That interval is not the one the least-squares fit reports. The fit says
±5, which treats the four points as exact; their own sampling errors run from
±25 at B/2 to ±153 at B/16. Propagating those through the fit gives [−251,
−164], and that is the number to quote.

## Against the prediction

Every point is outside its predicted interval, in the same direction, by a
factor of two and a half. The prediction came from published self-play
doubling curves for classical engines, which sit near 50–70 Elo. **This engine
is about three times as sensitive to speed as that literature suggests.**

The reason is visible in what the budgets buy. At the reference budget of 5000
nodes the search reaches depth 3.0; at B/2 it reaches 2.0, at B/8 1.6. The
published curves are measured at long time controls where a doubling adds a
ply to a search that already has fifteen. Here a doubling is the difference
between seeing a three-move tactic and not seeing it. **Elo per doubling is
not a constant of an engine, it is a property of the region of the curve you
measure in**, and this measurement is at the steep end.

Linearity, the pre-registered claim, holds: the residuals are +48, −2, −14, −1
against per-point errors of ±25 to ±153. Only the B/2 point sits away from the
line, and not by more than its own error. Whatever curvature exists is smaller
than this design can see.

## The cross-check that disagreed

The same halvings were also run as *movetime* divisions, on the prediction
that the two methods are two spellings of the same slowdown.

| budget | node arm | movetime arm |
|---|---:|---:|
| B/2 | −159 [−212, −113] | −201 [−257, −153] |
| B/8 | −636 [−911, −532] | **−332 [−409, −273]** |

At B/2 they agree. At B/8 they do not overlap at all, and the movetime arm is
300 Elo stronger. **Two methods intended to be equivalent are not**, which is
the finding the cross-check existed to catch.

### Why: they are not dividing the same thing

The pre-registered guess was granularity — `SearchStats.check_interval` is
2048 nodes, so a clock cannot stop a search earlier than that inside an
iteration. Measuring what each budget actually spends shows that is part of it
and not the main part:

| arm | nominal | nodes actually searched | real division |
|---|---|---:|---:|
| nodes | B/1 | 5000 (min 5000, max 5000) | — |
| nodes | B/2 | 2500 (exact) | 1/2.0 |
| nodes | B/8 | 625 (exact) | 1/8.0 |
| movetime | B/1 | 6144 | — |
| movetime | B/2 | 3582 (min 3920, max 4096) | **1/1.7** |
| movetime | B/8 | 1485 (min 569, max 2048) | **1/4.1** |

A movetime division by eight is a node division by **four**. The clock was
never dividing the thing the experiment was varying. Two separate causes:

1. **The reference points differ.** 0.09 s buys 6144 nodes, not the 5000 the
   node arm starts from, so the movetime arm was slowed from a 23% higher
   base.
2. **The floor.** At B/8 the budget is 11 ms, and the spend runs from 569 to
   2048 nodes — the top of that range is exactly one check interval. The
   search cannot stop mid-iteration before 2048 nodes; only the
   between-iteration check stops it earlier. The nominal budget is below the
   resolution of the instrument enforcing it.

### What is left over after correcting for that

Put both arms on nodes actually searched and let the node arm's curve predict
the movetime arm:

| movetime budget | nodes | curve predicts | measured | 95% interval |
|---|---:|---:|---:|---:|
| B/2 | 3582 | −161 | −201 | [−257, −153] — consistent |
| B/8 | 1485 | −425 | −332 | [−409, −273] — **outside, by 16** |

B/2 is explained. B/8 is not: after correcting for node cost, the movetime arm
is still about 90 Elo stronger than the curve says it should be, and the
prediction falls outside the measured interval — though only just, by 16 Elo
on an interval 136 wide.

Two mechanisms could produce that and **this experiment does not separate
them**:

* A varying budget spent adaptively is worth more than a fixed one. The
  movetime arm spends 569 nodes on some moves and 2048 on others; the node arm
  spends exactly 625 on all of them. Spending unevenly across positions is the
  whole idea behind time management, and it would show up here as free Elo.
* A node limit truncates the search at an arbitrary point inside an iteration,
  discarding partial work; a clock checked between iterations more often stops
  at a boundary with a completed result.

Distinguishing them needs a third arm — a fixed node budget checked only at
iteration boundaries — which is not run here. **Recorded as an open question
rather than settled by picking whichever story sounds better.**

## What this means for the rest of the project

The +39% speedup shipped earlier is worth **207 × log2(1.39) = +98 Elo**,
interval [+79, +120].

That reframes two earlier results:

* The old note that a 1.39× speedup is "worth roughly +29 Elo by the usual
  rule of thumb" used the 50–70 Elo figure from the literature. Measured on
  this engine it is three times that. The conclusion drawn there — that the
  ten-game calibration could not have detected it — still holds, because ±110
  Elo of noise still swamps +98.
* Atropos runs at 8,938 nodes/second against this engine's ~54,000, which is
  2.6 doublings. At −207 per doubling that is **−537 Elo from throughput
  alone**, against a measured gap to Level 6 of about 440. The two agree to
  within the error on either, and no evaluation difference needs to be
  invoked to explain why an engine with feature parity loses.

## Reproducing

    python -m scripts.speed_elo --arm nodes --workers 6
    python -m scripts.speed_elo --arm movetime --workers 6

Both resume; `--minutes N` bounds a chunk. Data in
`data/speed_elo_nodes.json` and `data/speed_elo_movetime.json`, with run
telemetry (wall, CPU, nodes, peak RSS, commit) under `data/telemetry/`.
