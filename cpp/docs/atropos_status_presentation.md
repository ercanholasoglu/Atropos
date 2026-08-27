# Atropos Status Presentation

## 1. Executive Summary

Atropos is now a working UCI chess engine prototype at Phase 15.

It has moved from a protocol scaffold to a real engine loop:

- legal move generation
- make/unmake
- perft validation
- handcrafted evaluation
- alpha-beta search
- quiescence
- iterative deepening
- transposition table
- killer/history ordering
- async UCI search
- basic time/node limits
- benchmark and tactical regression infrastructure
- cached Zobrist hashing
- allocation-light search move buffers
- deterministic self-play strength tracking

It is not yet a strong chess engine. The current objective is still engineering
correctness, measurement, and search/eval infrastructure.

## 2. What Has Been Built

### Phase 0: Project Foundation

- CMake build
- Unit test harness
- CI scaffold
- Minimal UCI loop
- UCI command parsing
- `scripts/check.sh`

### Phase 1: Board And Legal Chess

- Board representation
- FEN parse/serialize
- Legal move generation
- Check detection
- Castling legality
- En passant legality
- Promotions
- `make_move` / `unmake_move`
- Repetition keys
- Fifty-move state
- UCI `position ... moves ...`

### Phase 2: Perft Correctness

- Recursive perft
- Divide output
- Known-node fixtures
- `perft <depth>`
- `go perft <depth>`

### Phase 3-5: Basic Search

- Material evaluation
- Fixed-depth negamax
- Alpha-beta pruning
- Mate/stalemate scoring
- Node limits
- Deadline limits
- UCI `go depth`, `go nodes`, `go movetime`

### Phase 6-7: UCI Search Runtime

- Worker-thread search
- Cooperative `stop`
- `quit` / `position` / `ucinewgame` safely stop active search
- Iterative deepening
- Per-depth UCI `info`
- Principal variation output

### Phase 8-9: Search Acceleration

- Transposition table
- TT exact/lower/upper bounds
- TT move ordering
- Killer moves
- History heuristic
- UCI metrics: `tthits`, `killers`, `history`

### Phase 10: Evaluation V2

- Piece-square tables
- Lightweight mobility
- Bishop pair bonus
- Doubled pawn penalty
- Isolated pawn penalty

### Phase 11-15: Measurement And Performance Foundation

- `bench [depth]`
- Fixed benchmark positions
- Tactical regression fixtures
- Cached Zobrist hash
- Hash consistency tests
- Allocation-light movegen overloads
- Ply-scoped search move buffers
- `selfplay [games] [depth] [maxplies]`
- Score-derived Elo-difference reporting

## 3. Current Engine Capabilities

Atropos can currently:

- run as a UCI engine
- parse positions from FEN or startpos
- search asynchronously
- stop active search
- search with depth, node, movetime and basic clock limits
- run infinite/ponder-style searches
- produce legal best moves
- validate movegen through perft
- run a deterministic benchmark suite
- run tactical bestmove regression tests

Useful commands:

```text
uci
isready
position startpos
go depth 4
go nodes 10000
go movetime 1000
go infinite
stop
perft 3
bench 3
selfplay 4 1 80
quit
```

## 4. Where We Are

Atropos is past the “toy scaffold” stage.

It is now a small but real classical chess engine with:

- correct legal move generation
- validated state transitions
- real alpha-beta search
- practical UCI behavior
- early search heuristics
- early handcrafted evaluation
- regression and benchmark infrastructure
- first internal strength tracking harness

The main gap is no longer “can it play?” The main gap is now “how well does it
play, and can we measure improvements rigorously?”

## 5. What Is Missing

Core missing work:

- stronger time management
- larger tactical suite
- benchmark baselines
- external gauntlet infrastructure
- calibrated Elo estimation pipeline
- evaluation v3
- tapered evaluation
- passed pawns
- open/semi-open files
- richer king safety
- late move reductions
- aspiration windows
- static exchange evaluation
- NNUE feature extraction
- NNUE inference
- NNUE training pipeline

