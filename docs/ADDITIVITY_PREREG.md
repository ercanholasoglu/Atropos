# Pre-registration: do evaluation terms add?

Committed before the games. This experiment exists because two measurements
cannot both be simple.

## The contradiction

| variant | what it is | Elo vs v2 |
|---|---|---:|
| `v3-rooks` | v2 + rook files | −2 [−26, +22] |
| `v3-passers` | v2 + passed pawns | +11 [−12, +34] |
| `shelter-only` | v2 + king shelter | **−54** [−84, −24] |
| `v3-shelter` | v2 + **all three** | **+21** [−5, +47] |

The parts sum to −45 ± 37. The bundle measures +21 ± 26. The difference is
66 ± 45 — 1.47 standard errors, which does not resolve, and which
`docs/SHELTER_PREREG.md` refused to interpret for exactly that reason.

## The experiment that separates them

`passers-rooks` — v2 plus passed pawns and rook files, no king safety at all.
It is the bundle with the harmful term removed. Verified against its definition
on 320 positions: it equals `v3-shelter` minus the shelter contribution
exactly, 0 mismatches. Throughput 53,556 nps against v2's 64,794, a 17.3% cost
worth **−48 Elo** at the measured conversion.

The two accounts make predictions **66 Elo apart**, which 600 games (±29)
separates at better than two standard errors:

| account | prediction | reasoning |
|---|---:|---|
| **terms add** | **+9** | −2 for rooks plus +11 for passers |
| **the bundle interacts** | **+75** | +21 for the bundle, minus the −54 that shelter contributes to it |

* **Near +9** → evaluation terms in this engine add. The bundle's +21 is then
  an over-reading of a noisy measurement, and `shelter-only`'s −54 is simply
  the largest real effect any of these terms has.
* **Near +75** → they do not add, the bundle genuinely exceeds its parts, and
  this variant is the strongest evaluation this project has measured — worth
  shipping over both v2 and the current engine.
* **Between, unresolved** → 600 games was not enough and the honest answer is
  that additivity is still open.

**Falsified if** the result lands outside [−40, +120], which no reading of the
four existing measurements leaves room for.

## Why this is worth the games

Every evaluation decision this project has taken assumed terms could be judged
one at a time — v3 was tested as a bundle, rejected, then its parts were tested
separately and one was shipped alone. **If terms do not add, that entire
procedure was invalid**, and the bundle result was the only one that ever meant
anything.

## The measurement

    python -m scripts.sprt_match --a passers-rooks --b v2 --fixed --max-games 600

600 games, fixed length, no stopping rule, 0.1s per move.
