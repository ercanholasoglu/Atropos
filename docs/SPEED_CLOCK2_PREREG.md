# Pre-registration: the point that decides whether B/2 was a bad point

Committed before the games it describes. This is the pairing
`docs/SPEED_CLOCK_PREREG.md` named as the next thing the clock arm needs.

## The question

Three clock points rejected a line through the origin (χ² = 13.8 on 2 dof,
p ≈ 0.001). The entire misfit is **B/2**, sitting 92 Elo below the line while
B/4 and B/8 sit on it. A line with an intercept fits comfortably
(`Elo = −144 − 80x`), but an intercept means the slowed side pays a fixed
penalty the moment its clock is divided at all — which nothing here explains,
and the obvious candidate (spend variance) is contradicted by B/8 having the
widest spread and lying on the line.

Two readings remain, and they differ in what the whole arm means:

* **B/2 is one bad point.** The clock arm is a line through the origin at
  about −158, and one measurement missed.
* **There is a real offset.** Dividing the clock costs something fixed on top
  of the nodes it removes, and the "Elo per doubling" summary is wrong for
  small changes — which is exactly where the +39% speedup and SEE conversions
  sit.

## The point that separates them

**B/1.5 — clock 60 ms.** Measured spend **4754 nodes/move (sd 142 over five
repetitions, range 4096–6144)**, which is **0.370 doublings** below the
reference. That lands between the origin and B/2 at 0.61, where the two
readings are furthest apart.

Why not the alternatives, decided before running and from measurement:

| divisor | ms | nodes | doublings | |
|---|---:|---:|---:|---|
| B/1.25 | 72.0 | 5972 | 0.041 | too close to the reference to carry information |
| **B/1.5** | **60.0** | **4754** | **0.370** | **chosen** |
| B/1.75 | 51.4 | 4069 | 0.594 | a duplicate of B/2 at 0.610 |

## Prediction

At 0.370 doublings:

* **line through the origin (−158):** −58 Elo
* **offset model (−144 − 80x):** −174 Elo

**115 Elo apart.** 240 games gives about ±45, so this separates them at better
than two standard errors — a real test rather than a gesture.

**Falsified if** the point lands outside both, below −219 or above −13, in
which case neither reading survives and the clock arm is not described by any
straight line at all.

## Consequences, fixed now

* **Near −58** → B/2 was a bad point. −158 [−182, −135] applies across the
  arm, the speedup converts to about +75 and SEE to about +61, and the caveats
  currently attached to both come off.
* **Near −174** → the offset is real. A single Elo-per-doubling figure is
  wrong for small speed changes, the speedup and SEE conversions are
  unusable as stated, and every downstream number under about one doubling has
  to be re-derived or withdrawn.

Both outcomes change what this project claims, which is the point of running
it.

## The test

    python -m scripts.speed_elo --arm movetime --workers 6

with `DIVISORS_MOVETIME = (1.5, 2, 4, 8)`. The three existing pairings resume
untouched; only B/1.5 is played. 240 games, fixed length, no stopping rule,
same operating point and opening book as every other pairing here.
