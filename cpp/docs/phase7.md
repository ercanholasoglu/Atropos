# Phase 7 expected behavior

Phase 7 adds iterative deepening on top of the asynchronous UCI search worker.

## Implemented

- `search_iterative` API
- Per-depth callback for completed depth results
- Cumulative node reporting across iterative depths
- UCI emits `info` for every completed depth
- Final `bestmove` comes from the last available iterative result
- Node, time and external stop limits carry across iterative depths

## Notes

- There is no aspiration window yet.
- Principal variation from the prior depth is not used for move ordering yet.
- Search still uses one worker thread and a single-threaded search core.
