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

---

## Result

**600 games, fixed length: 53.7%, +26 Elo, interval [+1, +51].**

| account | prediction | inside the interval? |
|---|---:|---|
| terms add | **+9** | **yes** |
| the bundle interacts | +75 | no |

**The interaction account is rejected. The additive one survives** — but only
for this pair, and the rest of the table complicates it.

### Additivity, tested piece by piece

| composition | predicted | observed | difference | verdict |
|---|---:|---:|---:|---|
| passers + rooks → `passers-rooks` | +9 | +26 | +17 ± 22 (0.75σ) | consistent |
| `passers-rooks` + shelter → bundle | −27 | +21 | +48 ± 25 (1.92σ) | consistent, barely |
| rooks + passers + shelter → bundle | −44 | +21 | +65 ± 27 (**2.42σ**) | **inconsistent** |

**The two cheap terms add cleanly. Shelter is where it breaks.**

Measuring shelter's contribution two ways makes the point directly:

| shelter added to | contributes |
|---|---:|
| v2 alone | **−53** ± 15 |
| v2 + passers + rooks | **−5** ± 20 |

Difference 48 ± 25, or 1.92σ — suggestive and not established. What can be
said without straining: **shelter is clearly harmful on its own and clearly
does nothing in company**, and whether that difference is a real interaction or
two noisy numbers is not settled by 1,158 games.

### The result that matters more than the hypothesis

| variant | Elo vs v2 | nps |
|---|---:|---:|
| v2 | — | 64,794 |
| `v3-rooks` — **the one that shipped** | −2 [−26, +22] | 60,337 |
| `shelter-only` | −53 [−84, −24] | 58,138 |
| **`passers-rooks`** | **+26 [+1, +51]** | 53,556 |
| `v3-shelter` (all three) | +21 [−5, +47] | 49,064 |

**`passers-rooks` is the first evaluation variant this project has measured
with an interval clear of zero on the positive side.** It is also cheaper than
the bundle, because it leaves out the term that was doing nothing.

The margin is thin — the lower bound is **+1**, one Elo clear of nothing, on
600 games. It is a result, not a comfortable one, and confirming it properly
would take another 600.

### What this says about the project's procedure

Evaluation v3 was tested as a bundle of three, rejected, and then its parts
were tested separately and **the one that measures −2 was shipped**. The
combination that actually measures positive — passed pawns and rook files,
without king safety — **was never tried until now**, because the bundle's
rejection was read as covering everything inside it.

Terms mostly add. The procedure that assumed they did was not wrong in
principle. It was applied to a bundle whose rejection was itself an artifact of
a stopping rule, and every step after that inherited the error.

---

## Confirmation run, declared before it starts

The result above is +26 with a lower bound of **+1**. That is a margin of one
Elo on 600 games, and this document called it "a result, not a comfortable
one". Confirming it means more games, and saying how many *before* playing
them — otherwise the run stops wherever it looks best, which is the failure
this whole line of work exists to document.

**Target: 1,200 games total, fixed length, no stopping rule.** The existing 600
are kept and 600 more are played from game index 600 onward, so no game is
replayed. 1,200 games gives about ±20 Elo.

**Prediction: +26 stays, and the interval tightens to roughly [+6, +46].**

* **Interval still clear of zero** → the effect is real at this operating
  point, and `passers-rooks` is a shipping candidate on the measurement rather
  than on an argument.
* **Interval now contains zero** → the 600-game result was the thin end of
  noise, and the honest position is that nothing in this evaluation programme
  has been shown to help.

Either way the number is reported. **No third extension.** If 1,200 games do
not resolve it, the answer is that an effect this size is at the resolution
floor of this setup — which the project measured early and has kept running
into.

### Confirmation result

**1,200 games: 51.67%, +12 Elo, interval [−8, +31].**

The prediction was that +26 would hold and the interval would tighten to about
[+6, +46]. **It did not.** The estimate fell from +26 to +12 as the games
accumulated, and the interval now contains zero.

By the outcome fixed before the run: *"the 600-game result was the thin end of
noise, and the honest position is that nothing in this evaluation programme has
been shown to help."* That is the position.

No third extension, as declared.

## The evaluation programme, closed

**3,672 A/B games across five variants.**

| variant | games | Elo vs v2 | 95% interval |
|---|---:|---:|---:|
| `v3-rooks` — the one that shipped | 600 | −2 | [−26, +22] |
| `v3-passers` | 714 | +11 | [−12, +34] |
| `shelter-only` | 558 | **−53** | **[−84, −24]** |
| `passers-rooks` | 1,200 | +12 | [−8, +31] |
| `v3-shelter` (all three) | 600 | +21 | [−5, +47] |

**Exactly one of these intervals is clear of zero, and it is clear on the
negative side.** After 3,672 games: nothing has been shown to improve the
evaluation, and one term has been shown to make it worse.

### The project predicted this at the start

An early measurement in this repository established a resolution floor: a
change worth ≥100 Elo resolves in 7–65 games, ≥40 Elo in about 350, ≥20 Elo in
about 1,500, and ≥10 Elo in about 6,000. Classical evaluation terms are worth
+10 to +25.

**1,200 games on the best candidate returned +12 [−8, +31].** That is precisely
what the table said would happen — an effect at the bottom of the plausible
range, measured with a tool whose resolution stops just short of it. The
programme did not fail to find an effect because the terms are worthless. It
failed because effects of this size need thousands more games than were spent,
and the table said so before any of them were played.

That is also the argument for where the effort went instead. The speed work
produced **+83 Elo** for the ladder's throughput improvement, measured and
converted, on a fraction of the games — because a 39% speed change is a
100-Elo-class effect and lands in the region this setup resolves easily.