## 6. Can We Estimate Elo Now?

Not as an absolute public rating.

A real Elo estimate requires games against calibrated opponents under controlled
conditions. Atropos now has a deterministic internal `selfplay` command, but it
does not yet have external opponent gauntlet results or a rating calibration set.

Any exact absolute Elo number today would still be speculation.

What we can say qualitatively:

- It should now play legal complete chess games.
- It has enough search infrastructure to beat random/legal-move players.
- It can produce a repeatable internal score and score-derived Elo difference.
- It is still likely weak versus established engines because evaluation,
  reductions, time management and tuning are early.

## 7. How We Should Measure Elo

Recommended measurement stack:

1. Build Atropos as a UCI engine.
2. Install a tournament runner:
   - cutechess-cli
   - fastchess
3. Choose calibrated opponents:
   - Fairy-Stockfish weakened levels
   - Stockfish skill levels
   - micro-Max
   - Vice
   - Sunfish-like engines
4. Run fixed time controls:
   - `10+0.1`
   - `60+0.6`
   - optionally depth-limited games for debugging
5. Run at least:
   - 100 games for rough signal
   - 400+ games for useful confidence
   - 1000+ games for stable comparisons
6. Track:
   - score percentage
   - Elo diff
   - confidence interval
   - crashes/time forfeits
   - illegal moves

Example future command:

```sh
cutechess-cli \
  -engine cmd=./build/atropos name=Atropos \
  -engine cmd=stockfish name=Stockfish-skill1 option.SkillLevel=1 \
  -each tc=10+0.1 proto=uci \
  -games 200 \
  -repeat \
  -concurrency 4 \
  -pgnout games/atropos_vs_stockfish_skill1.pgn
```

## 8. Near-Term Roadmap

### Phase 14: Allocation-Light Move Lists

Status: done.

Delivered:

- low-allocation movegen overloads
- reusable legal/pseudo move buffers inside search
- regression coverage that checks output parity

### Phase 15: Strength Tracking

Status: first internal harness done.

Delivered:

- deterministic internal self-play runner
- UCI `selfplay [games] [depth] [maxplies]`
- win/draw/loss distribution
- score-derived Elo-difference calculation

Still remaining for calibrated Elo:

- `games/` output directory
- gauntlet scripts
- cutechess/fastchess runner scripts
- PGN output
- summary parser
- first calibrated Elo estimate

### Phase 16: Evaluation V3

Goal: improve chess quality.

Expected work:

- tapered midgame/endgame eval
- passed pawns
- rook open-file bonus
- king safety terms
- safer queen/king behavior

### Phase 17: Search V2

Goal: improve depth and tactical sharpness.

Expected work:

- aspiration windows
- late move reductions
- static exchange evaluation
- better quiescence filtering
- check extensions

## 9. Current Risk Register

Main risks:

- No external game testing yet
- No Elo baseline
- Move generation is correct by current tests, but broader perft coverage is
  still useful
- Evaluation is still simple
- Time management is not tournament-grade
- No crash/timeout gauntlet yet

## 10. Recommended Next Action

The best next step is Strength Tracking v2: external gauntlet and SPRT-style
rating gates.

Reason:

- Internal self-play exists, but it cannot calibrate absolute Elo.
- We need external opponents, fixed time controls and PGN/result logs.
- That gives a concrete baseline before heavier eval/search tuning.

## 11. One-Slide Summary

Atropos today:

- Phase 15 complete
- Legal chess engine
- UCI-compatible
- Alpha-beta + quiescence
- Iterative deepening
- TT + killer/history
- Handcrafted eval
- Bench and tactical tests
- Cached Zobrist
- Search move buffers
- Self-play strength harness

Not yet:

- calibrated external Elo
- strong time management
- tuned evaluation
- external gauntlet
- NNUE

Next:

1. build external Elo gauntlet
2. measure first calibrated rating
3. improve eval/search from data
