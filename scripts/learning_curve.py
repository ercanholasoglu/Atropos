"""How much self-play does TDLeaf need, and what does it buy?

One point exists: 10,000 games, scored 53.1% against the hand-written tables
over **sixteen games** — an interval of roughly +/-100 Elo, which is to say no
measurement at all. This turns that into a curve, and measures each point at a
length that can carry a conclusion.

**Two things are recorded per point and neither is derivable from the other.**
What the training cost: CPU-seconds, positions seen, wall-clock. And what it
bought: playing strength against the hand-written tables, over enough fixed
games to have an interval. A learning result quoted without its cost is not a
result anyone can act on, because the decision it informs is always "is more
of this worth buying?"

The measure is strength, not weight similarity. A learned table that
correlates with the hand-written one and loses to it has not learned chess;
one that looks nothing like it and wins has. The shape correlation is recorded
alongside, as a description rather than a score.

    python -m scripts.learning_curve --train 1000,3000,10000,30000
    python -m scripts.learning_curve --evaluate --games 240
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import chess
import numpy as np

from elo.calculator import elo_diff_from_score
from research.self_play.value_learner import PieceSquareEvaluator
from scripts.self_play_run import LearnedEngine
from scripts.telemetry import TelemetryRecorder
from tournament.match import play_game
from tournament.openings import OPENING_BOOK

WEIGHTS_DIR = Path("data/learning_curve")
MOVETIME = 0.2


def weights_path(games: int | str) -> Path:
    return WEIGHTS_DIR / f"weights_{games}.json"


def play_one(job: tuple[str, int, int, float, int]) -> tuple[float, int]:
    """One game, learned weights against the hand-written tables.

    Module level and taking plain data because a pool spawns on macOS. The
    weights come from a file rather than the tuple: a full piece-square table
    is 768 floats and pickling it per game is a cost with no purpose.
    """
    path, index, _games, movetime, max_plies = job

    learned = np.array(json.loads(Path(path).read_text())["weights"], dtype=float)
    reference = PieceSquareEvaluator.from_engine_tables().weights

    opening = OPENING_BOOK[(index // 2) % len(OPENING_BOOK)]
    learned_is_white = index % 2 == 0
    a = LearnedEngine(
        PieceSquareEvaluator(learned), name="learned", seed=1000 + index, time_limit=movetime
    )
    b = LearnedEngine(
        PieceSquareEvaluator(reference), name="tables", seed=2000 + index, time_limit=movetime
    )
    white, black = (a, b) if learned_is_white else (b, a)
    record = play_game(
        white, black, start_fen=opening.fen, max_plies=max_plies, opening=opening.name
    )
    white_score = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}[record.result]
    return (white_score if learned_is_white else 1 - white_score), record.nodes


def train(sizes: list[int], args) -> None:
    """Run the learner at each size, keeping what it cost as well as what it learned."""
    import subprocess

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    for games in sizes:
        target = weights_path(games)
        if target.exists() and not args.retrain:
            print(f"{games:>6} games: already trained, skipping")
            continue
        print(f"{games:>6} games: training", flush=True)
        started = time.perf_counter()
        # Reuse the existing runner rather than reimplementing the learner:
        # a second implementation would be a second thing to keep correct.
        subprocess.run(
            [
                ".venv/bin/python",
                "-m",
                "scripts.self_play_run",
                "--games",
                str(games),
                "--seed",
                str(args.seed),
                "--match-games",
                "0",  # strength is measured separately, properly
                "--out",
                str(target),
            ],
            check=True,
        )
        print(f"{games:>6} games: {time.perf_counter() - started:.0f}s", flush=True)


def _write(out: Path, results: list[dict]) -> None:
    """Merge these points into whatever the file already holds, atomically.

    Called after every point rather than at the end. The first run of this was
    killed after three of four and wrote nothing; those points survived only
    because run telemetry had recorded them independently, which is luck rather
    than design.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(out.read_text())["points"] if out.exists() else []
    by_size = {r["training_games"]: r for r in existing}
    by_size.update({r["training_games"]: r for r in results})
    tmp = out.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            {"points": sorted(by_size.values(), key=lambda r: r["training_games"])}, indent=1
        )
    )
    tmp.replace(out)


def evaluate(sizes: list, args) -> None:
    """Play each trained set against the hand-written tables, fixed length."""
    results = []
    for games in sizes:
        path = weights_path(games)
        if not path.exists():
            print(f"{games}: no weights, skipping")
            continue

        with TelemetryRecorder(
            "learning_curve_eval",
            {"training_games": games, "match_games": args.games, "movetime": MOVETIME},
        ) as recorder:
            jobs = [(str(path), i, games, MOVETIME, args.max_plies) for i in range(args.games)]
            total = 0.0
            played = 0
            with ProcessPoolExecutor(max_workers=args.workers) as pool:
                pending = {
                    pool.submit(play_one, jobs.pop(0)) for _ in range(min(args.workers, len(jobs)))
                }
                while pending:
                    done = next(as_completed(pending))
                    pending.discard(done)
                    score, nodes = done.result()
                    total += score
                    played += 1
                    recorder.add_games()
                    recorder.add_nodes(nodes)
                    if jobs:
                        pending.add(pool.submit(play_one, jobs.pop(0)))

            score = total / played
            se = (score * (1 - score) / played) ** 0.5
            row = {
                "training_games": games,
                "match_games": played,
                "score_vs_tables": score,
                "elo_vs_tables": elo_diff_from_score(score),
                "interval": [
                    elo_diff_from_score(max(score - 1.96 * se, 1e-6)),
                    elo_diff_from_score(min(score + 1.96 * se, 1 - 1e-6)),
                ],
                "training_seconds": json.loads(path.read_text()).get("seconds"),
            }
            results.append(row)
            recorder.snapshot(row)
            _write(Path(args.out), results)
            print(
                f"{games:>6} training games -> {score:>6.1%}, "
                f"{row['elo_vs_tables']:+.0f} Elo "
                f"[{row['interval'][0]:+.0f}, {row['interval'][1]:+.0f}] "
                f"({row['training_seconds']:.0f}s to train)",
                flush=True,
            )

    _write(Path(args.out), results)
    print(f"\nwritten to {args.out}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", default=None, help="comma-separated training sizes")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--sizes", default="1000,3000,10000,30000")
    parser.add_argument("--games", type=int, default=240, help="match games per point")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--max-plies", type=int, default=160)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--retrain", action="store_true")
    parser.add_argument("--out", default="data/learning_curve.json")
    args = parser.parse_args()

    # Training sizes are integers; evaluation labels need not be. A repaired
    # or hand-modified weight set is a point on the same axis and should be
    # measurable by the same path, so the label is kept as written.
    raw = [x.strip() for x in (args.train or args.sizes).split(",")]
    sizes = [int(x) if x.isdigit() else x for x in raw]
    if args.train:
        train([s for s in sizes if isinstance(s, int)], args)
    if args.evaluate:
        evaluate(sizes, args)
    if not args.train and not args.evaluate:
        parser.error("nothing to do: pass --train, --evaluate, or both")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
