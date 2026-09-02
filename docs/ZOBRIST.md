# How many bits does the position key need?

Results for `docs/ZOBRIST_PREREG.md`. The predictions in that file were fixed
and committed before any of the numbers below existed.

## Part (a) — collisions, counted

A **key collision** is two different positions producing the same key. It is
the failure the table cannot detect: the probe compares keys, they match, and
the search is handed another position's score and best move. The counter that
already existed, `TranspositionTable.collisions`, counts *index* collisions —
two keys landing in one slot — which are detected and discarded. Nothing
counted the undetectable kind until this.

Method: walk every position perft visits, collect the set of distinct full
keys, and for each width count `distinct positions − distinct truncated keys`.
A repeat visit to the same position is not a collision, which is why the count
comes from the set of distinct keys rather than from the visit sequence.

### The key is re-drawn every run

`position_key` is `hash(board._transposition_key())`, and that tuple holds
`None` in the en-passant slot whenever there is no legal en passant — which is
most positions. In CPython `hash(None)` is derived from the address of the
`None` singleton, so it changes with every process, and `PYTHONHASHSEED` does
not fix it:

```
$ for i in 1 2 3; do python -c 'print(hash(None))'; done
-9223372036584416528
-9223372036581041424
-9223372036582253840
```

A collision count is therefore a sample, not a constant. Everything below is
reported as several independent draws, not one number. This has no consequence
for the engine — the table lives and dies inside one process and is never
persisted — but it does mean a single run would have been reported with a
precision it does not have.

### Counts

perft(5) from the opening position: 5,072,213 nodes, **898,812 distinct
positions**. Four draws:

| width | slots | collisions (four draws) | mean | predicted | ratio |
|---|---|---|---|---|---|
| 16 | 65,536 | 833276, 833276, 833277, 833276 | 833,276 | 6,163,506 | 0.14 |
| 24 | 16,777,216 | 23681, 23477, 23391, 23609 | 23,540 | 24,076 | 0.98 |
| 32 | 4,294,967,296 | 95, 95, 95, 90 | 94 | 94 | 1.00 |
| 48 | 281,474,976,710,656 | 0, 0, 0, 0 | 0 | 0.0006 | — |

perft(4), 77,796 distinct positions, eight draws, as a check that the pattern
is not an artefact of one depth:

| width | collisions (eight draws) | mean | predicted | ratio |
|---|---|---|---|---|
| 16 | 32223 32204 32308 32248 32238 32348 32384 32314 | 32,283 | 46,175 | 0.70 |
| 24 | 177 179 171 180 178 189 189 172 | 179 | 180 | 0.99 |
| 32 | 1 1 0 1 1 1 2 0 | 1 | 1 | 1.24 |
| 48 | 0 0 0 0 0 0 0 0 | 0 | 0 | — |

### Against the registered criterion

The criterion was: *falsified if the measured count differs from the birthday
prediction by more than a factor of three at 24 or 32 bits.*

- 24 bits: 0.98 of prediction at depth 5, 0.99 at depth 4.
- 32 bits: 1.00 at depth 5, 1.24 at depth 4 (on a mean of one collision).

**Not falsified.** The key distributes like a uniform random hash to within
2% where the sample is large enough to say so. That was an assumption, not a
fact, until it was counted: python-chess's tuple hash was never designed as a
position hash, and it would have been reasonable for board structure to leave a
pattern in the low bits. It does not.

### The 16-bit prediction was arithmetically impossible

The registration predicted ~2×10⁷ collisions at 16 bits. A collision count
cannot exceed the number of positions, and there are 898,812. The birthday
approximation `n²/2^(b+1)` is only valid while `n ≪ 2^b`; at 16 bits there are
65,536 slots for 898,812 positions and the table is saturated.

The measured count is then not a measurement of the hash at all. Every slot is
occupied, so collisions = 898,812 − 65,536 = **833,276** exactly — which is
what all four draws report, to within one. The pigeonhole principle fixes it;
the hash function has nothing to do with it. The three-draws-identical column
at 16 bits is that, not precision.

This is a mistake in the pre-registration, and it is the kind pre-registration
is supposed to catch: the prediction was checkable by arithmetic before any
code ran, and it was not checked. It is recorded rather than corrected in
place. The criterion it would have supported — *"is 16 bits clearly worse"* —
is answered in part (b) by games, where saturation is the whole point.

Reproduce: `python -m scripts.zobrist_width --depth 5`

## Between (a) and (b): a deterministic prediction, recorded before the games

Part (a) counted collisions over perft. The table does not see perft; it sees
whatever one game puts in it. So before spending games, the same engine was
played against itself at fixed depth 4 with no clock — fully deterministic, one
game, the table persisting across moves as it does in play. Any divergence is
the truncated key and nothing else.

| width | first divergence | plies identical | tt entries filled | hits | index collisions |
|---|---|---|---|---|---|
| full | — | 73 | 55,584 | 30,132 | 1,478 |
| 48 | none | 73 | 55,584 | 30,132 | 1,478 |
| 32 | none | 73 | 55,584 | 30,133 | 1,478 |
| 24 | none | 73 | 55,575 | 30,358 | 1,393 |
| 16 | ply 6 | 5 | 47,951 | 181,271 | 0 |

Read the last two columns together. At 16 bits the key is narrower than the
table's index, so every index collision *becomes* a silent false hit: index
collisions fall to zero and hits rise six-fold, from 30,132 to 181,271. Nothing
is detected because there is nothing left to detect with. At 24 bits the same
conversion happens 85 times over a whole game — 1,478 index collisions down to
1,393, hits up by 226 — and the engine still plays all 73 plies identically.

