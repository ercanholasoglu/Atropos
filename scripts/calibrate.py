"""Place an external engine on this project's ladder.

A rating measured only against your own engines is self-consistent and could
still be uniformly wrong. This plays an external UCI engine against the rungs
until it finds the one it matches, which calibrates both sides at once: the
outsider gets a rating in this ladder's units, and the ladder gets a check
that its numbers mean something outside itself.

    python -m scripts.calibrate --engine /path/to/engine --levels 3-7
"""

from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from elo.calculator import elo_diff_from_score, performance_rating
from engine.levels import available_levels, create_engine
from engine.utils.constants import INITIAL_ELO
from tournament.match import play_game
from tournament.openings import OPENING_BOOK
from scripts.telemetry import TelemetryRecorder
from tournament.uci_engine import UciEngineError, UciEngineProcess, UciLimits


def parse_levels(spec: str) -> list[int]:
    if spec == "all":
        return available_levels()
    levels: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            levels.extend(range(int(start), int(end) + 1))
        else:
            levels.append(int(part))
    return [level for level in levels if level in available_levels()]


def finish(row: dict, rating: int, args: argparse.Namespace) -> None:
    """Recompute a pairing's derived numbers from its running counts.

    Called after every game so the checkpoint on disk is always a complete,
    readable record rather than raw tallies waiting to be interpreted.
    """
    played = row["games"]
    row["score"] = (row["wins"] + 0.5 * row["draws"]) / played
    row["implied_elo"] = rating + elo_diff_from_score(row["score"])
    # Reported alongside the point estimate because a twelve-game pairing and
    # a two-hundred-game one produce the same-looking number and mean very
    # different things.
    lo, hi = score_interval(row["score"], played)
    row["implied_interval"] = [
        rating + elo_diff_from_score(lo),
        rating + elo_diff_from_score(hi),
    ]
    row["complete"] = played >= args.games


