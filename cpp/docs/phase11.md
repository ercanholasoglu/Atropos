# Phase 11 expected behavior

Phase 11 adds repeatable benchmark and tactical regression infrastructure.

## Implemented

- Fixed-position benchmark suite
- `benchmark::run(depth)` aggregate metrics
- UCI `bench [depth]` command
- Bench output: depth, positions, nodes, TT hits and elapsed milliseconds
- Tactical fixture file with expected best moves
- Tactical regression test runner

## Notes

- Bench is deterministic enough for local regression checks, not a calibrated
  cross-machine performance score.
- Tactical fixtures are intentionally small. They should grow as search and
  evaluation improve.
- Benchmark uses a shared TT across its fixed positions to exercise TT behavior.
