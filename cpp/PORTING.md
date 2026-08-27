# The C++ engine

Sixteen phases of a C++ UCI engine, preserved here because until this commit it
had no version control at all — it lived on the Desktop, untracked inside an
accidental repository at `$HOME`, with no history and nothing to roll back to.

The project has since moved to Python at the root of this repository. This tree
is kept as the record of where it came from and as the reference for the phases
still to be ported.

## What has already been ported

| C++ | Python |
|---|---|
| `src/board/` | `python-chess` via `engine/board.py` |
| `src/movegen/` | `python-chess`, verified by `engine/perft.py` |
| `src/perft/` | `engine/perft.py` |
| `src/search/` | `engine/search/` — plus null-move, LMR, aspiration |
| `src/evaluation/` | `engine/evaluation/` — plus tapered eval |
| `src/transposition_table/` | `engine/search/transposition.py` |
| `src/uci/` | `uci/` — plus a `Level` option and time management |
| `src/strength/` | `elo/`, `tournament/`, and `elo/sprt.py` |
| `src/benchmark/` | `engine/perft.py`, `engine/tactics.py` |

## Measured, before deciding to port

Same five positions, depth 4, both engines with quiescence, a transposition
table, killers and history:

| | nodes/second |
|---|---:|
| this C++ engine | 8,938 |
| the Python engine | ~54,000 |

Six times faster in Python, which is not what anyone expects and is worth
saying plainly. The cause is visible in the source: a mailbox board of
`std::array<std::optional<Piece>, 64>`, mobility that walks rays at every leaf,
and `Position` passed into the search by value with its repetition vector in
tow.

## One fix was applied here

`src/main.cpp` gained `std::cout << std::unitbuf;`. Without it the engine never
flushed its output, so `info` and `bestmove` — written from the search worker
thread — sat in the buffer until the process exited. `std::cin` is tied to
`std::cout`, which flushed the handshake by accident and hid the problem. The
engine could not play a game against any GUI, and the Phase 16 gauntlet was
built on top of that.
