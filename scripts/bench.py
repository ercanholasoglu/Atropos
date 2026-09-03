"""A deterministic benchmark, and the distinction it exists to enforce.

Throughput is this project's one reliably measurable lever: a doubling of
search budget is worth about **−171 Elo** (`docs/SPEED.md`), while every
evaluation term tested landed inside its own error bars. So speed changes get
measured, and measuring them needs an instrument that is not a match.

**The distinction.** A change can make the engine faster, or it can make the
engine search *different nodes*, and those are not the same result even when
both show up as "more nodes per second". This benchmark reports them
separately:

* **nodes** — deterministic. The same commit searching the same positions to
  the same depth visits the same nodes, every run. A change here means the
  search or the evaluation behaves differently, and no timing claim is
  comparable across it.

  This was not true until the position key was made process-stable. Five runs
  of this benchmark on one commit gave 188,242, 188,242, 188,246, 188,246 and
  188,246 nodes, because the key was re-drawn every process and that changed
  which positions shared a table slot. The claim above is the point of the
  instrument, so it is now also a test:
  ``test_the_key_is_the_same_in_a_different_process``. Found by the Zobrist
  width experiment (``docs/ZOBRIST.md``), not by the benchmark itself.
* **time** — noisy. Machine load, thermal state and whatever else is running
  move it by a few percent, which is why it is reported with a spread over
  repeats rather than as a single number.

Confusing the two is not hypothetical. Evaluation variants in this project
searched 166,458 nodes against a baseline's 181,238 at the same depth, so
their nps comparison was never measuring computation cost alone.

    python -m scripts.bench
    python -m scripts.bench --level 7 --depth 5 --repeats 5
    python -m scripts.bench --baseline data/bench_baseline.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path

import chess

from engine.levels import create_engine
from engine.tactics import TACTICAL_SUITE
from tournament.openings import OPENING_BOOK

# Openings for the quiet case, tactical positions for the sharp one. A
# benchmark drawn only from the opening book measures one shape of tree.
POSITIONS: tuple[tuple[str, str], ...] = tuple(
    [(f"open:{o.name}", o.fen) for o in OPENING_BOOK]
    + [(f"tact:{p.name}", p.fen) for p in TACTICAL_SUITE]
)


def commit() -> str | None:
    """The commit this is running, or None — never a placeholder."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - environment
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def run_once(level: int, depth: int) -> tuple[dict[str, int], float]:
    """Search every position once. Returns per-position nodes and total seconds."""
    engine = create_engine(level, seed=1, time_limit=None)
    # Levels below 3 have no depth to set; the attribute is on the searching
    # ones only, which is why this is a setattr rather than a plain assignment.
    setattr(engine, "depth", depth)
    nodes: dict[str, int] = {}
    started = time.perf_counter()
    for name, fen in POSITIONS:
        nodes[name] = engine.analyse(chess.Board(fen)).nodes
    return nodes, time.perf_counter() - started


def compare(current: dict, baseline: dict) -> list[str]:
    """What changed, with speed and behaviour kept apart."""
    lines: list[str] = []
    moved = {
        name: (baseline["nodes"].get(name), count)
        for name, count in current["nodes"].items()
        if baseline["nodes"].get(name) != count
    }
    if moved:
        lines.append(
            f"SEARCH CHANGED — {len(moved)} of {len(current['nodes'])} positions visit "
            f"a different number of nodes than the baseline."
        )
        for name, (was, now) in sorted(moved.items())[:5]:
            lines.append(f"    {name:<28} {was:>9,} -> {now:>9,}")
        if len(moved) > 5:
            lines.append(f"    ... and {len(moved) - 5} more")
        lines.append(
            "  The engine is not doing the same work, so the nps figures below "
            "are not a speed comparison."
        )
    else:
        lines.append(
            f"search unchanged — all {len(current['nodes'])} positions visit the same "
            f"nodes as the baseline, so nps is a clean speed comparison."
        )
        ratio = current["nps"] / baseline["nps"]
        change = "faster" if ratio > 1 else "slower"
        lines.append(
            f"  {current['nps']:,.0f} nps against {baseline['nps']:,.0f} "
            f"— {abs(ratio - 1):.1%} {change}"
        )
        # The conversion this project measured, applied only where it is valid.
        import math

        elo = -171 * math.log2(1 / ratio)
        lines.append(
            f"  at the measured −171 Elo per doubling that is {elo:+.0f} Elo " f"(docs/SPEED.md)"
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", type=int, default=7)
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=3, help="timing repeats")
    parser.add_argument("--baseline", default=None, help="a previous run to compare against")
    parser.add_argument("--out", default=None, help="write this run somewhere")
    args = parser.parse_args()

    print(
        f"level {args.level}, depth {args.depth}, {len(POSITIONS)} positions, "
        f"{args.repeats} repeats\n"
    )

    nodes, first = run_once(args.level, args.depth)
    times = [first] + [run_once(args.level, args.depth)[1] for _ in range(args.repeats - 1)]

    # Determinism is the benchmark's whole basis, so it is checked rather than
    # assumed: a second run that visits different nodes means the engine is
    # not reproducible and no comparison it feeds is worth anything.
    again, _ = run_once(args.level, args.depth)
    if again != nodes:
        differing = sum(1 for k in nodes if again.get(k) != nodes[k])
        print(
            f"NOT DETERMINISTIC — {differing} positions differ between two runs "
            f"of the same build. Nothing below is comparable."
        )
        return 1

    total = sum(nodes.values())
    best = min(times)
    result = {
        "commit": commit(),
        "level": args.level,
        "depth": args.depth,
        "positions": len(POSITIONS),
        "nodes": nodes,
        "total_nodes": total,
        # Best of N rather than the mean: the fastest run is the one least
        # interrupted, and interruptions only ever add time.
        "seconds": best,
        "seconds_spread": max(times) - best,
        "nps": total / best,
    }

    print(f"{'position':<30} {'nodes':>10}")
    print("-" * 42)
    for name, count in nodes.items():
        print(f"{name:<30} {count:>10,}")
    print("-" * 42)
    print(f"{'total':<30} {total:>10,}")
    print()
    print(f"  {best:.3f}s best of {args.repeats}  (spread {result['seconds_spread']:.3f}s)")
    print(f"  {result['nps']:,.0f} nodes per second")
    print(f"  commit {result['commit'] or 'unknown'}")

    if args.baseline:
        base = json.loads(Path(args.baseline).read_text())
        if (base["level"], base["depth"]) != (args.level, args.depth):
            print(
                f"\nbaseline was level {base['level']} depth {base['depth']}; "
                f"not comparable to level {args.level} depth {args.depth}"
            )
        else:
            print(f"\nagainst {args.baseline} (commit {base.get('commit') or 'unknown'}):")
            for line in compare(result, base):
                print("  " + line)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=1))
        print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