def write_partial(path: Path, payload: dict) -> None:
    """Write what is known so far, atomically.

    A gauntlet is an hour of play and anything that long gets interrupted.
    Writing only at the end means an interruption in the last pairing throws
    away every pairing before it — which is what happened, once.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1))
    tmp.replace(path)


def score_interval(score: float, games: int) -> tuple[float, float]:
    """95% interval on a match score, normal approximation.

    Here so the implied rating can be printed with the width of its own
    uncertainty; a rung implied by ten games and one implied by two hundred
    look identical without it.
    """
    if games == 0:
        return (0.0, 1.0)
    se = math.sqrt(max(score * (1 - score), 1e-9) / games)
    return (
        min(max(score - 1.96 * se, 1e-6), 1 - 1e-6),
        min(max(score + 1.96 * se, 1e-6), 1 - 1e-6),
    )


def play_calibration_job(job: tuple[str, str, int, int, float, int]) -> tuple[float, int]:
    """One game against one rung, scored for the external engine.

    Module level and taking a single tuple because a process pool on macOS
    spawns rather than forks. Each game gets its own external process: the
    cost is a few milliseconds of startup and the gain is that a match can be
    spread over workers at all, which is the difference between a ten-game
    pairing and one wide enough to have an interval worth reporting.
    """
    engine_path, name, level, index, movetime, max_plies = job

    opening = OPENING_BOOK[(index // 2) % len(OPENING_BOOK)]
    external_is_white = index % 2 == 0
    external = UciEngineProcess([engine_path], name=name, limits=UciLimits(movetime=movetime))
    # Fixed time per move on both sides. Fixed *depth* would compare nothing:
    # one engine's depth 6 is another's depth 3.
    ours = create_engine(level, seed=level * 13 + index, time_limit=movetime)
    try:
        external.start()
        white, black = (external, ours) if external_is_white else (ours, external)
        record = play_game(
            white, black, start_fen=opening.fen, max_plies=max_plies, opening=opening.name
        )
    finally:
        external.close()

    white_score = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}[record.result]
    return (white_score if external_is_white else 1 - white_score), record.nodes


def main() -> int:
    parser = argparse.ArgumentParser(description="Rate an external UCI engine against the ladder")
    parser.add_argument("--engine", required=True, help="path to the external UCI engine")
    parser.add_argument("--name", default=None)
    parser.add_argument("--levels", default="3-7")
    parser.add_argument("--games", type=int, default=8, help="games per level")
    parser.add_argument("--movetime", type=float, default=0.2, help="seconds per move, both sides")
    parser.add_argument("--max-plies", type=int, default=200)
    parser.add_argument("--workers", type=int, default=1, help="parallel games")
    parser.add_argument("--restart", action="store_true", help="discard any resumable run")
    parser.add_argument(
        "--minutes", type=float, default=0.0, help="budget for this chunk; 0 = no limit"
    )
    parser.add_argument("--out", default="data/calibration.json")
    args = parser.parse_args()

    levels = parse_levels(args.levels)
    if not levels:
        raise SystemExit(f"no implemented levels in {args.levels!r}")

    name = args.name or Path(args.engine).name
    if not Path(args.engine).exists():
        raise SystemExit(f"no engine at {args.engine}")

    # One handshake up front, purely to record what the engine calls itself.
    # The games each start their own process, so without this the record would
    # say only which path was executed.
    probe = UciEngineProcess([args.engine], name=name, limits=UciLimits(movetime=args.movetime))
    with probe:
        reported_name = probe.reported_name

    recorder = TelemetryRecorder(
        "calibrate",
        {
            "engine": args.engine,
            "name": args.name,
            "levels": args.levels,
            "games_per_level": args.games,
            "workers": args.workers,
            "movetime": args.movetime,
            "max_plies": args.max_plies,
        },
    )

    print(f"{'matchup':<28} {'score':>7} {'W-D-L':>10} {'implied':>9} {'time':>7}")
    print("-" * 66)

    rows: list[dict[str, Any]] = []
    # Resume only from a file that answers the same question. A record made
    # at a different time control or a different game count is a different
    # experiment, and silently mixing the two would be worse than starting
    # over.
    if Path(args.out).exists() and not args.restart:
        prior = json.loads(Path(args.out).read_text())
        same = (
            prior.get("engine") == name
            and prior.get("movetime") == args.movetime
            and prior.get("games_per_level") == args.games
        )
        if same:
            rows = prior.get("rows", [])
            if rows:
                print(f"resuming: {len(rows)} pairing(s) already played", flush=True)
        elif prior.get("rows"):
            raise SystemExit(
                f"{args.out} holds a run at movetime={prior.get('movetime')} "
                f"games={prior.get('games_per_level')} engine={prior.get('engine')!r}; "
                f"this one is movetime={args.movetime} games={args.games} engine={name!r}. "
                f"Pass --restart to overwrite it or --out to write somewhere else."
            )
    opponent_ratings: list[float] = []
    points = 0.0
    started = time.perf_counter()

    by_level = {row["level"]: row for row in rows}
    deadline = started + args.minutes * 60 if args.minutes else None
    stopped_early = False

    def checkpoint() -> None:
        write_partial(
            Path(args.out),
            {
                "engine": name,
                "reported_name": reported_name,
                "movetime": args.movetime,
                "games_per_level": args.games,
                "rows": rows,
                "performance_rating": None,
                "complete": all(r["games"] >= args.games for r in rows)
                and len(rows) == len(levels),
            },
        )

    for level in levels:
        rating = INITIAL_ELO[level]
        row = by_level.get(level)
        if row is None:
            row = {
                "level": level,
                "level_elo": rating,
                "games": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
            }
            rows.append(row)
            by_level[level] = row
        if row["games"] >= args.games:
            print(f"{name + ' vs L' + str(level):<28} {row['score']:>6.1%}  (resumed)", flush=True)
            continue

        elapsed = time.perf_counter()
        # Games are indexed from where the last chunk stopped, so a resumed
        # run continues the opening book and the colour alternation instead of
        # replaying the same games it already has.
        jobs = [
            (args.engine, name, level, i, args.movetime, args.max_plies)
            for i in range(row["games"], args.games)
        ]
        try:
            workers = max(1, args.workers)
            queue = list(jobs)
            with ProcessPoolExecutor(max_workers=workers) as pool:
                # Only ever `workers` jobs outstanding. Submitting all of them
                # and cancelling on the deadline does not work: a future that
                # the pool has already fed to a worker cannot be cancelled, so
                # the chunk overruns its budget by however much work was
                # queued. Feeding one job per completion keeps the deadline
                # honest and costs nothing.
                pending = {
                    pool.submit(play_calibration_job, queue.pop(0))
                    for _ in range(min(workers, len(queue)))
                }
                while pending:
                    finished = next(as_completed(pending))
                    pending.discard(finished)
                    score_one, nodes = finished.result()
                    recorder.add_nodes(nodes)
                    recorder.add_games()
                    row["games"] += 1
                    if score_one > 0.75:
                        row["wins"] += 1
                    elif score_one < 0.25:
                        row["losses"] += 1
                    else:
                        row["draws"] += 1
                    finish(row, rating, args)
                    checkpoint()
                    if deadline is not None and time.perf_counter() > deadline:
                        # Stop feeding. The games still in flight are already
                        # paid for and are allowed to finish.
                        stopped_early = True
                        queue.clear()
                    if queue:
                        pending.add(pool.submit(play_calibration_job, queue.pop(0)))
        except UciEngineError as error:
            print(f"{name} vs L{level}: aborted — {error}")
            break

        if row["games"] == 0:
            continue
        wdl = f"{row['wins']}-{row['draws']}-{row['losses']}"
        partial = "  (partial)" if row["games"] < args.games else ""
        print(
            f"{name + ' vs L' + str(level):<28} {row['score']:>6.1%} "
            f"{wdl:>10} {row['implied_elo']:>9.0f} "
            f"{time.perf_counter() - elapsed:>6.0f}s{partial}",
            flush=True,
        )
        if stopped_early:
            break

    for row in rows:
        opponent_ratings += [float(row["level_elo"])] * row["games"]
        points += row["score"] * row["games"]

    print("-" * 66)
    if opponent_ratings:
        overall = performance_rating(opponent_ratings, points / len(opponent_ratings))
        print(f"{name} performance rating over the whole gauntlet: {overall:.0f}")
        nearest = min(rows, key=lambda row: abs(float(row["score"]) - 0.5))
        print(f"closest rung: Level {nearest['level']} (scored {nearest['score']:.1%} against it)")
    else:
        overall = None

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "engine": name,
                "reported_name": reported_name,
                "movetime": args.movetime,
                "games_per_level": args.games,
                "rows": rows,
                "performance_rating": overall,
                "complete": True,
                "seconds": time.perf_counter() - started,
            },
            indent=1,
        )
    )
    recorder.write(
        {
            "engine": name,
            "reported_name": reported_name,
            "performance_rating": overall,
            "rows": rows,
        }
    )
    print(f"written to {output}")
    print(f"telemetry: {recorder.summary()}")
    print(f"           {recorder.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
