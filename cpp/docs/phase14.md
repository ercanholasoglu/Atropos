# Phase 14 expected behavior

Phase 14 reduces avoidable move-list allocation in the search hot path without
changing engine behavior.

## Implemented

- `generate_pseudo_legal_moves_into` fills a caller-owned move vector.
- `generate_legal_moves_into` fills a caller-owned legal vector and can reuse a
  caller-owned pseudo-legal scratch vector.
- Existing value-returning movegen APIs remain available for tests, tools and
  simple callers.
- Search owns ply-scoped legal and pseudo-legal move buffers in `SearchContext`.
- Root search, negamax and quiescence reuse those buffers instead of allocating a
  fresh move vector at each node.

## Notes

- This is a conservative allocation reduction, not a complete move storage
  redesign.
- Move ordering and legal filtering behavior are unchanged.
- Later performance phases can replace `std::vector<Move>` with fixed-capacity
  move lists after profiling proves the next bottleneck.

## Coverage

The regression suite checks that the new `generate_legal_moves_into` overload
matches the existing value-returning API on a mixed tactical/castling position.
