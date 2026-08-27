"""Driving an external UCI engine as if it were one of ours.

This is what makes a rating mean anything. A ladder measured only against
itself is self-consistent and could still be uniformly terrible; the only way
to find out is to play something that was not written here. Wrapping an
external process in :class:`BaseEngine` means every piece of machinery already
built — matches, gauntlets, the Elo tracker, the openings — works on it
unchanged.

No cutechess-cli. It is the usual answer and it is an external dependency that
has to be installed, configured and parsed; speaking UCI over a pipe is a few
hundred lines and removes the dependency entirely.

The hard part is not the protocol, it is misbehaviour. An opponent may hang,
die mid-game, or answer with a move that is not legal. Each of those has to
end the game rather than the tournament, which is why every read has a
deadline and every answer is checked.
"""

from __future__ import annotations

import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field

import chess

from engine.base_engine import BaseEngine, SearchResult


class UciEngineError(RuntimeError):
    """The external engine did something the protocol does not allow."""


@dataclass
class UciLimits:
    """How the external engine is told to think.

    Fixed time per move by default. It is the setting that makes two engines
    comparable — a fixed depth compares nothing, since one engine's depth 6 is
    another's depth 3.
    """

    movetime: float | None = 0.2
    depth: int | None = None
    nodes: int | None = None

    def to_go(self) -> str:
        parts = ["go"]
        if self.depth is not None:
            parts += ["depth", str(self.depth)]
        if self.nodes is not None:
            parts += ["nodes", str(self.nodes)]
        if self.movetime is not None:
            parts += ["movetime", str(int(self.movetime * 1000))]
        return " ".join(parts) if len(parts) > 1 else "go movetime 200"


@dataclass
class UciInfo:
    """The last thing the engine said about its search."""

    depth: int = 0
    score_cp: float = 0.0
    nodes: int = 0
    time_ms: float = 0.0
    pv: list[chess.Move] = field(default_factory=list)


