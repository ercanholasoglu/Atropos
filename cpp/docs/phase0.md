# Phase 0 expected behavior

Phase 0 establishes the repository, C++20 build system, formatting/lint hooks,
CI, test runner and a minimal UCI-compatible process.

## Assumptions

- The engine lives in `atropos/` because the workspace root contains unrelated
  BirdCLEF dataset files and the nearest Git repository root is the user's home
  directory.
- No production chess logic is implemented in this phase.
- `go` returns `bestmove 0000` until Phase 1 and Phase 3 provide legal moves and
  search.
- Malformed commands are ignored or reported to stderr, never stdout.

## Determinism

The scaffold owns options in an `EngineOptions` value. Defaults are:

- `Hash = 16`
- `Threads = 1`
- `Seed = 0`

No global mutable engine state is required for Phase 0.

## Required modules

The module directories exist now. Later phases should add implementation behind
the same logical boundaries:

- `board/state`
- `movegen`
- `zobrist`
- `perft`
- `search`
- `evaluation`
- `transposition_table`
- `time_manager`
- `uci`
- `benchmark`
- `tests`
- `training_tools`
- `nnue`
