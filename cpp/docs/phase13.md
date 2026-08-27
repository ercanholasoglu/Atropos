# Phase 13 expected behavior

Phase 13 makes Zobrist hashing O(1) for callers by caching the position hash.

## Implemented

- Cached `Position::hash()`
- Piece-key updates through `set_piece`
- Side-to-move, castling and en passant key transitions in make/unmake
- Undo-state hash restore
- Regression coverage against reparsed-FEN hashes after legal moves

## Notes

- `hash()` no longer scans all 64 squares.
- `from_fen` computes the initial cached hash once.
- `unmake_move` restores the saved hash from undo state after board/state
  restoration.
- This is a performance foundation for TT-heavy search, not a change to chess
  behavior.
