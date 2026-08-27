# Phase 6 expected behavior

Phase 6 makes search asynchronous at the UCI engine boundary.

## Implemented

- Worker-thread search for non-perft `go`
- External cancellation flag in `SearchLimits`
- `stop` requests cancellation and joins the active worker
- `quit`, `ucinewgame` and `position` stop any active search before mutating
  engine state
- Engine destructor joins active search
- Deterministic `wait_for_search_idle()` hook for tests

## Notes

- Search itself is still single-threaded.
- Output is emitted by the worker when search exits.
- `stop` is cooperative: search checks the flag at node/deadline checkpoints.
- There is no pondering, infinite search mode, MultiPV or background analysis
  session management yet.
