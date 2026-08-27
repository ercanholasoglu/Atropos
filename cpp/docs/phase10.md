# Phase 10 expected behavior

Phase 10 replaces material-only evaluation with a small handcrafted evaluation
model.

## Implemented

- Piece-square tables for all piece types
- Lightweight pseudo-mobility scoring
- Bishop pair bonus
- Doubled pawn penalty
- Isolated pawn penalty
- Side-to-move perspective remains the public `evaluate` convention
- `evaluate_material` remains material-only for tests and diagnostics

## Notes

- Evaluation is still handcrafted and intentionally simple.
- There is no tapered midgame/endgame interpolation yet.
- King safety is limited to the king piece-square table.
- Pawn structure does not yet include passed pawns, backward pawns or open files.
- NNUE is not implemented.
