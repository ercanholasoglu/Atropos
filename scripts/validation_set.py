"""A held-out set of games the learner has never seen and could not have.

The learning curve peaks at 3,000 self-play games and falls after
(`docs/LEARNING_CURVE_PREREG.md`). Telling overfitting from the alternatives
needs a validation set, and a validation set drawn from the learner's own games
would not be one — it would be more of the distribution the learner made.

Source: the Lichess January 2013 database dump, human games with results. It
predates this project by more than a decade and has no path into training.

    python -m scripts.validation_set --games 200
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import TextIO, cast

import chess
import chess.pgn

DUMP = Path("data/validation/lichess_2013_01.pgn.zst")
OUT = Path("data/validation/heldout.json")
OUTCOME = {"1-0": 1.0, "0-1": -1.0, "1/2-1/2": 0.0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--min-elo", type=int, default=1800)
    parser.add_argument("--min-plies", type=int, default=30)
    parser.add_argument("--max-plies", type=int, default=120)
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()

    # Streamed rather than decompressed to disk: the dump is 17MB compressed
    # and several hundred uncompressed, and only the first few thousand games
    # are needed.
    proc = subprocess.Popen(["zstd", "-dc", str(DUMP)], stdout=subprocess.PIPE, text=True)
    stream = cast(TextIO, proc.stdout)

    kept: list[dict] = []
    scanned = 0
    while len(kept) < args.games:
        game = chess.pgn.read_game(stream)
        if game is None:
            break
        scanned += 1
        headers = game.headers
        if headers.get("Result") not in OUTCOME:
            continue
        try:
            elo = min(int(headers["WhiteElo"]), int(headers["BlackElo"]))
        except (KeyError, ValueError):
            continue
        if elo < args.min_elo:
            continue
        moves = [m.uci() for m in game.mainline_moves()]
        if not args.min_plies <= len(moves) <= args.max_plies:
            continue
        kept.append(
            {
                "site": headers.get("Site", ""),
                "elo": elo,
                "outcome": OUTCOME[headers["Result"]],
                "moves": moves,
            }
        )
    proc.terminate()

    plies = sum(len(g["moves"]) for g in kept)
    results = {o: sum(1 for g in kept if g["outcome"] == o) for o in (1.0, 0.0, -1.0)}
    print(f"scanned {scanned:,} games, kept {len(kept)}")
    print(f"  {plies:,} plies, {plies / max(len(kept), 1):.0f} per game")
    print(f"  white {results[1.0]}, draw {results[0.0]}, black {results[-1.0]}")
    print(f"  lowest rating in a kept game: {min(g['elo'] for g in kept)}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"source": str(DUMP), "games": kept}, indent=1))
    print(f"written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
