"""What a measurement cost to take.

Every result in this project is a number plus the compute that bought it, and
only one of those two has been recorded. The gap shows: the ten-thousand-game
TDLeaf run produced a clean answer and left no record of the hours it took, so
"Elo per CPU-hour" cannot be reconstructed for it. That number cannot be
recovered afterwards — the run has to write it while it happens.

So each run drops one JSON next to its result: how long it took in wall clock,
how much CPU it burned across every worker, how many positions it searched, how
much memory it peaked at, and — the part that makes the rest re-runnable — the
commit it ran on.

Two honesty notes about the numbers:

* **CPU seconds cover the workers.** ``RUSAGE_CHILDREN`` accumulates a child's
  time once the child is reaped, and a process pool reaps at shutdown, so the
  figure is complete only after the pool closes. Verified on this machine: four
  workers report 3.8x wall clock.
* **Peak memory is the largest single process, not the sum.**
  ``ru_maxrss`` for children is a maximum, not a total, and the field is named
  for what it actually is.
"""

from __future__ import annotations

import json
import os
import platform
import resource
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

TELEMETRY_DIR = Path("data/telemetry")


def git_commit() -> str | None:
    """The commit the run is measuring, or None outside a repository.

    None rather than a placeholder: a run whose commit is unknown should say
    so, and never be mistaken for one that was recorded.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def git_dirty() -> bool | None:
    """Whether the tree had uncommitted changes when the run started."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return bool(result.stdout.strip()) if result.returncode == 0 else None


def _rusage() -> tuple[float, int]:
    """``(cpu seconds including reaped children, peak RSS in bytes)``."""
    me = resource.getrusage(resource.RUSAGE_SELF)
    kids = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = me.ru_utime + me.ru_stime + kids.ru_utime + kids.ru_stime
    # ru_maxrss is bytes on macOS and kilobytes everywhere else.
    scale = 1 if sys.platform == "darwin" else 1024
    return cpu, max(me.ru_maxrss, kids.ru_maxrss) * scale


@dataclass
class RunTelemetry:
    """One experiment run: what it did, what it cost, what it concluded."""

    tool: str
    started_at: str
    finished_at: str = ""
    commit: str | None = None
    tree_dirty: bool | None = None
    parameters: dict = field(default_factory=dict)
    wall_seconds: float = 0.0
    cpu_seconds: float = 0.0
    cpu_per_wall: float = 0.0
    peak_rss_mb_largest_process: float = 0.0
    nodes: int = 0
    nodes_per_cpu_second: float = 0.0
    games: int = 0
    machine: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


class TelemetryRecorder:
    """Measures one run and writes it out, whatever happens to the run.

    Used as a context manager so a run that crashes or is killed still leaves
    a record — an interrupted experiment costs the same CPU as one that
    finished, and the cost curve should know about it.
    """

    def __init__(self, tool: str, parameters: dict, directory: Path | None = None) -> None:
        self.directory = directory or TELEMETRY_DIR
        self.telemetry = RunTelemetry(
            tool=tool,
            started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            commit=git_commit(),
            tree_dirty=git_dirty(),
            parameters=parameters,
            machine={
                "platform": platform.platform(),
                "processor": platform.processor() or platform.machine(),
                "cpu_count": os.cpu_count(),
                "python": platform.python_version(),
                "host": socket.gethostname(),
            },
        )
        self._cpu0, self._rss0 = _rusage()
        self._wall0 = time.perf_counter()
        self.path = self.directory / self._filename()

    def _filename(self) -> str:
        stamp = self.telemetry.started_at.replace(":", "").replace("-", "").replace("+0000", "Z")
        return f"{stamp}-{self.telemetry.tool}.json"

    # --- during the run ---------------------------------------------------

    def add_nodes(self, nodes: int) -> None:
        self.telemetry.nodes += nodes

    def add_games(self, games: int = 1) -> None:
        self.telemetry.games += games

    def note(self, message: str) -> None:
        self.telemetry.notes.append(message)

    # --- finishing --------------------------------------------------------

    def snapshot(self, result: dict | None = None) -> RunTelemetry:
        cpu, rss = _rusage()
        telemetry = self.telemetry
        telemetry.wall_seconds = time.perf_counter() - self._wall0
        telemetry.cpu_seconds = cpu - self._cpu0
        telemetry.cpu_per_wall = (
            telemetry.cpu_seconds / telemetry.wall_seconds if telemetry.wall_seconds else 0.0
        )
        telemetry.peak_rss_mb_largest_process = max(rss, self._rss0) / 1_048_576
        telemetry.nodes_per_cpu_second = (
            telemetry.nodes / telemetry.cpu_seconds if telemetry.cpu_seconds > 0 else 0.0
        )
        telemetry.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if result is not None:
            telemetry.result = result
        return telemetry

    def write(self, result: dict | None = None) -> Path:
        self.snapshot(result)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(self.telemetry), indent=1))
        return self.path

    def summary(self) -> str:
        t = self.telemetry
        return (
            f"{t.wall_seconds:.0f}s wall, {t.cpu_seconds:.0f}s cpu "
            f"({t.cpu_per_wall:.1f}x), {t.games} games, {t.nodes:,} nodes, "
            f"{t.peak_rss_mb_largest_process:.0f} MB peak, commit "
            f"{t.commit or 'unknown'}{' (dirty)' if t.tree_dirty else ''}"
        )

    def __enter__(self) -> "TelemetryRecorder":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None:
            self.note(f"run ended with {exc_type.__name__}: {exc}")
        self.write()
        print(f"telemetry: {self.summary()}", flush=True)
        print(f"           {self.path}", flush=True)
