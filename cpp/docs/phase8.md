# Phase 8 expected behavior

Phase 8 adds a transposition table to the single-threaded search core.

## Implemented

- Fixed-size transposition table
- Exact, lower-bound and upper-bound entries
- Depth-aware replacement for same-key entries
- Probe/store in full-width negamax
- TT best move ordering
- Cumulative `tt_hits` in search results
- UCI `info ... tthits <n>` reporting when hits occur
- UCI `Hash` option resizes the table
- `ucinewgame` and `position` clear stale entries

## Notes

- Quiescence search does not use the transposition table yet.
- Mate score normalization by ply is not implemented for TT storage.
- The current engine uses one active worker search. TT access is not designed
  for multiple simultaneous search workers.
