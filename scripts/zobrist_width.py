"""How narrow can the position key get before the table starts lying?

Part (a) of `docs/ZOBRIST_PREREG.md`: count **key collisions** — two different
positions producing the same key — over the positions a perft walk visits.

One property of the key forces the protocol. ``position_key`` is
``hash(board._transposition_key())``, and that tuple holds ``None`` when there
is no en passant square. In CPython ``hash(None)`` is derived from the address
of the ``None`` singleton, so it changes with every process and is not fixed by
``PYTHONHASHSEED``. The key is therefore re-drawn on each run: a collision
count is a sample, not a constant. This script measures one draw; run it
several times and report the spread.

The distinction this measures is the one the table cannot see. An *index*
collision (two keys, one slot) is detected: each entry stores its key and a
mismatch is treated as a miss. A *key* collision is undetectable by
construction — the probe compares keys, they match, and the search is handed
another position's score and move. `TranspositionTable.collisions` counts the
first kind. Nothing counted the second until this.

Two positions are the same position if their full keys agree; a repeat visit
is not a collision. That is why the map is truncated-key to full-key rather
than a simple count.

    python -m scripts.zobrist_width --depth 5
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import chess

from engine.search.transposition import position_key
from scripts.telemetry import TelemetryRecorder

WIDTHS = (16, 24, 32, 48)


Stats = dict[str, int]


def walk(board: chess.Board, depth: int, keys: set[int], stats: Stats) -> None:
    """Depth-first over every position perft would visit, full keys collected."""
    keys.add(position_key(board))
    stats["nodes"] += 1
    if depth == 0:
        return
    for move in board.legal_moves:
        board.push(move)
        walk(board, depth - 1, keys, stats)
        board.pop()


def collisions(keys: set[int], width: int) -> int:
    """Positions that lose their identity when the key is cut to `width` bits.

    Two different positions sharing a truncated key is one collision; the count
    is therefore distinct positions minus distinct truncated keys. Revisiting
    the same position is not a collision, which is why this works from the set
    of distinct full keys rather than from the visit sequence.
    """
    mask = (1 << width) - 1
    return len(keys) - len({k & mask for k in keys})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--fen", default=chess.STARTING_FEN)
    parser.add_argument("--out", default="data/zobrist_collisions.json")
    args = parser.parse_args()

    with TelemetryRecorder(
        "zobrist_collisions", {"depth": args.depth, "fen": args.fen, "widths": list(WIDTHS)}
    ) as recorder:
        keys: set[int] = set()
        stats: Stats = {"nodes": 0}
        started = time.perf_counter()
        walk(chess.Board(args.fen), args.depth, keys, stats)
        elapsed = time.perf_counter() - started
        recorder.add_nodes(stats["nodes"])

        distinct = len(keys)
        print(
            f"perft depth {args.depth}: {stats['nodes']:,} nodes, "
            f"{distinct:,} distinct positions, {elapsed:.1f}s\n"
        )
        print(f"{'width':>6} {'collisions':>12} {'per million':>13} {'expected':>12}")
        rows = []
        for w in WIDTHS:
            c = collisions(keys, w)
            # birthday approximation, the prediction fixed in the registration
            expected = distinct * distinct / (2 ** (w + 1))
            rows.append(
                {
                    "width": w,
                    "collisions": c,
                    "distinct": distinct,
                    "per_million": 1e6 * c / distinct,
                    "expected": expected,
                }
            )
            print(f"{w:>6} {c:>12,} {1e6 * c / distinct:>13,.0f} {expected:>12,.0f}")

        result = {
            "depth": args.depth,
            "nodes": stats["nodes"],
            "distinct": distinct,
            "seconds": elapsed,
            "rows": rows,
        }
        recorder.snapshot(result)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1))
    print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
