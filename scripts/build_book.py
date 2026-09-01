"""Build a second opening book, so an effect can be tested off the first one.

Every match in this project started from the same eight mainline openings at
ply 5-6. The null control (`docs/NULL_CONTROL_PREREG.md`) showed the harness
has no colour or scoring tilt, and named the thing it could not see: a bias
affecting both arms equally. **An unrepresentative book is exactly that** —
both sides play it, so it cancels in a null control and does not cancel in a
generalisation claim.

This builds a middlegame book to test against. The requirements, fixed before
generating:

* **Reached by play, not composed.** Positions the ladder actually produces
  from the existing book, so they are the right shape for this engine.
* **Balanced.** Stockfish must score them inside +/-60 centipawns, or one side
  starts the game already winning and the pairing measures nothing.
* **Distinct.** No two positions from the same game, and no duplicates.
* **Alive.** Not over, both kings present, enough material that the game has
  somewhere to go.

    python -m scripts.build_book --want 8
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import chess
import chess.engine

STOCKFISH = "/opt/homebrew/bin/stockfish"
BALANCE_CP = 60
VERIFY_DEPTH = 14
TARGET_PLY = 30


def usable(board: chess.Board) -> bool:
    if board.is_game_over() or not board.is_valid():
        return False
    # Enough material left that the position is a middlegame rather than a
    # technical ending, where a capture-pruning change has little to prune.
    pieces = sum(
        len(board.pieces(pt, c))
        for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
        for c in (chess.WHITE, chess.BLACK)
    )
    return pieces >= 8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--want", type=int, default=8)
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--out", default="data/midgame_book.json")
    args = parser.parse_args()

    from engine.levels import create_engine
    from tournament.openings import OPENING_BOOK

    rng = random.Random(args.seed)
    found: list[dict] = []
    seen: set[str] = set()

    with chess.engine.SimpleEngine.popen_uci(STOCKFISH) as sf:
        attempt = 0
        while len(found) < args.want and attempt < 200:
            attempt += 1
            opening = OPENING_BOOK[attempt % len(OPENING_BOOK)]
            board = chess.Board(opening.fen)
            white = create_engine(rng.choice([5, 6, 7]), seed=attempt, time_limit=0.02)
            black = create_engine(rng.choice([5, 6, 7]), seed=attempt * 7, time_limit=0.02)
            target = TARGET_PLY + rng.randint(-6, 10)
            for _ in range(target):
                if board.is_game_over():
                    break
                move = (white if board.turn == chess.WHITE else black).get_best_move(board)
                if move is None or move not in board.legal_moves:
                    break
                board.push(move)

            if not usable(board):
                continue
            key = " ".join(board.fen().split()[:2])
            if key in seen:
                continue

            info = sf.analyse(board, chess.engine.Limit(depth=VERIFY_DEPTH))
            score = info["score"].white().score(mate_score=10_000)
            if score is None or abs(score) > BALANCE_CP:
                continue

            seen.add(key)
            found.append(
                {
                    "name": f"mid-{opening.name.lower().replace(chr(32), '-')}-{len(found) + 1}",
                    "fen": board.fen(),
                    "from_opening": opening.name,
                    "ply": board.ply(),
                    "stockfish_cp": score,
                }
            )
            print(
                f"  {len(found):>2}/{args.want}  ply {board.ply():>3}  "
                f"eval {score:+4d}cp  from {opening.name}",
                flush=True,
            )

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(
            {"balance_cp": BALANCE_CP, "verify_depth": VERIFY_DEPTH, "positions": found}, indent=1
        )
    )
    print(f"\n{len(found)} positions written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
