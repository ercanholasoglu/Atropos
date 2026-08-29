# chess-bot

A level-based chess engine: **8 difficulty levels** from random mover to a
neural/LLM-assisted searcher, each one tracked with a live Elo rating earned
in self-play tournaments.

A companion to the Athena platform rather than a component of it: the engine
ladder is a controlled testbed for evaluating search, evaluation and
LLM-assisted reasoning against a measurable score, and it is kept in its own
repository so its measurements stand on their own.

**[Measurement record →](https://claude.ai/code/artifact/4f9ebb66-e882-451a-a152-470a9632e0b3)**
— the ladder, the external anchor, the speed curve, every pre-registered
prediction including the three that failed, and the four claims that were
withdrawn. Source: [`docs/showcase.html`](docs/showcase.html).

## Status

| Phase | Scope | State |
|-------|-------|-------|
| 1 | Core engine, Level 1–2, tests | ✅ done |
| 2 | Minimax, alpha-beta (L3–L4), match runner | ✅ done |
| 3 | PST + tapered eval (L5) | ✅ done |
| 4 | Quiescence, TT, pruning (L6–L7) | ✅ done |
| 5 | Elo database + calculator | ✅ done |
| 6 | Tournament system | ✅ done |
| 7 | Streamlit UI | ✅ done |
| — | Perft, UCI, external calibration, tactical suite | ✅ done |
| 8 | Level 8 + LLM commentary | ✅ done |

## The ladder

| Level | Technique | Target Elo | Measured |
|-------|-----------|-----------:|---------:|
| 1 | Random legal move | 200 | — |
| 2 | Material count, 1-ply | 600 | **96.9%** vs L1 |
| 3 | Minimax, depth 3 | 900 | **100%** vs L2 |
| 4 | Alpha-beta + iterative deepening, depth 4 | 1200 | **93.8%** vs L3 |
| 5 | Piece-square tables, tapered eval, depth 5 | 1500 | **84.4%** vs L4 |
| 6 | Quiescence, transposition table, killers, MVV-LVA | 1800 | **90.6%** vs L5 |
| 7 | Null-move, LMR, history, aspiration windows | 2100 | **75.0%** vs L6 † |
| 8 | Adaptive time management, optional LLM advisor | 2400 | **−85 vs L7 †† ** |

Measured over 16 games per pairing from the opening book, 300-ply limit, at a
fixed 0.3s per move (`make ladder`, 2026-08-23).

### The same claim, tested sequentially

Those numbers came from fixed sixteen-game matches — the method that, tested
against itself elsewhere in this project, called an evaluation change +60 Elo
at 64 games and −2 at 359. The claim deserved the better instrument, so every
adjacent pairing was re-run as an SPRT against `H1: at least 100 Elo`
(`make ladder-sprt`, 0.1s per move):

| pairing | games | score | Elo † | 95% interval | verdict |
|---|---:|---:|---:|---:|---|
| L2 vs L1 | 9 | 88.9% | +361 | [+194, +800] | accepted |
| L3 vs L2 | 7 | 100.0% | +800 | [+800, +800] | accepted |
| L4 vs L3 | 9 | 88.9% | +361 | [+194, +800] | accepted |
| L5 vs L4 | 33 | 68.2% | +132 | [+45, +240] | accepted |
| L6 vs L5 | 9 | 88.9% | +361 | [+134, +800] | accepted |
| L7 vs L6 | 65 | 63.1% | +93 | [+21, +174] | accepted |
| **L8 vs L7** | **25** | **38.0%** | **−85** | **[−238, +40]** | **rejected** |

**The ladder is ordered up to Level 7. Level 8 adds nothing measurable.**

**† The Elo column is not an estimate of anything.** Simulating this exact
stopping rule against known truths ([`docs/SPRT_BIAS.md`](docs/SPRT_BIAS.md))
shows that a run which accepts H1 and stops early reports **about +110
whatever the true difference is** — +113 when the truth is zero, +118 when it
is a hundred. The number moves by five Elo across a range of a hundred. What
carries information is the *verdict*: this rule accepts 3% of the time at a
true zero and 97% at a true hundred. Read the column as "the test stopped
here", and the verdict as the claim.

The first thing that table shows is what sequential testing buys: the bottom
three rungs were settled in **25 games between them**, where the fixed gauntlet
spent 48 and proved less. Budget goes where the question is hard — L7 vs L6
needed 65 games.

### The Target Elo column is a column of names

The second thing it shows took an outside instrument to see. The rungs are
labelled 300 Elo apart. **Nothing in this project has ever measured that, and
the measurements that exist disagree with it.**

Every pairing above was tested with the bracket `elo0=0, elo1=100`. "Accepted"
therefore means *this gap looks more like 100 Elo than like 0* — a test of
ordering. It is not a test of 300 and cannot be read as confirming one. Where
the intervals are informative rather than censored at the bound, they come in
well under the label: L7 vs L6 is **+93 [+21, +174]** and L5 vs L4 is **+132
[+45, +240]**, against a nominal 300 in both cases.

A fixed-depth Stockfish placed against two rungs in turn says the same thing
from outside (`docs/ANCHOR.md`): it scores −17 Elo against Level 7 and −21
against Level 6, putting the two rungs **4 Elo apart, interval [−47, +40]**,
where the labels claim 300. Two instruments, one internal and one external,
and neither finds the spacing the names assert.

The numbers themselves come from `INITIAL_ELO`, where they were assigned at
construction as targets. They are what each level was *aiming at*. Read the
"Target Elo" column as the specification it is, and the "Measured" column as
the only claim being made: **the ladder is ordered, and the ordering is
verified. The spacing is not.**

### Fitting all of it at once

Every number above came from one pairing at a time. Fitting all 2,730 games at
0.1s simultaneously ([`docs/RATING_FIT.md`](docs/RATING_FIT.md)) uses something
the chain of adjacent pairs throws away: **Stockfish at fixed depth played both
Level 6 and Level 7**, and what it says about the gap between them is
independent of the ladder match that also measures it.

| how the L7-over-L6 gap is computed | Elo |
|---|---:|
| score only, draws ignored — the method used above | +93 |
| the same 65 games with a draw model | +100 |
| every 0.1s game jointly, Stockfish included | **+50** [−3, +103] |

The outsider scores 47.5% against L7 and 46.9% against L6 — **4 Elo apart**,
where the direct match says 93. Pooled, the interval **includes zero**.

That disagreement then resolved itself. A true difference near 50, passed
through the ladder's stopping rule and stopped early, reports about 108 — so
**the direct match and the cross-link were never in conflict.** One is a
measurement; the other is the output of a rule that returns roughly the same
number regardless of the truth. And the fit refuses to place Levels 1 and 2 at
all: their only link to the rest is a 7-0-0 result, whose maximum likelihood is
at infinity, so the gap is reported as "+109 Elo or more" and nothing further.

The fit does **not** reopen Level 8. It reports −143 [−290, +3], but the shift
from the −85 measured directly comes from imposing a pooled draw parameter on a
pairing whose own draw rate is a fifth of the pool's. The interval contains zero
either way, and the correction below stands.

### A correction, and the mistake behind it

This section first reported the last row as *"Level 8 is a regression"*. That
was an over-read, and the table itself contains the reason: the interval is
**[−238, +40]**, which includes zero. What an accepted H0 proves is "not ≥100
Elo better" — it says nothing about which side of zero the truth is on.

The bracket was the real error. Asking "is this worth at least 100 Elo?" of two
engines that differ in one time-allocation heuristic was never going to return
anything interesting: H0 was close to certain before a game was played, exactly
the mistake made earlier with a 39% speedup measured against ±110 Elo error
bars. A bracket is a hypothesis about effect size and has to be picked from
what the change plausibly does.

Tested properly — the feature against its own absence, same engine, same
search, only the adaptive clock switched off:

| 54 games, 0.1s per move | score | Elo | 95% interval | verdict |
|---|---:|---:|---:|---|
| L8-uniform vs L8 | 48.1% | −13 | [−99, +72] | unresolved |

So the adaptive clock is not what costs Level 8 anything, and the diagnosis
that followed from the over-read — that redistributing time is noise — is not
supported either. Measured over 192 real positions the factor averages
**1.06×** in a range of 0.80× to 1.76×, so it redistributes rather than
underspends; whether that helps or hurts is still open, and 54 games cannot
say.

What stands after both tests is narrower and duller than the first claim:
**Level 8 has no measurable advantage over Level 7**, which is what should be
expected of a level that is Level 7's search plus one heuristic. The learned
evaluator it was designed around is still untrained; `static_eval` is the hook,
and until something goes in there Level 8 is a placeholder with a clock.

Each level must score **> 70%** against the level below it. `make ladder`
runs the gauntlet that produces those numbers and exits non-zero when a
pairing misses the bar; the test suite carries a cheaper regression guard,
because a sample small enough to run in CI cannot certify a 70% threshold
without flaking.

**†† Level 8 fails its pairing** — see the sequential table below.

**† Level 7 is the one pairing whose result depends on the clock**, and
tracking down why was the most interesting result in the ladder.

| Time control | L7 vs L6 | W-D-L |
|---|---:|---|
| 0.3s per move | 68.8% | 9-4-3 |
| 1.5s per move | **75.0%** | 10-4-2 |

Everything Level 7 adds — null-move pruning, late move reductions, history —
is a gamble that buys depth. At 0.3s per move in a middlegame position that
budget buys *both* levels exactly three plies: Level 7 saves nodes it has no
time to spend, and pruning without extra depth is a gamble with no upside, so
it lands slightly *behind* the level whose techniques are all exact. Given a
second or more it runs one to two plies deeper everywhere, and the rating gap
appears.

Two things this rules out. The first suspect was the null-move guard —
`depth - 1 - R` could bottom out at zero, making the verification search pure
quiescence, a free gamble. That was a real bug and it is fixed (the invariant
is now a test), but fixing it did not move the 0.3s number at all: 68.8%
before, 68.8% after. The second was the sample; the colour-reversed opening
book and 16 games make that unlikely, and the 1.5s run reproduces cleanly.
The clock was the whole story.

## Setup

```bash
make install          # uv venv (Python 3.11) + dependencies
make test             # full suite
make test-fast        # skip the self-play matches
make cov              # coverage report
make ladder           # long gauntlet: every level vs the one below it
make notebooks        # run the research notebooks
```

## Research

Five experiments built on top of the ladder, each measured against it rather
than against a training curve. See [`research/README.md`](research/README.md)
for the findings and [`notebooks/`](notebooks/) for the experiments themselves.

## Conventions

* **Scores are centipawns.** 100 = one pawn.
* **`evaluate()` and `SearchResult.score` are always from White's
  perspective** — positive means White is better. Search internals use
  negamax (side-to-move relative) and convert at the boundary.
* **Mate scores** shrink with distance (`MATE_SCORE - ply`) so shorter mates
  win, and anything above `MATE_THRESHOLD` is a forced mate.
* **Every engine owns a seeded RNG** (`self.rng`); no level touches the
  global `random` module, so tournaments replay exactly.
* **Search is negamax** — internally every score is relative to the side to
  move, converted to White-relative once, at the root, in `SearchEngine`.
* **Alpha-beta must agree with minimax.** Same depth, same evaluation, same
  score — only the node count differs. That equivalence is a test, and it is
  the safety net under every future pruning trick.
* **Piece-square tables are written from White's side** — index 0 is a8. The
  lookup mirrors for each colour (`table[square ^ 56]` for White,
  `table[square]` for Black), and every table is folded together with its
  piece value at import, so one lookup covers material and placement.
* **Evaluation is tapered**, never switched. Middlegame and endgame scores
  are both computed and blended by the material left on the board, so trading
  a piece cannot make the score jump.
* **Exact techniques must not change the score.** Alpha-beta, the
  transposition table, killers and MVV-LVA only reorder or skip work that
  provably cannot matter, so Level 6 at a given depth agrees with plain
  minimax — a test asserts it. Level 7's null-move pruning and late move
  reductions are gambles by design and are held to no such rule.
* **The game log is the source of truth.** Ratings in the `engines` table are
  a cache of it — `EloTracker.rebuild()` replays every game and must reproduce
  them exactly, which is what makes changing the K-factor a safe operation.
* **From Level 6 up the clock is the limit, not the depth.** Quiescence makes
  a full-width depth-6 search unaffordable in every position, so the levels
  iteratively deepen under a time budget and Level 7's advantage is the extra
  plies its pruning buys in the same three seconds.

## Layout

```
engine/
  base_engine.py     BaseEngine + SearchResult
  board.py           ChessGame — moves, results, PGN
  perft.py           move-generation proof and the throughput benchmark
  levels/            one module per level, a shared SearchEngine, registry
  evaluation/        material, pst, positional, tapered, structure, complexity
  search/            context, minimax, alphabeta, advanced (L6/L7),
                     quiescence, transposition, move_ordering, pruning
  utils/             constants, helpers
uci/
  protocol.py        command, go and position parsing
  options.py         Hash, Level, Move Overhead, Ponder
  time_manager.py    clock -> thinking budget
  engine.py          the loop, on a worker thread with cooperative stop
tournament/
  match.py           play_game / play_match — the base of every other mode
  uci_engine.py      an external UCI process wearing the BaseEngine interface
  base.py            pairings in, standings out; shared by all three formats
  round_robin.py     swiss.py     gauntlet.py
  openings.py        8-line opening book for low-variance testing
elo/
  calculator.py      expected score, rating updates, performance ratings
  database.py        SQLite: engines, games, elo_history
  tracker.py         ties games to ratings; rebuild() replays the log
  leaderboard.py     rankings, head-to-head, gauntlet ratings
app/
  streamlit_app.py   entry point (make run)
  pages/             play, watch, tournaments, leaderboard, analysis
  components/        board_view, eval_bar, move_history, elo_chart
research/
  features.py        384/768-dim position features shared by every experiment
  params.py          the evaluation as a tunable vector
  rl_tuning/         policy-gradient parameter tuning
  self_play/         TDLeaf(λ) value learning
  minimal_nnue/      architecture search and feature ablation
  hybrid_eval/       complexity-routed tiered evaluation
  alphazero_lite/    ResNet + PUCT MCTS + self-play loop
notebooks/           one per research module, with the experiments run
llm/                 optional Claude commentary and analysis
scripts/             ladder.py, tournament.py, leaderboard.py
tests/               pytest suite
data/                elo.db + PGN archive
```

## Playing other engines

The engine speaks UCI, so it plays in any chess GUI and against anything else
that does:

```bash
python -m uci                    # the engine on stdin/stdout
make calibrate                   # rate an external engine against the ladder
```

`Level` is a UCI option (1–8), which is what makes the ladder externally
measurable — a GUI or a match runner can pick the rung it wants to play.

External engines are driven over a pipe by `tournament/uci_engine.py`, which
wraps a subprocess in the same `BaseEngine` interface everything else uses, so
matches, gauntlets and the Elo tracker work on it unchanged. There is no
cutechess-cli dependency: speaking the protocol directly is a few hundred lines
and removes an install step, and the hard part was never the protocol — it is
an opponent that hangs, dies mid-game, or answers with an illegal move. Each of
those ends one game rather than the tournament.

### A calibration against something not written here

A ladder measured only against itself is self-consistent and could still be
uniformly terrible. **Atropos**, a C++ UCI engine with its own negamax,
quiescence, transposition table, killers and history, played the rungs at a
fixed 0.3s per move:

| matchup | score | W-D-L | implied |
|---|---:|---:|---:|
| atropos vs L2 | 100.0% | 12-0-0 | 1400 |
| atropos vs L3 | 91.7% | 10-2-0 | 1317 |
| atropos vs L4 | 70.8% | 5-7-0 | 1354 |
| atropos vs L5 | 75.0% | 6-6-0 | 1691 |
| atropos vs L6 | 12.5% | 0-3-9 | 1462 |
| atropos vs L7 | 4.2% | 0-1-11 | 1555 |

**Performance rating over the whole gauntlet: 1514** — between Level 5 (1500)
and Level 6 (1800), which is where an engine with that feature list belongs.

Re-run after the ladder got 39% faster, expecting Atropos to drop:

| matchup | score | W-D-L | implied |
|---|---:|---:|---:|
| atropos vs L4 | 85.0% | 7-3-0 | 1501 |
| atropos vs L5 | 50.0% | 2-6-2 | 1500 |
| atropos vs L6 | 15.0% | 0-3-7 | 1499 |
| atropos vs L7 | 15.0% | 1-1-8 | 1799 |

**1538.** It did not drop, and the prediction was wrong in a way worth writing
down rather than explaining away. A 1.39× speedup is worth roughly **+29 Elo**
by the usual rule of thumb; one standard error on a ten-game pairing is about
**110 Elo**. The effect was a quarter of the noise before the run started —
the experiment could not have detected it either way, and the +24 that came
out is a coincidence of the same size as the thing being looked for.

Both numbers above — **1514** and **1538** — were measured against the ladder
running **evaluation v2**, before the rook-on-open-file term was adopted. They
are kept here as the record of what was measured when.

### The third run, and the explanation it killed

The rook term shipped (+44 Elo, `positional_score`), so the gauntlet was run
again against the ladder as it now stands. This time at **120 games per
pairing instead of ten**, because the earlier runs had a standard error near
110 Elo and were being read as though they did not.

| matchup | games | score | W-D-L | implied | 95% interval |
|---|---:|---:|---:|---:|---:|
| atropos vs L4 | 120 | 74.6% | 60-59-1 | 1387 | [1321, 1468] |
| atropos vs L5 | 120 | 61.3% | 45-57-18 | 1580 | [1518, 1647] |
| atropos vs L6 | 120 | 11.2% | 5-17-98 | 1441 | [1309, 1523] |
| atropos vs L7 | 120 | 11.7% | 1-26-93 | 1748 | [1620, 1830] |

**Performance rating: 1518** (evaluation v3-rooks, 480 games). Next to 1538
and 1514 that looks like stability, and reading it that way would be the third
mistake in this section.

Look at the implied ratings instead. They span **361 Elo**, and at 120 games
apiece **their intervals do not overlap**: L4 says [1321, 1468] and L5 says
[1518, 1647], with nothing in between. The earlier README explained that
scatter as sampling noise — "twelve games per pairing has a standard error
near 14%". **Ten times the games says otherwise.** The scatter is not noise.
It is structure, and it means no single number describes Atropos against this
ladder at all.

A rating is only as good as its opponents' ratings. Solve the gauntlet the
other way round — take Atropos as the fixed point and ask where each rung sits
relative to it — and the reason comes out:

| gap | nominal | this gauntlet (480 games) | the ladder's own SPRT |
|---|---:|---:|---:|
| L4 → L5 | 300 | **+107** [+11, +204] | +132 [+45, +240] |
| L5 → L6 | 300 | **+438** [+319, +557] | +361 [+134, +800] |
| L6 → L7 | 300 | **−7** [−148, +134] | +93 [+21, +174] |

Two instruments that share no code path agree with each other and disagree
with the labels — in *both directions*. The L5 → L6 step, where quiescence,
the transposition table, killers and MVV-LVA all arrive at once, is half again
larger than its label. The L6 → L7 step is not there at all. **300 falls
outside the measured interval for all three gaps.**

Fixed-depth Stockfish, an engine with no connection to either, reads the last
row the same way: 4 Elo, [−47, +40] (next section).

So the honest statement about Atropos is not a rating. It is this: **it plays
between Level 5 and Level 6, closer to Level 5, and the distance between those
two rungs is about 440 Elo rather than the 300 their names claim.**

The interesting part is *why* it stops there. Atropos has everything Level 6
has — quiescence, a transposition table, killers, MVV-LVA — and scores 11.2%
against it over 120 games. What it does not have is throughput: measured on
the same five positions at depth 4 it runs at **8,938 nodes/second against
this engine's 41,817**, so at the same clock Level 6 simply searches deeper.
Feature parity, four and a half times the speed, and — now that the gap has
actually been measured rather than read off a label — **about 440 Elo.**

### An outside ruler, and what it caught

Atropos measured the ladder's *spacing*, but not its offset: it has no
published rating either, so it cannot say where the whole scale sits. **Stockfish 18 at fixed depth** was the next
instrument (`docs/ANCHOR.md`). Fixed *depth*, not `Skill Level`: the skill
settings make the engine blunder on purpose, and deliberate mistakes add
variance that has nothing to do with the strength being measured.

162 games each, 0.1s per move on our side, against Level 7:

| opponent | score | Elo vs L7 | 95% interval | SPRT |
|---|---:|---:|---:|---|
| Stockfish depth 1 | 47.5% | −17 | [−48, +13] | no verdict |
| Stockfish depth 2 | 58.6% | +61 | [+23, +100] | accepted |
| Stockfish depth 3 | 60.2% | +72 | [+41, +104] | accepted |

Depth 1 is Level 7's equal. Depths 2 and 3 cannot be told apart from each
other. All three land inside a 90-Elo band, because Stockfish's "depth 1"
already carries a quiescence search and an NNUE evaluation — most of its
strength is present at the first ply, and the next two add little. **A depth
number from one engine does not name the same work as the same number from
another.**

The pairing that earned its cost was the extra one: the *same* opponent
against **Level 6**. It scored −21 there against −17 against Level 7, which
puts the two rungs **4 Elo apart, interval [−47, +40]**, where their labels
claim 300. That is the measurement written up two sections above — the reason
the "Target Elo" column is a column of names.

What it does **not** give is an absolute rating. Fixed-depth Stockfish appears
on no published list — CCRL and CEGT rate engines at time controls — so
Level 7's absolute Elo can only be stated as a conditional: given an assumed
R(d) for the Stockfish configuration used, Level 7 is R(1) + 17 ± 30, or
R(2) − 61 ± 39, or R(3) − 72 ± 31. Those ± are the statistical part and more
games would shrink them. R(d) is the part that no amount of play here can
reduce, and getting it means playing a rated engine at a rated time control,
or entering the Lichess bot pool.

## What a doubling of speed is worth

Every optimisation here was reported in nodes per second, which is not a unit
anyone cares about. Level 7 against a deliberately slowed copy of itself, node
budget halved four times, 240 games per pairing, 960 games. Brackets,
predictions and the falsifiable claim were committed before the first game
(`b84fd6e`).

| budget | measured | 95% interval | predicted |
|---|---:|---:|---:|
| B/2 | **−159** | [−212, −113] | −60 |
| B/4 | **−417** | [−518, −349] | −120 |
| B/8 | **−636** | [−911, −532] | −180 |
| B/16 | **−830** | [−2400, −678] | −240 |

**−207 Elo per doubling, interval [−251, −164].** The least-squares fit reports
±5; that treats the four points as exact when their own errors run ±25 to
±153. The propagated interval is the one to quote.

That number turned out to be about the *instrument* as much as the engine —
see the third arm below. **The conversion to use is measured on the clock:
−171 [−194, −149]**, across four points from 0.34 to 2.04 doublings.

Every point missed its prediction, in the same direction, by two and a half
times. The predictions came from published doubling curves for classical
engines (50–70 Elo), measured at long time controls where a doubling adds a
ply to a search that already has fifteen. Here the reference budget reaches
depth 3.0 and B/2 reaches 2.0 — a doubling is the difference between seeing a
three-move tactic and not seeing it. **Elo per doubling is not a constant of
an engine; it is a property of the part of the curve you measure in.**

The pre-registered claim — linearity in log2(budget) — survives: residuals
+48, −2, −14, −1 against per-point errors of ±25 to ±153.

### The third arm, and the number it overturned

The cross-check left ~90 Elo unexplained at B/8, so a third arm was built: a
node budget enforced **only between iterations**, no clock involved.
Pre-registered with two outcomes 92 Elo apart. **It landed outside both** — at
−165 [−213, −122] against predictions of −349 and −257 — which fired the
falsification clause and sent the curve itself back for examination.

That took no games at all:

| budget | enforcement | nodes spent | depth reached |
|---|---|---:|---:|
| 5000 | hard | 5000 | 3.00 |
| 2000 | soft | 3422 | 3.00 |

**A hard budget spends 46% more nodes to reach the same depth**, because it is
interrupted mid-iteration and that iteration is thrown away. Every rung of the
original experiment carried that overhead, so −207 was measuring what a node
is worth *and* what truncation costs, together.

| enforcement | Elo per real doubling | 95% interval |
|---|---:|---:|
| hard node limit | −207 | [−251, −164] |
| **clock** (4 points) | **−171** | [−194, −149] |
| soft node limit | −98 | [−126, −69] |

Hard and soft do not overlap; the clock sits between and is not separable from
the hard arm. **How a budget is enforced is a first-order variable in this
measurement** — that much is established, a precise ordering of all three is
not. A hard node budget is an experimental instrument; nothing plays that way.

Recomputed on the clock arm: Atropos's 2.6-doubling throughput deficit is
**−445** [−504, −386] against a 480-game measured gap of about −440. The hard
arm had predicted −537 and was failing that check quietly.

Getting the clock arm to four points was the longest thread in the project and
it is worth the two paragraphs. A third point rejected the through-origin fit
(χ² = 13.8 on 2 dof); a fourth localised the whole misfit to B/2; replaying
B/2 with fresh games moved it from −201 to −116, **two runs of the same
pairing differing at p = 0.015**.

The fault was not the point but the error bars. Each carried only binomial
noise, while the clock arm's node spend drifts run to run by up to 5.3% —
another ±13 Elo that no binomial interval contains. That drift had already
been measured and written down one document earlier; it was applied to the
slope estimate, where it changed nothing, and not to the per-point errors,
where a goodness-of-fit test lives. With it included: **χ² = 7.4 on 3 dof,
nothing rejected, nothing discarded.** See
[`docs/SPEED_CLOCK2_PREREG.md`](docs/SPEED_CLOCK2_PREREG.md).

### The cross-check that disagreed

The same halvings were also run as *movetime* divisions, on the assumption
that the two are the same slowdown spelled differently. At B/2 they agree. At
B/8 they do not overlap: −636 [−911, −532] against **−332 [−409, −273]**.

Measuring what each budget actually spends shows why. A movetime division by
eight is a node division by **four** — 0.09 s buys 6144 nodes rather than the
5000 the node arm starts from, and at 11 ms the spend runs from 569 to 2048
nodes, the top of that range being exactly one `check_interval`. The clock was
never dividing the quantity the experiment was varying.

Correcting for that closes B/2 and leaves B/8 about 90 Elo unexplained, just
outside its interval. Two mechanisms could do it — an unevenly spent budget is
worth more than a fixed one, or a node limit truncates mid-iteration where a
clock stops at a boundary — and **this design does not separate them**. It is
recorded as open rather than resolved by picking the better-sounding story.
Full write-up in [`docs/SPEED.md`](docs/SPEED.md).

### What it costs the rest of the project

The +39% speedup is worth **+81 Elo** [+71, +92], not the +29 the rule of
thumb suggested.

Atropos runs 2.6 doublings slower than this engine (8,938 nps against
~54,000). At −171 per doubling that is **−445 Elo from throughput alone**
[−504, −386], against a measured gap to Level 6 of about 440. Nothing about
the evaluation needs to be invoked to explain why an engine with feature
parity loses.

### Using the curve to predict a change, then testing the prediction

Static exchange evaluation was the one item on Atropos's Phase 17 list with no
counterpart here. It plays an exchange out on a square — each side recapturing
with its cheapest attacker — so quiescence can skip captures that lose material
to the recapture.

Counted first, deterministically, at fixed depth: **24.7% fewer nodes, 23.3%
less wall time, the same move in all 8 book positions.** SEE costs about 2% of
throughput to compute and the saving is net of that.

The speed curve turns that into a prediction rather than a hope. 23.3% less
time to depth is 0.38 doublings, which on the clock arm is **+66 Elo
[+57, +74]** — pre-registered at +79 from the hard arm, before that arm was
known to be the wrong one; the conclusion below is unaffected either way — in [`docs/SEE_PREREG.md`](docs/SEE_PREREG.md)
along with what each outcome would mean, before any game was played.

| run | games | Elo | 95% interval |
|---|---:|---:|---:|
| sequential (SPRT) | 120 | +73 | [+20, +130] |
| **fixed length** | **240** | **+48** | **[+11, +87]** |

The pre-registration said an interval spanning both +79 and +20 is a null
result on the magnitude question and would be reported as one. **It spans
both.** SEE pruning is better than not having it — both intervals exclude zero
— and how much better is unresolved between +11 and +87.

The sequential run said +73 and the fixed run said +48, which is the direction
the stopping-rule bias predicts. It does not demonstrate it: the intervals
overlap across most of their length, and 25 Elo between two samples this size
is ordinary noise. Worth recording precisely because it is easy to over-read.

The flag is **off by default**. The effect is positive, but Level 7 is the rung
the Stockfish anchor and the Atropos gauntlet were both measured against.
Turning it on changes the instrument every current number was taken with —
a decision about what the ladder is for, not one the data settles.

## Where the time actually went

Three measurements in a row pointed at throughput — Atropos losing 440 Elo to
Level 6 on speed alone, and Evaluation v3 failing because it cost too much per
leaf. So the search got profiled instead of guessed at.

The profile said one thing loudly: **1,318,794 move generations for 199,916
nodes** — 6.6 per node, where one would do. Quiescence was building the full
legal move list and then filtering it down to the captures, and quiescence is
69% of all nodes searched.

`python-chess` will generate only the captures if asked. Adding the quiet
promotions separately (a pawn stepping onto the last rank is as forcing as
anything) makes the two lists identical — verified move-for-move across 400
random positions — at a fraction of the cost:

| | |
|---|---:|
| build all legal moves, then filter | 36.8 µs |
| generate the loud moves directly | 8.3 µs |

The second change was the pawn structure, which counted doubled and isolated
pawns with a loop over eight files. The standard bitboard file-fill does the
same job in about ten integer operations. It is exactly equivalent — asserted
against the old counters across 1,600 colour-positions — and the first attempt
was *wrong*, marking every pawn doubled because a bidirectional fill covers a
whole file and a file is trivially above itself. The equivalence test caught it
on the first run.

| depth-4 bench, five positions | nps |
|---|---:|
| before | 41,817 |
| generating loud moves directly | 51,000 |
| plus the bitboard pawn structure | **58,138** |

Same tree, same node counts — 108,966 either way. **+39% for free**, and move
generation fell from 6.6 per node to 2.1.

Two things worth saying about it. Micro-benchmarking the pawn structure in
isolation showed a change of 0.3µs and the full evaluation reading *slower*,
which was noise; only the search-level measurement, repeated, showed the real
gain. And a speedup invalidates every rating measured before it — the Atropos
calibration below was taken against the slower ladder.

## Evaluation v3, and why it is not the default

Passed pawns, rook files and king safety went in, measured, and **did not
ship**. The terms exist, they are correct, and they are behind a flag.

A new evaluation term is always an improvement on paper — it knows something
the old one did not. In a search it is also a cost: every microsecond at a leaf
is depth not searched, and depth is the strongest thing an engine has. The two
effects point in opposite directions and no amount of reasoning settles which
is larger. So they played, at the same search and the same time per move, with
only the evaluation different:

| | score vs v2 | Elo | verdict |
|---|---:|---:|---|
| **v3-full** (with the attacker term), 60 games | 43.3% | −47 | not an improvement |
| **v3-shelter** (without it), 359 games, SPRT | 49.7% | −2 | **rejected** |

v3-full was settled in sixty games: one standard error the wrong side of level,
weak evidence it is worse and firm evidence it is not better.

v3-shelter took 359 and is the more interesting one, because the answer changed
three times on the way:

| games | score | Elo | LLR |
|---:|---:|---:|---:|
| 64 | 58.6% | +60 | +1.00 |
| 198 | 57.1% | +49 | **+2.31** |
| 313 | 52.7% | +19 | −0.07 |
| 359 | 49.7% | **−2** | **−2.96** → rejected |

At 198 games the likelihood ratio was **0.63 away from accepting it** as a
forty-Elo improvement. A fixed match that happened to stop there — or a
slightly looser bound — would have shipped it. A hundred and sixty games later
the evidence had crossed the *opposite* bound and the effect was gone: 49.7%,
a point estimate of −2 Elo.

The original sixty-game match read 54.2% and was dismissed as noise. It was
closer to the truth than the sequential test's own reading at 64 games. The
lesson is not that sequential testing is always right — it is that a small
sample errs in both directions, and the only thing that reliably tells you
*when to stop believing a number* is a test that knows what evidence it still
needs.

The two results together say something more useful than either alone: the
knowledge is worth having, but only while it is cheap. The king-attacker term
is 58% of the cost of the whole module, and adding it is what turns a possible
small gain into a measured loss. v3-full runs at 17.5µs per leaf against v2's
6.5µs — two and a half times the price for knowledge the search was mostly
finding anyway. That is the Atropos calibration's lesson from the other
direction: **feature parity loses to throughput.**

Neither variant is the default: both were measured, both failed.

### Testing the terms one at a time

A bundle failing says nothing about its parts, so the terms were separated —
which parallel game generation made affordable (six workers, ~250 games per
twelve minutes against ~50 serially).

| term | cost vs v2 | games | score | Elo | 95% interval | verdict |
|---|---:|---:|---:|---:|---:|---|
| passed pawns only | 1.4× | 714 | 51.5% | +11 | [−12, +34] | unresolved |
| rook open files only | 1.3× | — | — | — | — | running |

The passed-pawn run is stopped rather than finished, and the reason is worth
being plain about: the bracket asks "is this worth at least 30 Elo?" and the
answer is converging on something near +10. Resolving an effect that size needs
a much narrower bracket and several thousand games. **Not shown to win is not
adopted**, so it stays off — but "unresolved" is the honest label, not
"rejected".

There is a structural reason to expect these terms to be small here, and it is
visible in the tables rather than inferred from the results:

| pawn on rank | PST endgame bonus | passed-pawn bonus | total |
|---:|---:|---:|---:|
| 4 | 20 | 40 | 60 |
| 6 | 50 | 120 | 170 |
| 7 | 80 | 200 | 280 |

The piece-square table already pays a pawn for advancing, and the passed-pawn
term pays it again on top. The same overlap covers king shelter, which restates
what `KING_MG` already encodes by pushing the king to the corner. Rook files
are the one term of the three a table genuinely *cannot* express — where a rook
stands is in the table, whether the file under it is open depends on pawns the
table cannot see — which is why it is being tested separately.

That is a structural observation about the tables, not a conclusion about the
results. It was briefly written up here as the latter, on the strength of a −3
Elo reading that moved to +21 a hundred games later.

### Fixed-length matches ask the wrong question

Three times in this project a fixed match came back "inside the noise" — Level 7
at six games, v3-shelter at sixty, the speedup calibration at ten — each time
after spending the whole budget to learn nothing. The last one was the clearest
mistake: a 39% speedup is worth about **+29 Elo** and one standard error on a
ten-game pairing is about **110**, so the experiment could not have detected the
effect before it started.

`elo/sprt.py` fixes the design. After every game it asks how much likelier the
results are under "worth at least *elo1*" than under "worth at most *elo0*",
and stops the moment the ratio is decisive. A clearly good change is confirmed
in a couple of hundred games, a clearly bad one rejected as fast, and only a
change sitting exactly on the boundary costs the full budget — which is the
case where the games are genuinely needed.

The probability model is BayesElo's, with the draw rate estimated from the
games rather than assumed: draws carry almost no information about which side
is better, so a pairing that draws 80% of the time needs far more games than
one that does not.

Simulated, to pick a bracket the compute budget can afford:

| bracket | true +0 | true +30 | true +60 |
|---|---:|---:|---:|
| [0, 10] | 1200+ games | 1128 | 549 |
| [0, 25] | 822 | 450 | 220 |
| **[0, 40]** | **344** | **326** | **159** |

`[0, 40]` asks a coarser question — "is this worth at least forty Elo?" — and
answers it in about an hour instead of four. `scripts/sprt_match.py` runs it in
resumable chunks, writing state after **every game**, because anything that
takes an hour gets interrupted eventually. It has been, four times, and no
games were lost.

### What the test says while it is still running

"Continue" is not an answer. Alongside the likelihood ratio the test reports a
confidence interval in Elo and, when it has not decided, why:

```
292 games  +133 =49 -110  (53.9%)  LLR +0.90  Elo [-8, +62]  continue
the interval [-8, +62] still spans the whole bracket [+0, +40] — more games
```

That is a real answer where a bare percentage is not. It also exposes a trap
worth naming: **a match that is all draws has a perfectly precise score and no
information at all.** Precision is not evidence, and engine matches draw often
enough for that to matter.

### A bracket chosen before the data

Midway through, the point estimate sat near +27 Elo — the middle of the
bracket, and the one case an SPRT resolves slowest because the evidence favours
neither hypothesis. `[0, 20]` would have decided it far sooner *if* +27 had
been the truth.

Moving the bracket at that moment would have been choosing the hypothesis to
fit the data, so it stayed where it was set — and the run went on to settle at
−2 Elo, where the original bracket was fine and the "better" one would have
been fitted to a number that turned out to be noise.

Two things were worth keeping from the exercise. The endgame skip (king safety
is not computed once the phase makes it worth nearly nothing) took the term
from 12.1µs to 2.4µs there, and the passed-pawn scan now returns both phases
from one walk instead of scanning twice. Neither changes a score; both are
free.

## The app

```bash
make run            # streamlit run app/streamlit_app.py
```

* **Play** — click-to-move against any level, with an evaluation bar, the
  engine's search statistics, undo, PGN export, and optional per-move
  commentary from Claude.
* **Watch** — two levels against each other, live evaluation graph, speed
  control.
* **Tournament** — round-robin, Swiss or gauntlet, with live progress; results
  go straight into the rating database.
* **Leaderboard** — ratings, rating history, head-to-head matrix.
* **Analysis** — one position, every level's answer side by side.

Or from the command line:

```bash
make tournament     # round-robin over the whole ladder
make gauntlet       # one level against the field
make leaderboard    # the current table
```

Get an engine by level:

```python
from engine.levels import create_engine

engine = create_engine(4, seed=42)
result = engine.analyse(board)     # -> SearchResult(move, score, depth, nodes, ...)
```

Play engines against each other:

```python
from tournament.match import play_match
from tournament.openings import book

match = play_match(create_engine(4), create_engine(3), openings=book())
print(match.summary())             # 'L4-AlphaBeta vs L3-Minimax: +13 =2 -1 (87.5%)'
```

### Where the language model goes — and does not

The obvious reading of "hybrid evaluation" is to route each search *leaf* to
a cheap or expensive evaluator. That does not survive contact with the
numbers: a leaf evaluation costs about six microseconds and a language model
costs seconds — six orders of magnitude apart. So the routing happens once,
at the root, where a millisecond of thought can redirect seconds of search.
Level 8 uses a complexity estimate to stretch or shrink its clock, and will
consult a model only to break a tie between moves the search has already
vetted. The engine calculates; the model explains and, at most, chooses
between two answers it was handed.

Every language-model feature is optional. With no `ANTHROPIC_API_KEY` the
engine plays, the tournaments run and the whole test suite passes; the
commentary is simply an empty string.

### A note on Zobrist hashing

The transposition table is not keyed on a Zobrist hash, and that is
deliberate. `chess.polyglot.zobrist_hash` recomputes from scratch at ~10µs
per call — more than twice the cost of the whole evaluation the table exists
to save. Maintaining the key incrementally instead would mean shadowing
python-chess's own make/unmake logic, where one missed XOR silently returns
the wrong move. python-chess already maintains an equivalent position key for
its repetition detection, and reading it costs ~0.4µs. `search/transposition.py`
uses that.

## License

MIT
