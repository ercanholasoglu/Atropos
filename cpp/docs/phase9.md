# Phase 9 expected behavior

Phase 9 improves quiet-move ordering with killer moves and history heuristics.

## Implemented

- Two killer move slots per ply
- History score table indexed by from/to square
- Quiet beta-cutoff updates for killer and history tables
- Killer/history scoring for quiet move ordering
- UCI `info ... killers <n> history <n>` reporting when updates occur
- Regression coverage for nonzero heuristic updates

## Notes

- Killer and history tables are local to a single search call.
- Captures and promotions are still ordered by tactical scoring before quiet
  heuristic ordering.
- TT best move keeps highest priority.
- There is no counter-move heuristic or late move reduction yet.
