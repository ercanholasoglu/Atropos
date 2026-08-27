# Phase 12 expected behavior

Phase 12 improves UCI search command coverage.

## Implemented

- `go infinite`
- `go ponder`
- `ponderhit`
- Cooperative stop for open-ended searches
- `movestogo` parsing
- Increment-aware clock allocation through `winc` and `binc`
- Clock allocation cap to avoid spending too much remaining time on one move
- Regression coverage for infinite, ponder and clock-form searches

## Notes

- Pondering is minimal: `go ponder` starts a normal background search and
  `ponderhit` marks it as no longer pondering.
- There is no ponder move validation or ponder-specific output policy yet.
- Time management is still simple and deterministic, not tournament-grade.
