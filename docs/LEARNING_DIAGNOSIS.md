# Why the learning curve falls after 3,000 games

Four hypotheses, taken in the order set out in the brief. Two of them needed no
games at all. Results for `docs/COLLAPSE_PREREG.md`.

## 1a. Is the peak real? Yes — and it was already in the data

The curve is four points, each 1,000 match games against the hand-written
tables at 0.2 s per move. Against a common opponent, the differences:

| step | difference | 95% interval | σ |
|---|---:|---|---:|
| 1,000 → 3,000 | **+67.6** | [+36.9, +98.3] | 4.3 |
| 3,000 → 10,000 | **−73.7** | [−104.4, −42.9] | 4.7 |
| 10,000 → 30,000 | **−129.5** | [−162.7, −96.2] | 7.6 |

Both the rise and the fall exclude zero. About 700 games per point would have
been enough; 1,000 were played. **No games were spent on this question** — the
answer was already bought, and the brief's instruction was to check before
hunting hypotheses.

## 1b. Overfitting? Not supported

Validation set: 200 human games from the **Lichess January 2013 database dump**
— a decade older than this project, no path into training — filtered to both
players ≥1800 and 30–120 plies (`scripts/validation_set.py`). Scored with the
same loss the training reports: values at the leaf of the same depth-2 search,
the last anchored to the actual result, mean |TD|.

| training games | weight L2 | value scale | train \|TD\| | valid \|TD\| | terminal error | sign agreement | correlation |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 9035 | 0.3535 | 0.1185 | 0.2459 | 0.5206 | 65.1% | 0.252 |
| 3,000 | 9002 | 0.3423 | 0.0758 | 0.2325 | 0.5299 | 65.0% | 0.267 |
| 10,000 | 8869 | 0.3262 | 0.0711 | 0.1938 | 0.5367 | 64.4% | 0.254 |
| 30,000 | 8483 | 0.3155 | 0.1523 | 0.1590 | 0.5478 | 64.3% | 0.281 |

Read the second column before the fifth. **Validation |TD| falls, and that
number means nothing on its own**: the value function is shrinking, and a
smaller value function makes every temporal difference smaller for free. The
measures that are scale-free, or that move the other way under shrinkage, tell
the real story — the terminal error rises monotonically (0.5206 → 0.5478,
exactly what shrinking values do to the distance from a ±1 result), while sign
agreement and correlation are flat and neither of their changes is resolved.

Overfitting means validation performance degrades. It does not degrade. It does
not improve either. **Eliminated.**

## 1c. Divergence? Not in its classic form — but the scale collapses

The deadly triad's signature is weights growing without bound. They shrink:
L2 9035 → 9002 → 8869 → 8483.

What is happening instead is a monotone collapse of every piece value toward
zero, ordered by piece:

| piece | reference | 1,000 | 3,000 | 10,000 | 30,000 | change |
|---|---:|---:|---:|---:|---:|---:|
| pawn | 100 | 89.2 | 80.2 | 64.9 | 57.9 | **−42%** |
| knight | 320 | 317.2 | 311.0 | 287.2 | 226.3 | −29% |
| bishop | 330 | 328.0 | 324.7 | 309.1 | 268.2 | −19% |
| rook | 500 | 498.5 | 497.0 | 490.3 | 459.4 | −8% |
| queen | 900 | 900.1 | 899.5 | 895.7 | 882.6 | −2% |

Divergence is **eliminated**; the collapse is **confirmed**. That the ordering
resembles how often each piece is on the board is an observation, not a
measurement — nothing here tested it.

## 1d. A training-pipeline fault? Not a misconfiguration

**Different seed: the collapse is unchanged.** At seed 23, 3,000 games: pawn
74.4 against seed 11's 80.2 — same place, same size, same direction. The peak
is not a seed accident.

**A fifth of the learning rate does not remove the collapse.** Plotted against
the product `learning rate × games`, the two arms lie on one curve:

| lr × games | pawn drop | arm |
|---|---:|---|
| 8k | −3.3 | lr 8, 1,000 games |
| 24k | −6.4 | lr 8, 3,000 |
| 40k | −10.8 | lr 40, 1,000 |
| 80k | −17.2 | lr 8, 10,000 |
| 120k | −19.8 | lr 40, 3,000 |
| 400k | −35.1 | lr 40, 10,000 |

So it is a bias that accumulates with total step mass, not a step size chosen
badly. **A pipeline fault in the sense of "wrong hyperparameter" is eliminated.**

## The prediction this made, and how it failed

