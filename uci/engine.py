"""The UCI engine loop.

UCI is a conversation with a GUI that never waits for the engine to be ready.
Three constraints follow, and between them they dictate the design:

* **``stop`` and ``isready`` must be answered while a search is running.**
  So the search runs on a worker thread and the reader thread stays free.
* **Exactly one ``bestmove`` per ``go``.** Not zero if the search was cut off,
  not two if the stop raced the finish. A single flag guards it.
* **A crash is a lost game.** An exception inside the search thread must
  still produce a legal move, because a GUI that gets nothing back just waits
  until the flag falls.

Everything is written against injected streams rather than ``sys.stdout``
directly, so the whole protocol is testable without a subprocess.
"""

from __future__ import annotations

import sys
import threading
from typing import TextIO

import chess

from engine.base_engine import BaseEngine
from engine.levels import create_engine
from engine.perft import perft_divide, run_suite
from engine.search.context import RootResult, SearchStats
from engine.utils.constants import MATE_THRESHOLD
from uci.options import EngineOptions, describe_options, parse_setoption, set_option
from uci.protocol import (
    Command,
    format_score,
    parse_command,
    parse_go,
    parse_position,
)
from uci.time_manager import TimeBudget, allocate

ENGINE_NAME = "chess-bot"
ENGINE_VERSION = "0.1.0"
ENGINE_AUTHOR = "ercanholasoglu"

# Used when a GUI says `go` with no limits at all, which is legal and means
# "think for a sensible while".
DEFAULT_MOVE_SECONDS = 2.0


