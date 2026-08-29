"""Shared search plumbing: node counting, time control, draw detection.

Everything in :mod:`engine.search` works in **negamax** convention — scores
are relative to the side to move, and get converted to White's perspective
only when a level hands the result back out.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

import chess

MAX_PLY = 64


class SearchTimeout(Exception):
    """Raised to unwind the search when the budget is spent or a stop arrives.

    One exception for both cases on purpose: the search does not care *why* it
    has to stop, and every unwind path already restores the board correctly.
    """


@dataclass
class SearchStats:
    """Node counter, time budget, and the stop signal for one search."""

    time_limit: float | None = None  # seconds; None = search to completion
    node_limit: int | None = None
    # Set from another thread to end the search — this is how UCI `stop`
    # reaches a search that is already running.
    stop_event: threading.Event | None = None
    nodes: int = 0
    start: float = field(default_factory=time.perf_counter)
    # Reading the clock at every node is measurable overhead; every 2048 is
    # far more often than a millisecond-scale budget needs.
    check_interval: int = 2048
    # Whether the node budget may stop a search part-way through an iteration.
    # A hard limit stops on the node that exceeds it and throws away whatever
    # that iteration had found so far; a soft one lets the iteration finish
    # and only declines to start the next. Exists so the two can be told
    # apart — see docs/SPEED.md, where a node budget and a clock produced
    # different strength at the same node count.
    node_limit_hard: bool = True

    def tick(self) -> None:
        """Count a node and abort the search if it should not continue."""
        self.nodes += 1
        if self.node_limit_hard and self.node_limit is not None and self.nodes >= self.node_limit:
            raise SearchTimeout
        if self.nodes % self.check_interval:
            return
        if self.stop_event is not None and self.stop_event.is_set():
            raise SearchTimeout
        if self.time_limit is not None and time.perf_counter() - self.start >= self.time_limit:
            raise SearchTimeout

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self.start

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed * 1000

    def out_of_time(self) -> bool:
        """Whether another iteration should be started at all."""
        if self.stop_event is not None and self.stop_event.is_set():
            return True
        if self.node_limit is not None and self.nodes >= self.node_limit:
            return True
        return self.time_limit is not None and self.elapsed >= self.time_limit


@dataclass
class RootResult:
    """A finished root search. ``score`` is side-to-move relative."""

    move: chess.Move | None
    score: float
    depth: int
    pv: list[chess.Move] = field(default_factory=list)


def is_draw(board: chess.Board) -> bool:
    """Draws a search must recognise inside the tree.

    Repetition is only worth testing once enough reversible moves have been
    played, which keeps the stack walk off the hot path.
    """
    if board.is_insufficient_material():
        return True
    if board.halfmove_clock >= 100:
        return True
    # Twofold inside the tree: a repetition the search can force is already a
    # draw for practical purposes, and it stops both sides from shuffling.
    return board.halfmove_clock >= 4 and board.is_repetition(2)


def unwind_to(board: chess.Board, stack_depth: int) -> None:
    """Take back every move pushed since ``stack_depth``.

    A :class:`SearchTimeout` unwinds the recursion without running any of the
    ``board.pop()`` calls the frames below it owed, so the root has to put the
    board back the way it found it.
    """
    while len(board.move_stack) > stack_depth:
        board.pop()


def new_pv_table() -> list[list[chess.Move]]:
    return [[] for _ in range(MAX_PLY + 1)]
