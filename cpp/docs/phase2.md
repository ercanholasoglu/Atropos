# Phase 2 expected behavior

Phase 2 adds correctness-oriented perft support on top of Phase 1 legal move
generation.

## Implemented

- Recursive perft node counting
- Divide output for root moves
- Fixture-driven known-node regression tests
- `perft <depth>` debug command
- `go perft <depth>` compatibility command

## Notes

- Perft is intentionally simple and mutates a local `Position` copy through
  make/unmake.
- Depth zero returns one node through the core API. The divide API returns no
  root entries for depth zero.
- Perft is a correctness tool, not a benchmark harness. Hot-path profiling and
  allocation reduction remain future work.
