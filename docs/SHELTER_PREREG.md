# Pre-registration: king shelter, on its own at last

Committed before the games.

## Why this variant did not exist until now

`v3-shelter` is `positional_eval_v3(king_attackers=False)` — evaluation v3
with only the *attacker* half of king safety switched off. It carries passed
pawns and rook files too. Reading its result as "king shelter" was an error I
made and withdrew (`docs/REJECTION_PREREG.md`).

`positional_eval_shelter` now exists and computes **v2 plus king shelter and
nothing else**. This measures it.

## What is already known

| variant | what it is | nps | Elo vs v2 |
|---|---|---:|---:|
| v2 | baseline | 64,886 | — |
| `v3-rooks` | + rook files | 60,337 | −2 [−26, +22] |
| `v3-passers` | + passed pawns | — | +11 [−12, +34] |
| **`shelter-only`** | **+ king shelter** | **58,138** | **this run** |
| `v3-shelter` | + all three | 49,640 | +21 [−5, +47] |

The throughput cost is measured: **58,138 against 64,886 is 10.4%**, which is
0.159 doublings, **−27 Elo** at the measured conversion. An A/B at a fixed
clock nets that off, so shelter's positional contribution has to clear +27
before the variant shows anything at all.

## Prediction

**+12 Elo**, from taking the three measured effects as additive: the bundle is
+21, rook files are −2 and passed pawns are +11, leaving 21 − (−2) − 11 = 12.

600 games gives about ±29, so the prediction is well inside what this run can
resolve either side of.

**That additivity is itself the hypothesis being tested.** Evaluation terms
are not obliged to add — two terms can encode the same positional fact and pay
for it twice, which is the double-counting this project has already measured
between the passed-pawn term and the piece-square tables.

* **Near +12** → the three terms are roughly independent, and the bundle's +21
  is the sum of its parts rather than an interaction.
* **Clearly above +12** → shelter carries more of the bundle than its share and
  the other two are dead weight in it.
* **Near zero or below** → the terms overlap, the bundle's +21 does not
  decompose, and shelter alone does not pay its 10%.

**Falsified if** the result lands outside [−40, +65] — the range the three
measured intervals leave room for under any additive reading.

## The measurement

    python -m scripts.sprt_match --a shelter-only --b v2 --fixed --max-games 600

600 games, fixed length, no stopping rule, 0.1s per move, same operating point
as every other A/B here.