**Prediction, fixed before any game is played:** 48 and 32 bits will measure 0
Elo, not "a small effect" — on this line the search is byte-identical, so games
can only add noise around zero. 24 bits will be indistinguishable from zero at
400 games. 16 bits will be clearly worse.

The registered arms are run anyway, all four at the registered 400 games. A
pre-registration that gets abandoned when the answer looks obvious in advance
is not one.

## Part (b) — Elo

Each width plays the full-key engine, 400 registered fixed-length games at
0.1 s per move, six workers, six-piece opening book, no stopping rule. Ratings
are fitted with the Rao-Kupper three-outcome model, not converted from the
score: these pairings draw 33–37% and a score-only conversion compresses what
it reports (`docs/RATING_FIT.md`).

| bits | collisions at perft(5) | rate | games | W-D-L | Elo vs full key | 95% interval | registered |
|---|---|---|---|---|---|---|---|
| 16 | 833,276 | 92.7% | 402 | 16-7-379 | **−611**\* | [−684, −538] | ≤ −200 |
| 24 | 23,681 | 2.6% | 402 | 112-132-158 | **−45** | [−76, −13] | −30 to −150 |
| 32 | 95 | 0.011% | 402 | 121-147-134 | −13 | [−44, +18] | −20 to +10 |
| 48 | 0 | 0% | 402 | 125-148-129 | −4 | [−35, +27] | −10 to +10 |

\* draw parameter fixed at 129, the value the other three arms agree on
(120/133/134). Fitted freely it goes to −2397 and the interval opens to
±44,000: 7 draws in 402 games is not a drawishness estimate, it is a singular
Hessian. The point estimate moves between −583 and −680 as the assumed draw
parameter moves from 100 to 200, so read the width of that range, not the
digits. Note also *why* it has so few draws — a 16-bit engine does not hold
positions well enough to draw them.

**Two of four intervals exclude zero.** 32 and 48 bits are not distinguishable
from the full key at 400 games; that is not a demonstration that they cost
nothing, only that nothing was resolved. 24 bits costs a measured 45 Elo.

Every registered band contains its measured point estimate.

### The registered falsifiable claim survives

*"The curve has a knee between 24 and 48 bits. Falsified if 16 bits is not
clearly worse than 48."*

16 bits measures −611 [−684, −538]; 48 bits measures −4 [−35, +27]. Not
falsified. The width at which the cost stops being resolvable lies between 24
and 32, inside the registered range.

One thing that is *not* shown: 24 bits is not resolvably worse than 32. The
difference between −45 and −13 is 32 Elo with a combined interval near ±45.
"24 is the last resolvable cost" and "24 is measurably worse than 32" are
different claims and only the first was measured.

### My own prediction was falsified at 24 bits

The deterministic check recorded before the games predicted 24 bits would be
indistinguishable from zero. It measured −45 [−76, −13], zero excluded.

The reason is scale, and it was checkable in advance. The deterministic game
ran at fixed depth 4 and left 55,584 entries in the table. Real games at 0.1 s
per move search ~570,000 nodes per game and fill the table to its 2²⁰ = 1,048,576
capacity. Collisions go as n², so the same key width that produced 85 silent
false hits in the deterministic game produces roughly 32,000 in a real one — a
350-fold difference. The deterministic check measured the right quantity on the
wrong table.

The prediction for 32 and 48 bits — no measurable cost — survives, but its
stated mechanism ("byte-identical, so games can only add noise") is wrong for
the same reason. At 32 bits a full table collides about 128 times per game. The
engine is not identical; the cost of those collisions is merely below what 400
games resolve.

### Against Zobrist's 1970 figures

Zobrist quotes 3% at 20 bits and 0.1% at 35 bits. A collision *rate* is not a
property of a bit width alone — it depends on how many positions are in the
table — so the two figures can only be compared once that number is supplied.
Under the same birthday model they imply:

| Zobrist's figure | implied positions |
|---|---|
| 3% at 20 bits | 62,915 |
| 0.1% at 35 bits | 68,719,477 |

Three orders of magnitude apart: the two percentages do not describe one table,
and quoting them side by side as a curve would be wrong.

What is comparable is the functional form, rate ≈ n/2^(b+1), and that is what
the measurement confirms. At perft(5)'s 898,812 positions the model gives
2.679% at 24 bits and 0.0105% at 32; measured, 2.635% and 0.0106%. The exponent
is right and the constant is right to within 2%. Zobrist's arithmetic holds on
a hash function he never saw, in a language that did not exist when he wrote it.

The rate also transfers to play without adjustment, which is luck but checkable
luck: perft(5)'s 898,812 distinct positions land within 15% of the table's
1,048,576-entry capacity, so the counted rate is close to the rate a real game
runs at.

### What this answers, and what it does not

For a 2²⁰-entry table at 0.1 s per move, a 32-bit key costs nothing this
project can measure and a 24-bit key costs 45 Elo. The knee is a property of
that configuration, not of the number 32: it sits where n²/2^(b+1) becomes
comparable to the number of positions in the table, so a bigger table or a
longer time control moves it right. Nothing here was measured at 1.0 s per
move, where `docs/LONG_TC_PREREG.md` showed the engine behaves differently.

Reproduce: `python -m scripts.zobrist_report`

### Slip

The first command omitted `--minutes` and took its default of 15, so three of
the four arms were cut at the clock rather than at the registered 400 games
(294, 282, 330). They were topped up afterwards from their state files and all
four ended at 402. No result was read off the short arms.
