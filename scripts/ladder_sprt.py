"""Re-test the ladder's central claim with a sequential test.

The README says each level beats the one below it. That was established with
sixteen-game matches — the same fixed-length method that, tested against
itself, said an evaluation change was worth +60 Elo at 64 games and −2 at 359.

The claim deserves the better instrument. Each adjacent pairing is run as an
SPRT with a bracket wide enough for the effect being claimed: rungs of a ladder
should be *clearly* apart, so H1 is 100 Elo rather than the 40 used for a
tuning change. Big effects resolve in a few dozen games, which makes the whole
ladder affordable; a pairing that does not resolve quickly is itself the
finding.

    python -m scripts.ladder_sprt --minutes 10
    python -m scripts.ladder_sprt --pairs 7:6,8:7 --minutes 10

**One pairing at a time.** These are time-controlled games; two running at once
share the machine and both answers are wrong.

**The time control is part of the question.** A fast control buys more samples
per hour and compresses the very thing some pairings are about. Level 7 beats
Level 6 by searching deeper in the same clock — at 0.1s per move there is
barely room for an extra iteration, so a test there measures L7 with its main
advantage taken away. That is a legitimate question ("is it better in blitz?")
but it is not the same question as "is the ladder ordered", and the answer
should say which one was asked.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from elo.calculator import elo_diff_from_score
from elo.sprt import Sprt, SprtConfig, Verdict
from engine.levels import available_levels
from scripts.sprt_match import build, save
from scripts.telemetry import TelemetryRecorder
from tournament.match import play_game
from tournament.openings import OPENING_BOOK


def adjacent_pairs() -> list[tuple[int, int]]:
    levels = available_levels()
    return [(high, low) for low, high in zip(levels, levels[1:])]


def parse_pairs(spec: str) -> list[tuple[int, int]]:
    if spec == "adjacent":
        return adjacent_pairs()
    pairs = []
    for part in spec.split(","):
        high, low = part.strip().split(":")
        pairs.append((int(high), int(low)))
    return pairs


def state_path(high: int, low: int) -> Path:
    return Path(f"data/sprt_L{high}_vs_L{low}.json")


def load_state(high: int, low: int, config: SprtConfig) -> Sprt | None:
    path = state_path(high, low)
    if not path.exists():
        return None
    stored = json.loads(path.read_text())
    test = Sprt(config)
    test.wins, test.draws, test.losses = stored["wins"], stored["draws"], stored["losses"]
    return test


def play_pairing(high: int, low: int, test: Sprt, args, deadline: float, recorder=None) -> int:
    """Play games for one pairing until it decides or the clock runs out."""
    played = 0
    while not test.finished and time.time() < deadline:
        index = test.games
        opening = OPENING_BOOK[(index // 2) % len(OPENING_BOOK)]
        high_is_white = index % 2 == 0

        stronger = build(f"L{high}", seed=1000 + index, movetime=args.movetime)
        weaker = build(f"L{low}", seed=2000 + index, movetime=args.movetime)
        white, black = (stronger, weaker) if high_is_white else (weaker, stronger)

        record = play_game(
            white, black, start_fen=opening.fen, max_plies=args.max_plies, opening=opening.name
        )
        white_score = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}[record.result]
        test.record(white_score if high_is_white else 1 - white_score)
        save(
            state_path(high, low),
            test,
            {"a": f"L{high}", "b": f"L{low}", "movetime": args.movetime},
        )
        played += 1
    return played


def run_pairings(args, config: SprtConfig) -> int:
    """Work through the undecided pairings, one at a time.

    Sequentially on purpose: these are time-controlled games, and two running
    at once share the machine so both answers come out wrong.

    Cheapest first — the lower rungs are hundreds of Elo apart and decide in a
    couple of dozen games, so a short budget still returns real verdicts
    instead of six half-finished tests.
    """
    deadline = time.time() + args.minutes_total * 60
    pairs = parse_pairs(args.pairs)
    recorder = TelemetryRecorder(
        "ladder_sprt",
        {
            "pairs": args.pairs,
            "elo0": args.elo0,
            "elo1": args.elo1,
            "movetime": args.movetime,
            "max_plies": args.max_plies,
            "max_games": args.max_games,
            "minutes_budget": args.minutes_total,
        },
    )
    verdicts: dict[str, dict] = {}

    for high, low in sorted(pairs, key=lambda pair: pair[0]):
        test = load_state(high, low, config) or Sprt(config)
        if test.finished:
            print(f"L{high} vs L{low}: already {test.verdict.value}", flush=True)
            continue
        if time.time() >= deadline:
            print(f"L{high} vs L{low}: out of budget, not started", flush=True)
            continue

        played = play_pairing(high, low, test, args, deadline, recorder)
        interval = test.elo_interval()
        verdicts[f"L{high} vs L{low}"] = {
            "games": test.games,
            "score": test.score,
            "elo_estimate": elo_diff_from_score(test.score),
            "elo_interval_95": list(interval),
            "llr": test.llr,
            "verdict": test.verdict.value,
            "games_this_run": played,
        }
        print(f"L{high} vs L{low}: {test.summary()}  (+{played} games this run)", flush=True)

    recorder.write({"pairings": verdicts})
    print()
    print(f"telemetry: {recorder.summary()}")
    print(f"           {recorder.path}")
    print()
    return report(args, config)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sequentially test the ladder")
    parser.add_argument("--pairs", default="adjacent")
    parser.add_argument("--elo0", type=float, default=0.0)
    parser.add_argument("--elo1", type=float, default=100.0)
    parser.add_argument("--movetime", type=float, default=0.1)
    parser.add_argument("--max-plies", type=int, default=160)
    parser.add_argument("--max-games", type=int, default=600)
    parser.add_argument("--minutes", type=float, default=10.0, help="budget per pairing")
    parser.add_argument("--report-only", action="store_true", help="just read the state files")
    parser.add_argument(
        "--minutes-total",
        type=float,
        default=None,
        help="run undecided pairings, cheapest first, within this budget",
    )
    args = parser.parse_args()

    config = SprtConfig(elo0=args.elo0, elo1=args.elo1, max_games=args.max_games)
    if args.minutes_total is not None:
        return run_pairings(args, config)
    return report(args, config)


def report(args, config: SprtConfig) -> int:
    pairs = parse_pairs(args.pairs)

    print(f"{'pairing':<12} {'games':>6} {'score':>7} {'Elo':>7} {'interval':>16} {'verdict':>14}")
    print("-" * 68)

    undecided = []
    for high, low in pairs:
        test = load_state(high, low, config)
        if test is None:
            print(f"{'L' + str(high) + ' vs L' + str(low):<12} {'-':>6} {'not run':>7}")
            undecided.append((high, low))
            continue
        low_elo, high_elo = test.elo_interval()
        print(
            f"{'L' + str(high) + ' vs L' + str(low):<12} {test.games:>6} {test.score:>6.1%} "
            f"{elo_diff_from_score(test.score):>+7.0f} "
            f"{f'[{low_elo:+.0f}, {high_elo:+.0f}]':>16} {test.verdict.value:>14}"
        )
        if test.verdict is Verdict.CONTINUE:
            undecided.append((high, low))

    print("-" * 68)
    if undecided:
        print("still open: " + ", ".join(f"L{h} vs L{l}" for h, l in undecided))
        print(
            "run each with: python -m scripts.sprt_match --a L<high> --b L<low> "
            f"--elo0 {args.elo0:.0f} --elo1 {args.elo1:.0f} --movetime {args.movetime}"
        )
    else:
        print("every pairing has a verdict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
