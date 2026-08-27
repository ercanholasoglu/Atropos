# Phase 4 expected behavior

Phase 4 improves tactical search behavior without changing the material-only
evaluation model.

## Implemented

- Root and interior move ordering
- MVV-LVA-style capture ordering
- Promotion ordering
- Castling preference above quiet moves
- Quiescence search at fixed-depth leaves
- Legal check evasion inside quiescence
- Depth-zero search still reports a legal root move and tactical score

## Notes

- Quiescence currently expands legal captures, promotions and all legal check
  evasions.
- There is a fixed quiescence ply guard for non-check tactical expansion.
- Quiet checks, killer/history heuristics and transposition-table move ordering
  are future work.
