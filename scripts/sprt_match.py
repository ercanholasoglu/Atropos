"""Run a match until the games answer, and survive being interrupted.

Two things this does that a fixed-length match does not.

**It stops when it knows.** A sequential test spends games until the evidence
is decisive rather than until a counter runs out, so a clearly good change is
confirmed in a couple of hundred games and a clearly bad one is rejected just
as fast.

**It can be resumed.** These runs take an hour or more and anything that long
gets interrupted eventually. State is written after *every game*, so a run
that dies picks up where it stopped instead of starting over — and a budget in
minutes lets it be driven in survivable chunks.

    python -m scripts.sprt_match --a v3-shelter --b v2 --minutes 15
    python -m scripts.sprt_match --a v3-shelter --b v2 --minutes 15   # resumes
    python -m scripts.sprt_match --a L6 --b L5 --elo1 100
    python -m scripts.sprt_match --a ../atropos/build/atropos --b L5
    python -m scripts.sprt_match --a L7-see --b L7 --pgn data/games/see.pgn
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path

import chess

from elo.calculator import elo_diff_from_score
from elo.sprt import Sprt, SprtConfig, Verdict
from engine.base_engine import BaseEngine
from engine.levels import available_levels, create_engine
from scripts.eval_ab import VARIANTS, VariantEngine
from tournament.match import play_game
from tournament.openings import OPENING_BOOK, load_book
from scripts.telemetry import TelemetryRecorder
from tournament.uci_engine import UciEngineProcess, UciLimits


def build(name: str, seed: int, movetime: float) -> BaseEngine:
    """Turn a name into an engine.

    Three kinds, so the same gate covers every comparison this project makes:
    ``L6`` is a rung of the ladder, ``v3-shelter`` an evaluation variant, and
    anything else is taken as a path to an external UCI engine.
    """
    if name in VARIANTS:
        return VariantEngine(name, seed=seed, time_limit=movetime)

    # `L8-uniform` is Level 8 with its adaptive clock switched off, so a
    # feature can be tested against its own absence rather than against a
    # different engine.
    base, _, flag = name.partition("-")
    if base.upper().startswith("L") and base[1:].isdigit():
        level = int(base[1:])
        if level not in available_levels():
            raise SystemExit(f"level {level} is not implemented; have {available_levels()}")
        engine = create_engine(level, seed=seed, time_limit=movetime)
        if flag.startswith("nodes") or flag.startswith("soft"):
            # Fixed node budgets, for the speed experiment's third arm. A
            # `soft` budget only declines to start the next iteration; a
            # `nodes` budget stops on the node that exceeds it. Both drop the
            # clock entirely, so the two are compared with no timing in play.
            digits = flag[5:] if flag.startswith("nodes") else flag[4:]
            if not digits.isdigit():
                raise SystemExit(f"{flag!r} needs a node count, e.g. L7-soft400")
            engine.time_limit = None
            engine.node_limit = int(digits)
            engine.node_limit_hard = flag.startswith("nodes")
            engine.name = f"L{level}-{flag}"
        elif flag == "v1":
            # The instrument as it stood before the v2 cut: rook-on-open-file
            # term in the evaluation, SEE pruning off. Rebuilt rather than
            # checked out, so both instruments can play each other in one
            # process and the cut can be measured directly instead of inferred
            # from two separate anchorings.
            from engine.evaluation import tapered
            from engine.evaluation.positional import positional_score_rooks

            searcher = getattr(engine, "searcher", None)
            if searcher is not None and hasattr(searcher.config, "use_see_pruning"):
                searcher.config.use_see_pruning = False
            # setattr rather than assignment: static_eval is defined on the
            # searching levels, not on BaseEngine, so a plain assignment is a
            # type error even though every engine reaching this branch has it.
            setattr(
                engine,
                "static_eval",
                lambda board: tapered.tapered_pst(board) + positional_score_rooks(board),
            )
            engine.name = f"L{level}-v1"
        elif flag == "see":
            searcher = getattr(engine, "searcher", None)
            if searcher is None or not hasattr(searcher.config, "use_see_pruning"):
                raise SystemExit(f"L{level} has no quiescence to prune")
            searcher.config.use_see_pruning = True
            engine.name = f"L{level}-see"
        elif flag == "uniform":
            if not hasattr(engine, "adaptive_time"):
                raise SystemExit(f"L{level} has no adaptive clock to switch off")
            engine.adaptive_time = False
            engine.name = f"L{level}-uniform"
        elif flag:
            raise SystemExit(
                f"unknown engine flag {flag!r}; defined flags are "
                f"'v1', 'see', 'uniform', 'nodes<N>' and 'soft<N>'"
            )
        return engine

    path = Path(name)
    if path.exists():
        engine = UciEngineProcess([str(path)], name=path.name, limits=UciLimits(movetime=movetime))
        return engine.start()

    raise SystemExit(
        f"cannot make an engine from {name!r}: "
        f"expected a variant {sorted(VARIANTS)}, a level like L6, or a path to a UCI engine"
    )


def play_one(job: tuple[str, str, int, float, int, str, str | None]) -> tuple[float, int, str]:
    """One game as ``(score for a, nodes searched)``. Runs in its own process.

    Module-level and taking only plain data because process pools have to
    pickle what they are handed. Nodes come back with the score so a run can
    report what its answer cost, which is not reconstructable afterwards.
    """
    a_spec, b_spec, index, movetime, max_plies, book_name, components = job

    book = load_book(book_name)
    opening = book[(index // 2) % len(book)]
    a_is_white = index % 2 == 0
    first = build(a_spec, seed=1000 + index, movetime=movetime)
    second = build(b_spec, seed=2000 + index, movetime=movetime)
    white, black = (first, second) if a_is_white else (second, first)

    try:
        record = play_game(
            white,
            black,
            start_fen=opening.fen,
            max_plies=max_plies,
            opening=opening.name,
            on_move=component_logger(
                Path(components) if components else None,
                index,
                {"a": a_spec, "b": b_spec, "movetime": movetime, "book": book_name},
            ),
        )
    finally:
        for engine in (first, second):
            if isinstance(engine, UciEngineProcess):
                engine.close()

    white_score = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}[record.result]
    return (white_score if a_is_white else 1 - white_score), record.nodes, record.pgn


def component_logger(path: Path | None, game_index: int, meta: dict):
    """A move hook that writes the evaluation term by term, or nothing.

    One JSON object per move, appended. It records what the engine thought and
    what it spent thinking: the evaluation split into its parts, the depth and
    nodes the search reached, and the principal variation. None of it can be
    reconstructed after the game — the search is gone the moment the move is
    played — which is why it is written during rather than derived after.
    """
    if path is None:
        return None

    from engine.evaluation.breakdown import breakdown

    def hook(game, engine, result) -> None:
        # The hook fires *after* the move is pushed, so game.board is the
        # position that follows it. Everything else in this record -- the
        # depth, the nodes, the score, the principal variation -- describes the
        # position the engine was *thinking about*, so that is the one whose
        # evaluation gets broken down. Logging the post-move position here
        # would pair a search with the wrong board.
        after = game.board
        board = after.copy(stack=False)
        if board.move_stack or after.move_stack:
            board = after.copy()
            try:
                board.pop()
            except IndexError:  # pragma: no cover - first move of a fresh game
                board = after.copy(stack=False)
        record = {
            "game": game_index,
            "ply": board.ply(),
            "fen": board.fen(),
            "fen_after": after.fen(),
            "engine": engine.name,
            "move": result.move.uci() if result.move else None,
            "depth": result.depth,
            "nodes": result.nodes,
            "time_ms": round(result.time_ms, 2),
            "score": round(result.score, 1),
            "pv": [m.uci() for m in result.pv[:8]],
            "eval": breakdown(board).as_dict(),
            **meta,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    return hook


def save_pgn(path: Path | None, pgn: str) -> None:
    """Append one finished game, if the run was asked to keep them.

    Fifteen thousand games were played in this project before anything wrote
    one down, which makes "why did that change help?" unanswerable after the
    fact. Appending is deliberate: a run that is interrupted keeps the games it
    already played, the same way its tally does.
    """
    if path is None or not pgn:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(pgn.rstrip() + "\n\n")


def load(path: Path, config: SprtConfig) -> Sprt:
    if not path.exists():
        return Sprt(config)
    stored = json.loads(path.read_text())
    test = Sprt(config)
    test.wins = stored["wins"]
    test.draws = stored["draws"]
    test.losses = stored["losses"]
    return test


def save(path: Path, test: Sprt, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                **meta,
                "wins": test.wins,
                "draws": test.draws,
                "losses": test.losses,
                "games": test.games,
                "score": test.score,
                "llr": test.llr,
                "elo_estimate": elo_diff_from_score(test.score) if test.games else 0.0,
                "verdict": test.verdict.value,
                "config": asdict(test.config),
            },
            indent=1,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sequential match between two evaluations")
    parser.add_argument("--a", required=True, help="variant, level (L6) or engine path under test")
    parser.add_argument("--b", required=True, help="what it has to beat")
    parser.add_argument("--elo0", type=float, default=0.0)
    parser.add_argument("--elo1", type=float, default=40.0)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--beta", type=float, default=0.05)
    parser.add_argument("--max-games", type=int, default=1200)
    parser.add_argument(
        "--book",
        default="default",
        choices=("default", "midgame"),
        help="which openings to start from; see tournament.openings.load_book",
    )
    parser.add_argument(
        "--log-components",
        default=None,
        help="append one JSON line per move: the evaluation split into its "
        "terms, plus depth, nodes, time and PV. Cannot be produced "
        "retroactively -- the search is gone once the move is played.",
    )
    parser.add_argument(
        "--pgn",
        default=None,
        help="append every finished game here (data/games/NAME.pgn by convention), "
        "so a result can be looked at afterwards rather than only counted",
    )
    parser.add_argument("--movetime", type=float, default=0.1)
    parser.add_argument("--max-plies", type=int, default=160)
    parser.add_argument("--minutes", type=float, default=15.0, help="budget for this chunk")
    parser.add_argument(
        "--fixed",
        action="store_true",
        help="play every game; do not stop early. For measuring a size rather "
        "than deciding a question — a sequential test stops as soon as it can "
        "reject, which biases the estimate away from zero and leaves an "
        "interval too wide to read a magnitude off.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="games in parallel; 4-6 is free on a 10-core machine, 8+ starts to contend",
    )
    parser.add_argument("--state", default=None)
    args = parser.parse_args()

    config = SprtConfig(
        elo0=args.elo0,
        elo1=args.elo1,
        alpha=args.alpha,
        beta=args.beta,
        max_games=args.max_games,
    )
    safe = lambda name: Path(name).name.replace(" ", "_")
    state_path = Path(args.state or f"data/sprt_{safe(args.a)}_vs_{safe(args.b)}.json")
    test = load(state_path, config)
    meta = {
        "a": args.a,
        "b": args.b,
        "movetime": args.movetime,
        "max_plies": args.max_plies,
        "book": args.book,
    }

    if test.games:
        print(f"resuming: {test.summary()}", flush=True)
    if test.finished and not args.fixed:
        print(f"already decided: {test.verdict.value}")
        return 0

    recorder = TelemetryRecorder(
        "sprt_match",
        {
            "a": args.a,
            "b": args.b,
            "elo0": args.elo0,
            "elo1": args.elo1,
            "alpha": args.alpha,
            "beta": args.beta,
            "workers": args.workers,
            "movetime": args.movetime,
            "max_plies": args.max_plies,
            "max_games": args.max_games,
            "minutes_budget": args.minutes,
            "games_before": test.games,
        },
    )

    # These are time-controlled games: two of them running at once share the
    # machine and both results are wrong. One at a time, on purpose.
    deadline = time.monotonic() + args.minutes * 60
    started_at = test.games
    pgn_path = Path(args.pgn) if args.pgn else None

    def done() -> bool:
        """Whether to stop playing. In fixed mode only the counter stops it."""
        if args.fixed:
            return test.games >= args.max_games
        return test.finished

    workers = max(1, args.workers)
    if workers == 1:
        while not done() and time.monotonic() < deadline:
            # Seeds move with the game index, so a resumed run does not replay
            # the games it already has.
            score, nodes, pgn = play_one(
                (
                    args.a,
                    args.b,
                    test.games,
                    args.movetime,
                    args.max_plies,
                    args.book,
                    args.log_components,
                )
            )
            save_pgn(pgn_path, pgn)
            test.record(score)
            recorder.add_nodes(nodes)
            recorder.add_games()
            save(state_path, test, meta)
            if test.games % 10 == 0 or done():
                print(f"  {test.summary()}", flush=True)
    else:
        # Batched, because a pool cannot be asked to stop mid-flight. The cost
        # is that the test can overshoot its stopping point by up to
        # `workers - 1` games, which slightly inflates the error rates it
        # promises. Measured contention on this machine: 4 workers cost 5% of
        # per-game speed, 6 cost 8%, 8 cost 22% — and a uniform slowdown does
        # not bias a game, since both engines in it are slowed the same.
        with ProcessPoolExecutor(max_workers=workers) as pool:
            while not done() and time.monotonic() < deadline:
                jobs = [
                    (
                        args.a,
                        args.b,
                        test.games + offset,
                        args.movetime,
                        args.max_plies,
                        args.book,
                        args.log_components,
                    )
                    for offset in range(workers)
                ]
                for score, nodes, pgn in pool.map(play_one, jobs):
                    save_pgn(pgn_path, pgn)
                    test.record(score)
                    recorder.add_nodes(nodes)
                    recorder.add_games()
                save(state_path, test, meta)
                print(f"  {test.summary()}", flush=True)

    low, high = test.elo_interval()
    recorder.write(
        {
            "games_total": test.games,
            "wins": test.wins,
            "draws": test.draws,
            "losses": test.losses,
            "score": test.score,
            "elo_estimate": elo_diff_from_score(test.score),
            "elo_interval_95": [low, high],
            "llr": test.llr,
            "verdict": test.verdict.value,
            "diagnosis": test.diagnosis(),
            "state_file": str(state_path),
        }
    )

    print()
    print(f"{args.a} vs {args.b}: {test.summary()}")
    print(f"estimate: {elo_diff_from_score(test.score):+.0f} Elo")
    print(f"this chunk played {test.games - started_at} games; state in {state_path}")
    print(f"telemetry: {recorder.summary()}")
    print(f"           {recorder.path}")
    if not test.finished:
        print("not decided yet — run again to continue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