`docs/COLLAPSE_PREREG.md`, committed before the games: if strength tracks the
collapse rather than the game count, then `lr=8, 10,000 games` — whose collapse
state (pawn 82.8) sits near the peak arm's (80.2) and far from the same-game-count
high-rate arm's (64.9) — should land **between −20 and +30 Elo**.

**Measured: +58 Elo [+31, +87]**, 600 fixed-length games, 304-92-204.

The whole interval lies above the predicted band. The registered falsification
trigger was "+60 or above" and the point estimate is +58, so the letter of the
criterion was not tripped; the prediction was still wrong, and saying otherwise
on a two-Elo technicality would be the kind of bookkeeping pre-registration
exists to prevent.

Both simple stories are now dead:

* **"Strength follows the game count"** predicts ≈ −63 at 10,000 games.
  Rejected — the interval does not come near it.
* **"Strength follows the collapse state"** predicts ≈ +10, the peak's value.
  Rejected too: +58 against the peak's +10 is a difference of +48 [+13, +83],
  zero excluded.

What actually happened is that the low-rate arm is **the strongest learned
evaluation this project has produced**: +58 [+31, +87] over the hand-written
tables, an interval clear of zero on the positive side. The fall at 10,000
games is not a property of 10,000 games. It is a property of 10,000 games *at
that learning rate*.

## The closure figure the brief asked for — and why a single number is not defensible

The published claim is *"10,000 games closes 38% of the 175 Elo between bare
material counting and the hand-written tables."* Two things are wrong with it.

**First, its sample.** The numbers behind it are in `data/self_play_run.json`:
match scores of 0.65625 and 0.53125 — that is 21/32 and 17/32. **Thirty-two
games each.** The first converts to +112 Elo with an interval of [−6, +264];
the second says the learner is +22 against the hand-written tables where the
proper 1,000-game measurement says −63. It was never a measurement.

**Second, its premise.** A closure ratio assumes the three engines sit on one
rating scale. They were measured, all three legs, 600 fixed-length games each
at 0.2 s, with wins, draws and losses recorded:

| pairing | W-D-L | draw rate | score |
|---|---|---:|---:|
| tables vs material-only | 368-112-120 | 18.7% | 0.707 |
| learned(3,000) vs material-only | 300-139-161 | 23.2% | 0.616 |
| learned(3,000) vs tables | 290-64-246 | 10.7% | 0.537 |

A Rao-Kupper fit over all three produces a consistent-looking set of ratings —
material 0, learned +113 ± 11, tables +119 ± 11 — and then fails to describe
the games that produced it:

| pairing | observed | expected under the fit | χ² |
|---|---|---|---:|
| tables vs material | 368-112-120 | 345-101-154 | 10.2 |
| learned vs material | 300-139-161 | 340-102-158 | 18.3 |
| learned vs tables | 290-64-246 | 239-113-248 | 32.0 |

**χ² = 60.5 on 3 degrees of freedom, p ≈ 5×10⁻¹³.** The single-scale model is
rejected. The largest single term is the head-to-head leg, and the way it fails
is specific: it draws 64 games where the fit needs 113. Two engines of nearly
equal strength normally draw *more*, not half as often. They are not equal-and-
similar; they are equal-and-different, winning in different positions.

So the honest answer to "what fraction of the gap does the method close at its
best" is in two parts:

* **If the ratio is taken at face value:** +82 [+54, +111] of +153 [+123, +185]
  is **54% [32%, 75%]** at 3,000 games, against a published 38% whose interval
  contains it and everything else.
* **The ratio's premise is measured false**, at p ≈ 5×10⁻¹³. What can be said
  without it is the head-to-head result, which needs no scale: at 3,000 games
  the learned table measures **+26 [−2, +54]** against the hand-written tables,
  and at 10,000 games with a fifth of the learning rate, **+58 [+31, +87]**.

The question the original brief asked — *how many games to beat the hand-written
tables* — has an answer that no longer needs extrapolating: **10,000, at learning
rate 8.** Whether fewer would do was not measured.

## Verdict

| hypothesis | status |
|---|---|
| the peak is noise | **eliminated** — 4.7σ, from games already played |
| overfitting | **eliminated** — held-out human games show no degradation |
| divergence (unbounded weights) | **eliminated** — norms shrink |
| a badly chosen learning rate | **eliminated** — the collapse follows lr × games |
| a systematic collapse of the value scale | **confirmed** — monotone, seed-independent, ordered by piece |
| what the collapse *is*, in the update rule | **open** — not measured, and not guessed at here |
| where the low-rate arm's own peak lies | **open** — +58 at 10,000 games is the last point measured, and it is still the best one |