class UciEngine:
    """A UCI-speaking front end over the level ladder."""

    def __init__(self, output: TextIO | None = None, log: TextIO | None = None) -> None:
        self.output = output or sys.stdout
        self.log = log or sys.stderr
        self.options = EngineOptions()
        self.board = chess.Board()
        self.engine: BaseEngine | None = None
        self._engine_level: int | None = None

        self._write_lock = threading.Lock()
        self._search_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._bestmove_sent = threading.Event()
        self._pondering = False

    # --- output -----------------------------------------------------------

    def send(self, line: str, output: TextIO | None = None) -> None:
        """Write one protocol line. Held under a lock: the search thread and
        the reader thread both write here."""
        stream = output or self.output
        with self._write_lock:
            stream.write(line + "\n")
            stream.flush()

    def note(self, message: str, log: TextIO | None = None) -> None:
        (log or self.log).write(f"info string {message}\n")

    # --- lifecycle --------------------------------------------------------

    def run(self, source: TextIO | None = None, output: TextIO | None = None) -> None:
        """Read lines until ``quit`` or end of input."""
        source = source or sys.stdin
        for line in source:
            if not self.handle_line(line, output):
                break
        self.request_stop(join=True)

    def handle_line(
        self, line: str, output: TextIO | None = None, log: TextIO | None = None
    ) -> bool:
        """Handle one line. Returns False when the engine should exit."""
        command = parse_command(line)
        if command is None:
            return True

        handler = getattr(self, f"_cmd_{command.name.lower().replace('.', '_')}", None)
        if handler is None:
            self.note(f"unknown command: {command.text}", log)
            return True
        return handler(command, output or self.output, log or self.log) is not False

    # --- handshake --------------------------------------------------------

    def _cmd_uci(self, command: Command, output: TextIO, log: TextIO) -> None:
        self.send(f"id name {ENGINE_NAME} {ENGINE_VERSION}", output)
        self.send(f"id author {ENGINE_AUTHOR}", output)
        for description in describe_options(EngineOptions()):
            self.send(description.to_uci(), output)
        self.send("uciok", output)

    def _cmd_isready(self, command: Command, output: TextIO, log: TextIO) -> None:
        # Deliberately does not wait for the search: a GUI uses `isready` to
        # check the engine is alive, including while it is thinking.
        self.send("readyok", output)

    def _cmd_setoption(self, command: Command, output: TextIO, log: TextIO) -> None:
        parsed = parse_setoption(command.args)
        if parsed is None:
            self.note(f"malformed setoption: {command.text}", log)
            return
        name, value = parsed
        if not set_option(self.options, name, value):
            self.note(f"unsupported option: {name}", log)
            return
        if name.strip().lower() in ("level", "hash"):
            # Both invalidate what the current engine has learned.
            self.engine = None
            self._engine_level = None

    def _cmd_ucinewgame(self, command: Command, output: TextIO, log: TextIO) -> None:
        self.request_stop(join=True)
        self.board = chess.Board()
        if self.engine is not None:
            self.engine.new_game()

    def _cmd_quit(self, command: Command, output: TextIO, log: TextIO) -> bool:
        self.request_stop(join=True)
        return False

    # --- position ---------------------------------------------------------

    def _cmd_position(self, command: Command, output: TextIO, log: TextIO) -> None:
        parsed = parse_position(command.args)
        if parsed is None:
            self.note(f"malformed position: {command.text}", log)
            return
        self.board = parsed.board()

    # --- searching --------------------------------------------------------

    def current_engine(self) -> BaseEngine:
        """The engine for the selected level, kept across moves.

        Rebuilt only when the level changes: its transposition table and
        killers are worth more than the cost of keeping them.
        """
        if self.engine is None or self._engine_level != self.options.level:
            self.engine = create_engine(self.options.level, seed=None)
            self._engine_level = self.options.level
        return self.engine

    def _cmd_go(self, command: Command, output: TextIO, log: TextIO) -> None:
        self.request_stop(join=True)
        params = parse_go(command.args)
        budget = allocate(
            params,
            self.board.turn,
            self.options.move_overhead_ms,
            default_seconds=DEFAULT_MOVE_SECONDS,
        )
        self._pondering = params.ponder

        if self.board.is_game_over():
            self.send("bestmove 0000", output)
            return

        self._stop_event = threading.Event()
        self._bestmove_sent.clear()
        self._search_thread = threading.Thread(
            target=self._search, args=(self.board.copy(), budget, output), daemon=True
        )
        self._search_thread.start()

    def _cmd_stop(self, command: Command, output: TextIO, log: TextIO) -> None:
        self.request_stop(join=True)

    def _cmd_ponderhit(self, command: Command, output: TextIO, log: TextIO) -> None:
        # The pondered move was played, so the search becomes a real one. With
        # no separate clock to switch to, the honest thing is to finish now.
        self._pondering = False
        self.request_stop(join=True)

    def request_stop(self, join: bool = False) -> None:
        self._stop_event.set()
        thread = self._search_thread
        if join and thread is not None and thread.is_alive():
            thread.join(timeout=10.0)
        self._search_thread = None

    def _search(self, board: chess.Board, budget: TimeBudget, output: TextIO) -> None:
        """Run one search on the worker thread and answer with a move."""
        engine = self.current_engine()
        engine.stop_event = self._stop_event
        engine.node_limit = budget.nodes
        engine.time_limit = None if budget.infinite else budget.seconds

        # A depth limit belongs to this search, not to the engine. Setting it
        # and walking away left every later search capped at whatever the last
        # `go depth N` happened to ask for.
        original_depth: int | None = getattr(engine, "depth", None)
        if budget.depth is not None and original_depth is not None:
            setattr(engine, "depth", budget.depth)
        engine.on_iteration = lambda result, stats, position: self._send_info(
            result, stats, position, output
        )

        move: chess.Move | None = None
        try:
            result = engine.analyse(board)
            move = result.move
            # A closing info line with the real totals. It also covers the
            # fixed-depth levels, which complete in one pass and so never fire
            # the per-iteration callback at all.
            self._send_info(
                RootResult(result.move, result.score, result.depth, list(result.pv)),
                SearchStats(nodes=result.nodes),
                board,
                output,
                elapsed_ms=result.time_ms,
            )
        except Exception as error:  # noqa: BLE001 - a crash here loses the game
            self.note(f"search failed: {error!r}")
        finally:
            engine.on_iteration = None
            engine.stop_event = None
            engine.node_limit = None
            if original_depth is not None:
                setattr(engine, "depth", original_depth)
            if move is None:
                legal = list(board.legal_moves)
                move = legal[0] if legal else None
            self._send_bestmove(move, output)

    def _send_bestmove(self, move: chess.Move | None, output: TextIO) -> None:
        """Exactly one per ``go`` — not zero on a stop, not two on a race."""
        if self._bestmove_sent.is_set():
            return
        self._bestmove_sent.set()
        self.send(f"bestmove {move.uci() if move else '0000'}", output)

    def _send_info(
        self,
        result: RootResult,
        stats: SearchStats,
        board: chess.Board,
        output: TextIO,
        elapsed_ms: float | None = None,
    ) -> None:
        if result.move is None:
            return
        elapsed = elapsed_ms if elapsed_ms is not None else stats.elapsed_ms
        # Scores are White-relative inside the engine; UCI wants them from the
        # side to move.
        score = result.score if board.turn == chess.WHITE else -result.score
        nps = int(stats.nodes / (elapsed / 1000)) if elapsed > 0 else 0
        parts = [
            f"info depth {max(result.depth, 1)}",
            f"score {format_score(score, MATE_THRESHOLD)}",
            f"nodes {stats.nodes}",
            f"nps {nps}",
            f"time {int(elapsed)}",
        ]
        if result.pv:
            parts.append("pv " + " ".join(move.uci() for move in result.pv))
        self.send(" ".join(parts), output)

    # --- extras beyond the protocol ---------------------------------------

    def _cmd_perft(self, command: Command, output: TextIO, log: TextIO) -> None:
        depth = _first_int(command.args, default=3)
        divided = perft_divide(self.board, depth)
        for uci, nodes in sorted(divided.items()):
            self.send(f"{uci}: {nodes}", output)
        self.send(f"nodes {sum(divided.values())}", output)

    def _cmd_bench(self, command: Command, output: TextIO, log: TextIO) -> None:
        depth = _first_int(command.args, default=3)
        suite = run_suite(depth=depth)
        self.send(
            f"bench depth {depth} positions {len(suite.results)} "
            f"nodes {suite.nodes} elapsedms {int(suite.seconds * 1000)} "
            f"nps {int(suite.nps)} ok {'yes' if suite.passed else 'no'}",
            output,
        )

    def _cmd_eval(self, command: Command, output: TextIO, log: TextIO) -> None:
        engine = self.current_engine()
        score = engine.evaluate(self.board)
        self.send(f"eval cp {int(score)} level {self.options.level}", output)

    def _cmd_d(self, command: Command, output: TextIO, log: TextIO) -> None:
        for line in str(self.board).splitlines():
            self.send(line, output)
        self.send(f"fen {self.board.fen()}", output)


def _first_int(args: tuple[str, ...] | list[str], default: int) -> int:
    for token in args:
        try:
            return int(token)
        except ValueError:
            continue
    return default


def main() -> int:
    UciEngine().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
