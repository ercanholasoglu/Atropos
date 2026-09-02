# DRAFT — pre-registration: how narrow can the position key get?

**Status: draft, awaiting approval. No games have been played and no
collision counting has been run.** The rule this project set is that a run
begins only after a committed pre-registration; this document is written to
*become* that, not to substitute for it.

---

## A correction that has to come first

The task names this a Zobrist experiment. **This engine does not use a Zobrist
hash.**

`engine/search/transposition.py` keys the table on
`hash(board._transposition_key())` — Python's hash of python-chess's own
repetition-detection key. The module docstring records why, and the reasoning
was measured rather than assumed: `chess.polyglot.zobrist_hash` recomputes
from scratch at ~10 µs per call, more than twice the cost of the evaluation it
is meant to save, while reading python-chess's maintained key costs ~0.4 µs.

That does not make the experiment meaningless — **key width and collision rate
are properties of any hash**, and truncation tests them the same way. It does
mean two things must be said plainly:

1. The comparison to Zobrist's 1970 predictions (≈3% at 20 bits, ≈0.1% at 35
   bits) is a comparison against a *different function*. Those figures assume
   uniformly random independent keys. Python's tuple hash is not designed as a
   cryptographic or avalanche hash, and its low bits may distribute worse or
   better. **Whether this key behaves like a Zobrist key is part of what the
   experiment measures, not an assumption it may make.**
2. Anything found here transfers to a real Zobrist implementation only if the
   two distribute alike, and that is a claim this design cannot check.

## What "collision" means here, precisely

The table already counts something it calls collisions, and it is **not** the
dangerous kind.

* **Index collision** — two different keys land in the same slot
  (`key & mask`). Detected: each entry stores its own key and `probe` rejects a
  mismatch. Costs a lost entry, never a wrong answer. This is what
  `TranspositionTable.collisions` counts today.
* **Key collision** — two *different positions* produce the *same key*.
  Undetectable by construction: the probe compares keys, the keys match, and
  the search receives another position's score and move. **This is the failure
  the experiment is about**, and nothing in the engine currently counts it.

At 64 bits a key collision is vanishingly rare. At 16 bits, with a 2^20-entry
table, it is the normal case. Somewhere between is the point where the
consequences become visible in play, and that point is what the two parts
below locate.

## Part (a) — count real key collisions during perft

No games. Perft walks a known, reproducible set of positions and their exact
node counts already serve as a correctness oracle.

**Method.** Run perft to a fixed depth with a dictionary mapping *truncated
key* → *full position key*. Every time a truncated key recurs with a different
full key, that is a real key collision, counted. Widths **16, 24, 32, 48** and
the full key as a control.

**Reported:** collisions per million distinct positions, at each width,
alongside the count of distinct positions seen — because a rate without a
denominator is not a rate.

**Cost:** minutes. Perft to depth 5 from the start position visits 4,865,609
nodes and this project already runs it.

**Prediction.** With `n` distinct positions and a `b`-bit key, the birthday
approximation gives an expected collision count of about `n² / 2^(b+1)`. For
perft(5) at 4.86 M nodes, taking distinct positions as roughly a third of
that:

| width | expected collisions |
|---:|---:|
| 16 bits | ~2 × 10^7 (every key reused thousands of times) |
| 24 bits | ~78,000 |
| 32 bits | ~305 |
| 48 bits | ~0.005 |

**Falsified if** the measured counts differ from these by more than a factor
of three at 24 or 32 bits. A large discrepancy would say the key is not
distributing uniformly — which is exactly the thing the Zobrist comparison
above cannot be assumed.

## Part (b) — what a collision costs in play

**Method.** The engine plays itself with the key truncated to each width,
against the same engine with the full key. Everything else identical:
instrument v2, 0.1 s per move, the default book, fixed length, no stopping
rule.

**Widths:** 16, 24, 32, 48.
**Games:** 400 per width, which is about ±35 Elo — enough to separate "ruinous"
from "harmless" without pretending to resolve single digits.
**Cost:** 1,600 games at roughly 1.4 s each on six workers, about **8 minutes**
per width, **35 minutes** total.

**Predictions.**

| width | predicted Elo vs the full key | reasoning |
|---:|---|---|
| 16 | **−200 or worse** | every key aliases many positions; the table returns other positions' scores constantly |
| 24 | **−30 to −150** | collisions common enough to poison a search several times a game |
| 32 | **−20 to +10** | a few hundred collisions across a whole search, most in positions that never matter |
| 48 | **−10 to +10**, indistinguishable from zero | expected collisions well under one per game |

**The falsifiable claim: the curve has a knee.** Somewhere between 24 and 48
bits the cost collapses from ruinous to unmeasurable, and it does not decline
smoothly across the range.

**Falsified if** 16 bits is not clearly worse than 48, which would mean the
table is contributing so little that corrupting it costs nothing — a finding
about the table rather than about hashing, and one worth having.

## What the pair gives that neither gives alone

Part (a) is a count and part (b) is a consequence. Together they give
**collisions per million → Elo**, which is the only form in which "how many
bits do you need" is answerable for *this* engine rather than for hashing in
general.

The honest limit: it answers it for a 2^20-entry table at 0.1 s per move, and
both of those move the answer. A bigger table holds more positions and
collides more; a longer clock searches more nodes and collides more. **The knee
is a property of the configuration, not of the number 32.**

## Rules this run inherits

* Brackets and predictions above are fixed before any run.
* An interval containing zero is no verdict.
* `diagnosis()` is read before anything is written up.
* No test suite runs while a timed match does.
* Six workers maximum.
* Every run recorded with telemetry.

---

**Awaiting approval. Nothing runs until this is committed.**
