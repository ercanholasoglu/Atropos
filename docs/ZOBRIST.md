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
