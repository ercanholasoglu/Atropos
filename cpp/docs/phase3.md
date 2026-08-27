# Phase 3 expected behavior

Phase 3 turns Atropos from a legal-move fallback into a minimal searching
engine.

## Implemented

- Material-only static evaluation
- Fixed-depth negamax search
- Alpha-beta pruning
- Mate and stalemate terminal scoring
- Principal variation collection
- UCI `go depth <n>` routed through search
- UCI `info depth ... score cp ... nodes ... pv ...` output

## Notes

- Move ordering is still board-order only.
- Evaluation intentionally ignores piece-square tables, mobility, king safety
  and pawn structure.
- Search is synchronous and does not yet honor time, node or stop limits.
- `go` without a depth defaults to depth one.