class UciEngineProcess(BaseEngine):
    """An external UCI engine, wearing this project's engine interface."""

    def __init__(
        self,
        command: list[str],
        name: str | None = None,
        level: int = 0,
        initial_elo: int = 1500,
        limits: UciLimits | None = None,
        options: dict[str, str] | None = None,
        startup_timeout: float = 10.0,
        move_timeout: float = 60.0,
        cwd: str | None = None,
    ) -> None:
        super().__init__(
            name=name or command[0].rsplit("/", 1)[-1], level=level, initial_elo=initial_elo
        )
        self.command = command
        self.limits = limits or UciLimits()
        self.options = options or {}
        self.startup_timeout = startup_timeout
        self.move_timeout = move_timeout
        self.cwd = cwd

        self._process: subprocess.Popen | None = None
        self._lines: queue.Queue[str] = queue.Queue()
        self._reader: threading.Thread | None = None
        self.last_info = UciInfo()
        self.reported_name = ""

    # --- process ----------------------------------------------------------

    def start(self) -> "UciEngineProcess":
        if self._process is not None:
            return self
        self._process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            cwd=self.cwd,
        )
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

        self._send("uci")
        for line in self._read_until("uciok", self.startup_timeout):
            if line.startswith("id name "):
                self.reported_name = line[len("id name ") :].strip()
        for option, value in self.options.items():
            self._send(f"setoption name {option} value {value}")
        self._sync()
        return self

    def _pump(self) -> None:
        """Read the engine's output on its own thread.

        A blocking read on a pipe whose far end has died never returns, so the
        reads that matter happen against a queue with a deadline instead.
        """
        assert self._process is not None and self._process.stdout is not None
        for line in self._process.stdout:
            self._lines.put(line.strip())
        self._lines.put("")  # end of stream

    def _send(self, line: str) -> None:
        if self._process is None or self._process.stdin is None:
            raise UciEngineError(f"{self.name} is not running")
        if self._process.poll() is not None:
            raise UciEngineError(f"{self.name} exited with code {self._process.returncode}")
        self._process.stdin.write(line + "\n")
        self._process.stdin.flush()

    def _read_until(self, prefix: str, timeout: float) -> list[str]:
        """Collect lines until one starts with ``prefix``, or give up."""
        deadline = time.monotonic() + timeout
        collected: list[str] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise UciEngineError(f"{self.name} did not answer '{prefix}' within {timeout:.0f}s")
            try:
                line = self._lines.get(timeout=min(remaining, 0.5))
            except queue.Empty:
                if self._process is not None and self._process.poll() is not None:
                    raise UciEngineError(f"{self.name} exited while waiting for '{prefix}'")
                continue
            if line.startswith(prefix):
                collected.append(line)
                return collected
            collected.append(line)

    def _sync(self) -> None:
        self._send("isready")
        self._read_until("readyok", self.startup_timeout)

    def close(self) -> None:
        if self._process is None:
            return
        try:
            self._send("quit")
            self._process.wait(timeout=3.0)
        except Exception:  # noqa: BLE001 - a stuck opponent still has to die
            self._process.kill()
            self._process.wait(timeout=3.0)
        finally:
            self._process = None

    def __enter__(self) -> "UciEngineProcess":
        return self.start()

    def __exit__(self, *exc_info) -> None:
        self.close()

    # --- the engine interface --------------------------------------------

    def new_game(self) -> None:
        super().new_game()
        if self._process is not None:
            self._send("ucinewgame")
            self._sync()

    def evaluate(self, board: chess.Board) -> float:
        """UCI has no way to ask for a static evaluation.

        Returning the last search score would be a different quantity wearing
        the same name, so this reports nothing rather than something wrong.
        """
        return 0.0

    def get_best_move(self, board: chess.Board) -> chess.Move:
        return self.analyse(board).move  # type: ignore[return-value]

    def analyse(self, board: chess.Board) -> SearchResult:
        if self._process is None:
            self.start()

        started = time.perf_counter()
        self._send(f"position fen {board.fen()}")
        self._send(self.limits.to_go())
        lines = self._read_until("bestmove", self.move_timeout)

        info = UciInfo()
        for line in lines:
            if line.startswith("info "):
                self._absorb_info(line, board, info)
        self.last_info = info

        move = self._parse_bestmove(lines[-1], board)
        elapsed = (time.perf_counter() - started) * 1000
        self.nodes = info.nodes

        result = SearchResult(
            move=move,
            # Engines report from the side to move; this project is
            # White-relative everywhere.
            score=info.score_cp if board.turn == chess.WHITE else -info.score_cp,
            depth=info.depth,
            nodes=info.nodes,
            time_ms=info.time_ms or elapsed,
            pv=info.pv,
        )
        self.last_result = result
        return result

    def _parse_bestmove(self, line: str, board: chess.Board) -> chess.Move:
        tokens = line.split()
        if len(tokens) < 2:
            raise UciEngineError(f"{self.name} sent a malformed bestmove: {line!r}")
        try:
            move = chess.Move.from_uci(tokens[1])
        except ValueError as error:
            raise UciEngineError(f"{self.name} sent {tokens[1]!r}, which is not a move") from error
        if move not in board.legal_moves:
            raise UciEngineError(
                f"{self.name} played {tokens[1]}, which is illegal in {board.fen()}"
            )
        return move

    @staticmethod
    def _absorb_info(line: str, board: chess.Board, info: UciInfo) -> None:
        tokens = line.split()
        index = 1
        while index < len(tokens):
            token = tokens[index]
            if token == "depth" and index + 1 < len(tokens):
                info.depth = _to_int(tokens[index + 1], info.depth)
                index += 2
            elif token == "nodes" and index + 1 < len(tokens):
                info.nodes = _to_int(tokens[index + 1], info.nodes)
                index += 2
            elif token == "time" and index + 1 < len(tokens):
                info.time_ms = float(_to_int(tokens[index + 1], int(info.time_ms)))
                index += 2
            elif token == "score" and index + 2 < len(tokens):
                kind, value = tokens[index + 1], _to_int(tokens[index + 2], 0)
                if kind == "cp":
                    info.score_cp = float(value)
                elif kind == "mate":
                    from engine.utils.constants import MATE_SCORE

                    info.score_cp = float(MATE_SCORE - abs(value) * 2) * (1 if value > 0 else -1)
                index += 3
            elif token == "pv":
                replay = board.copy(stack=False)
                info.pv = []
                for text in tokens[index + 1 :]:
                    try:
                        move = chess.Move.from_uci(text)
                    except ValueError:
                        break
                    if move not in replay.legal_moves:
                        break
                    info.pv.append(move)
                    replay.push(move)
                break
            else:
                index += 1


def _to_int(text: str, fallback: int) -> int:
    try:
        return int(text)
    except ValueError:
        return fallback
