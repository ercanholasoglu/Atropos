"""Tie the ladder to an outside reference, and say how loosely it is tied.

Every rating in this project is in the ladder's own nominal units. Those are
internally consistent and could still be uniformly wrong, and nothing measured
against Atropos fixes that — Atropos has no published rating either.

Stockfish does, which makes it the reference. Two decisions about how it is
used:

**Fixed depth, not Skill Level.** Skill Level makes Stockfish blunder on
purpose; the levels are not evenly spaced in Elo and the deliberate mistakes
add variance that has nothing to do with the strength being measured. A fixed
depth is a fixed, reproducible player.

**One rung, not one each.** The ladder's own pairings are already verified
sequentially, so anchoring a single rung anchors all of them. Measuring every
Stockfish depth against the same level keeps the three estimates on one scale
instead of chaining three separate comparisons.

## Declared before the runs

* Reference rung: **Level 7** — the strongest sequentially verified rung, and
  the closest to all three Stockfish depths in scouting.
* Bracket: **elo0 = 0, elo1 = 100.** An anchor asks how far apart two engines
  are, so the bracket is set where "clearly stronger" sits for engines a rung
  apart, matching the ladder's own pairings.
* Minimum games: **160 per depth**, before the stopping rule is allowed to
  fire. An anchor needs an interval, not a verdict, and a test that stops at
  twenty games gives an interval hundreds of Elo wide.
* Our side plays at **0.1s per move**, the operating point every other
  measurement in this project used.
* Six workers, the measured limit before contention on this machine passes 8%.

## What this can and cannot deliver

It measures the ladder against Stockfish exactly. Turning that into absolute
Elo needs a published rating for Stockfish *at these fixed depths*, which is
not something this repository can establish — it is an external number, and
the mapping is only ever as good as it is. The report states the assumption
separately from the measurement so the two can be corrected independently.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from elo.calculator import elo_diff_from_score
from elo.sprt import Sprt, SprtConfig
from engine.levels import create_engine
from scripts.telemetry import TelemetryRecorder
from tournament.match import play_game
from tournament.openings import OPENING_BOOK
from tournament.uci_engine import UciEngineProcess, UciLimits

REFERENCE_LEVEL = 7
ELO0, ELO1 = 0.0, 100.0
MIN_GAMES = 160
STOCKFISH = "/opt/homebrew/bin/stockfish"


def play_anchor_job(job: tuple[str, int, int, int, float, int]) -> tuple[float, int]:
    """Pool entry point — plain data in, plain data out.

    Separate from :func:`play_anchor_game` because a process pool on macOS
    spawns rather than forks, so whatever it is handed has to be importable
    and take a single picklable argument.
    """
    return play_anchor_game(*job)


def play_anchor_game(
    engine_path: str, depth: int, level: int, index: int, movetime: float, max_plies: int
) -> tuple[float, int]:
    """One game, scored for Stockfish. Returns ``(score, nodes)``."""
    opening = OPENING_BOOK[(index // 2) % len(OPENING_BOOK)]
    sf_is_white = index % 2 == 0

    reference = UciEngineProcess(
        [engine_path], name=f"sf-d{depth}", limits=UciLimits(movetime=None, depth=depth)
    )
    ours = create_engine(level, seed=1000 + index, time_limit=movetime)
    try:
        reference.start()
        white, black = (reference, ours) if sf_is_white else (ours, reference)
        record = play_game(
            white, black, start_fen=opening.fen, max_plies=max_plies, opening=opening.name
        )
    finally:
        reference.close()

    white_score = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}[record.result]
    return (white_score if sf_is_white else 1 - white_score), record.nodes


def run_depth(depth: int, args, recorder: TelemetryRecorder) -> dict:
    config = SprtConfig(elo0=ELO0, elo1=ELO1, max_games=args.max_games)
    test = Sprt(config)
    state = Path(f"data/anchor_sf-d{depth}_vs_L{args.level}.json")
    if state.exists() and not args.restart:
        stored = json.loads(state.read_text())
        test.wins, test.draws, test.losses = stored["wins"], stored["draws"], stored["losses"]
        print(f"  resuming at {test.games} games", flush=True)

    started = time.monotonic()
    deadline = started + args.minutes * 60
    workers = max(1, args.workers)

    def should_stop() -> bool:
        # The stopping rule is held back until there are enough games for the
        # interval to mean something — an anchor is an estimate, not a verdict.
        if test.games >= args.max_games:
            return True
        return test.games >= MIN_GAMES and test.finished

    with ProcessPoolExecutor(max_workers=workers) as pool:
        while not should_stop() and time.monotonic() < deadline:
            jobs = [
                (args.engine, depth, args.level, test.games + offset, args.movetime, args.max_plies)
                for offset in range(workers)
            ]
            for score, nodes in pool.map(play_anchor_job, jobs):
                test.record(score)
                recorder.add_nodes(nodes)
                recorder.add_games()
            print(f"  {test.games} games  {test.summary()}", flush=True)

    low, high = test.elo_interval()
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "depth": depth,
                "level": args.level,
                "wins": test.wins,
                "draws": test.draws,
                "losses": test.losses,
                "games": test.games,
                "score": test.score,
                "elo_vs_level": elo_diff_from_score(test.score),
                "elo_interval_95": [low, high],
                "llr": test.llr,
                "verdict": test.verdict.value if test.games >= MIN_GAMES else "below minimum games",
                "movetime": args.movetime,
                "min_games": MIN_GAMES,
            },
            indent=1,
        )
    )
    return json.loads(state.read_text())


def main() -> int:
    parser = argparse.ArgumentParser(description="Anchor the ladder to Stockfish at fixed depth")
    parser.add_argument("--engine", default=STOCKFISH)
    parser.add_argument("--depths", default="1,2,3")
    parser.add_argument("--level", type=int, default=REFERENCE_LEVEL)
    parser.add_argument("--movetime", type=float, default=0.1)
    parser.add_argument("--max-plies", type=int, default=160)
    parser.add_argument("--max-games", type=int, default=400)
    parser.add_argument("--minutes", type=float, default=12.0, help="budget per depth")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    depths = [int(d) for d in args.depths.split(",")]

    if args.report_only:
        return report(depths, args)

    recorder = TelemetryRecorder(
        "anchor",
        {
            "engine": args.engine,
            "depths": depths,
            "reference_level": args.level,
            "elo0": ELO0,
            "elo1": ELO1,
            "min_games": MIN_GAMES,
            "movetime": args.movetime,
            "max_plies": args.max_plies,
        },
    )
    for depth in depths:
        print(f"stockfish depth {depth} vs L{args.level}", flush=True)
        row = run_depth(depth, args, recorder)
        print(
            f"  -> {row['games']} games, {row['score']:.1%}, "
            f"{row['elo_vs_level']:+.0f} Elo, interval "
            f"[{row['elo_interval_95'][0]:+.0f}, {row['elo_interval_95'][1]:+.0f}], "
            f"{row['verdict']}",
            flush=True,
        )

    recorder.write({"depths": {str(d): run_depth_state(d, args.level) for d in depths}})
    print(f"\ntelemetry: {recorder.summary()}\n           {recorder.path}")
    return report(depths, args)


def run_depth_state(depth: int, level: int) -> dict:
    path = Path(f"data/anchor_sf-d{depth}_vs_L{level}.json")
    return json.loads(path.read_text()) if path.exists() else {}


def report(depths: list[int], args) -> int:
    print()
    print(
        f"{'reference':<18} {'games':>6} {'score':>7} {'Elo vs L' + str(args.level):>12} {'95% interval':>18}"
    )
    print("-" * 68)
    for depth in depths:
        row = run_depth_state(depth, args.level)
        if not row:
            print(f"{'stockfish d' + str(depth):<18} {'-':>6} {'not run':>7}")
            continue
        low, high = row["elo_interval_95"]
        print(
            f"{'stockfish d' + str(depth):<18} {row['games']:>6} {row['score']:>6.1%} "
            f"{row['elo_vs_level']:>+12.0f} {f'[{low:+.0f}, {high:+.0f}]':>18}"
        )
    print("-" * 68)
    print(
        "These are measured. Converting them to absolute Elo needs a published\n"
        "rating for Stockfish at these fixed depths — an external number this\n"
        "repository cannot establish. See docs/ANCHOR.md for the mapping and\n"
        "what it assumes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
