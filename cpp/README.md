# Atropos

Atropos is a research-oriented open-source UCI chess engine.

Current status: Phase 16. This repository contains the build/test tooling, UCI
process scaffold, board state, FEN parsing/serialization, legal move generation,
make/unmake, check detection, castling, en passant, promotion generation,
repetition-key tracking, fifty-move state, perft correctness tooling,
handcrafted evaluation, fixed-depth negamax search, move ordering and quiescence
search, node limits, basic time deadline handling and worker-thread UCI search
with cooperative stop, iterative deepening, a transposition table, killer moves
and history heuristics, plus benchmark and tactical regression infrastructure.
Position hashing is cached and updated through make/unmake, and search reuses
ply-scoped move buffers to reduce hot-path allocation. A deterministic self-play
strength harness reports result distribution and approximate score-derived Elo
difference. External gauntlet scaffolding is available for calibrated engine
matches through `cutechess-cli`. Richer time management and NNUE are
intentionally not implemented yet.

## Build

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

## Test

```sh
ctest --test-dir build --output-on-failure
```

## Run UCI

```sh
./build/atropos
```

Supported commands:

- `uci`
- `isready`
- `ucinewgame`
- `position startpos`
- `position fen <fen>`
- `go depth <n>`
- `go nodes <n>`
- `go movetime <ms>`
- `go wtime <ms> btime <ms> winc <ms> binc <ms>`
- `go infinite`
- `go ponder`
- `ponderhit`
- `go perft <depth>`
- `perft <depth>`
- `bench [depth]`
- `selfplay [games] [depth] [maxplies]`
- `stop`
- `quit`
- `setoption name <option> value <value>`

`go depth <n>` runs iterative deepening on a worker thread and reports a
principal variation for each completed depth. `go nodes <n>`,
`go movetime <ms>` and basic clock forms route through search limits. `stop`
cooperatively cancels the active worker search.
`go infinite` and `go ponder` run until `stop`, `quit` or a state-changing
command cancels them.

`perft` prints root move divide counts followed by `nodes <total>`.
`bench` prints aggregate fixed-suite search metrics.
`selfplay` runs a small deterministic internal match suite and prints white win,
black win, draw, score-rate, approximate Elo-difference and node totals. It is a
relative tracking tool, not an absolute public Elo claim.

## External Gauntlet

```sh
OPPONENT_CMD=stockfish OPPONENT_NAME=StockfishSkill1 GAMES=100 TC=10+0.1 \
  ./scripts/run_gauntlet.sh
```

The gauntlet script requires `cutechess-cli`, writes PGN/log output under
`games/`, and is intended for calibrated external Elo tracking.
