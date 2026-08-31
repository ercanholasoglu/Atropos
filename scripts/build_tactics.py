"""Mine verified tactical positions instead of transcribing remembered ones.

The first version of this suite was written from memory and shipped **two
illegal positions and three wrong solutions**. Nothing about that is unusual —
a FEN is easy to mistype and a "well-known" tactic is easy to misremember —
which is why this generates positions rather than recalling them.

The method, and why each part is there:

1. **Play games** between ladder levels at a low budget, so the positions are
   ones an engine like this actually reaches rather than composed studies.
2. **Ask an outside engine**, not ours. Verifying with the engine under test
   would build a suite it passes by construction. Stockfish is the oracle.
3. **Keep only decisive positions.** Two lines are searched: unless the best
   move is far better than the second best, the position does not have "one
   right answer" and would score the suite on taste.
4. **Require the answer to be a win, not merely better.** A position where the
   best move loses slightly less than the alternatives tests nothing useful.
5. **Check legality directly**, because that is the failure that got through
   last time.

    python -m scripts.build_tactics --want 12 --out data/tactics_candidates.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import chess
import chess.engine

STOCKFISH = "/opt/homebrew/bin/stockfish"

# A tactic is a position where one move wins and the rest do not. These are the
# thresholds for "wins" and for "the rest do not", in centipawns, fixed here
# rather than tuned until the suite looked the right size.
MIN_ADVANTAGE = 300
MIN_MARGIN = 250
VERIFY_DEPTH = 16


def legal_and_playable(board: chess.Board) -> bool:
    """Rejects what got through last time: illegal positions and finished ones."""
    return (
        board.is_valid()
        and not board.is_game_over()
        and board.king(chess.WHITE) is not None
        and board.king(chess.BLACK) is not None
    )


def score_cp(info, board: chess.Board) -> int:
    """Score for the side to move, mates counted as a large finite number."""
    return info["score"].pov(board.turn).score(mate_score=10_000)


def candidates(engine: chess.engine.SimpleEngine, board: chess.Board) -> dict | None:
    """Whether this position has one decisively best move, and what it is."""
    if not legal_and_playable(board):
        return None
    if board.legal_moves.count() < 2:
        return None  # a forced move is not a test of anything

    lines = engine.analyse(board, chess.engine.Limit(depth=VERIFY_DEPTH), multipv=2)
    if len(lines) < 2:
        return None

    best, second = score_cp(lines[0], board), score_cp(lines[1], board)
    if best < MIN_ADVANTAGE or best - second < MIN_MARGIN:
        return None

    move = lines[0]["pv"][0]
    if move not in board.legal_moves:  # pragma: no cover - defensive
        return None
    return {
        "fen": board.fen(),
        "best_san": board.san(move),
        "best_uci": move.uci(),
        "score": best,
        "margin": best - second,
        "mate_in": lines[0]["score"].pov(board.turn).mate(),
    }


def walk(rng: random.Random, engine: chess.engine.SimpleEngine, want: int) -> list[dict]:
    """Play scrappy games and keep the positions that turn out to be tactics."""
    from engine.levels import create_engine

    found: list[dict] = []
    seen: set[str] = set()
    game = 0
    while len(found) < want and game < 400:
        game += 1
        board = chess.Board()
        white = create_engine(4, seed=game, time_limit=0.02)
        black = create_engine(3, seed=game * 7, time_limit=0.02)
        for ply in range(70):
            if board.is_game_over():
                break
            # Sampling every position would return dozens of near-duplicates
            # from the same game; this takes a scattered few.
            if ply > 8 and rng.random() < 0.30:
                key = " ".join(board.fen().split()[:2])
                if key not in seen:
                    seen.add(key)
                    hit = candidates(engine, board)
                    if hit:
                        found.append(hit)
                        print(
                            f"  found {len(found):>2}/{want}: {hit['best_san']:<8} "
                            f"score {hit['score']:+6d} margin {hit['margin']:+6d}"
                            f"{' mate in ' + str(hit['mate_in']) if hit['mate_in'] else ''}",
                            flush=True,
                        )
                        if len(found) >= want:
                            break
            mover = white if board.turn == chess.WHITE else black
            move = mover.get_best_move(board)
            if move is None or move not in board.legal_moves:
                break
            board.push(move)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--want", type=int, default=12)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--out", default="data/tactics_candidates.json")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH) as engine:
        found = walk(rng, engine, args.want)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(
            {
                "verify_depth": VERIFY_DEPTH,
                "min_advantage": MIN_ADVANTAGE,
                "min_margin": MIN_MARGIN,
                "positions": found,
            },
            indent=1,
        )
    )
    print(f"\n{len(found)} positions written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
