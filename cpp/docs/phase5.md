# Phase 5 expected behavior

Phase 5 adds search limits and basic time-control interpretation.

## Implemented

- `SearchLimits` API
- Node limit checks inside negamax and quiescence
- Deadline checks inside negamax and quiescence
- UCI `go nodes <n>`
- UCI `go movetime <ms>`
- UCI `go wtime <ms> btime <ms>` using a simple one-thirtieth allocation
- Search result `stopped` flag
- UCI `info ... string limit` marker when search exits through a limit

## Notes

- Search is still synchronous.
- `stop` still maps to an immediate depth-default search instead of cancelling
  an active worker thread.
- If no depth is provided for a non-perft `go`, Atropos defaults to depth four.
- Time management is deliberately conservative and deterministic enough for
  local testing, not tournament-grade.
