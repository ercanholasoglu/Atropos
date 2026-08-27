"""Turning a clock into a thinking budget.

The engine is told how much time is left on the whole clock and has to decide
how much of it this one move deserves. Three rules do nearly all the work:

* **Never spend what you do not have.** Every allocation loses the move
  overhead first, and is capped well below the remaining time. Losing on time
  in a won position is the most avoidable loss in chess.
* **Spread the clock over the moves still to come.** With ``movestogo`` that
  number is given; without it, a game is assumed to have roughly thirty moves
  left, which is wrong in both directions and wrong slowly.
* **The increment is nearly free.** It arrives after the move, so most of it
  can be spent — but not all, or a long game drifts downward one move at a
  time.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from uci.protocol import GoParams

# Assumed moves remaining when the GUI does not say. Deliberately shorter than
# a real game: overspending early is recoverable, running out is not.
ASSUMED_MOVES_REMAINING = 30

# How much of the increment to spend, and the ceiling on any single move as a
# fraction of what is left.
INCREMENT_SHARE = 0.75
MAX_CLOCK_SHARE = 0.4

# Nothing below this is worth the round trip; nothing above it is a good idea
# without being asked.
MINIMUM_BUDGET = 0.01


@dataclass
class TimeBudget:
    """What the search is allowed to use."""

    seconds: float | None = None  # None means "until told to stop"
    depth: int | None = None
    nodes: int | None = None
    infinite: bool = False

    def describe(self) -> str:
        if self.infinite:
            return "infinite"
        parts = []
        if self.seconds is not None:
            parts.append(f"{self.seconds:.2f}s")
        if self.depth is not None:
            parts.append(f"depth {self.depth}")
        if self.nodes is not None:
            parts.append(f"{self.nodes} nodes")
        return ", ".join(parts) or "unbounded"


def allocate(
    params: GoParams,
    turn: chess.Color,
    move_overhead_ms: int = 30,
    default_seconds: float | None = None,
) -> TimeBudget:
    """Decide the budget for one move."""
    overhead = move_overhead_ms / 1000.0

    if params.infinite or params.ponder:
        # Pondering ends on `ponderhit` or `stop`, never on a clock.
        return TimeBudget(depth=params.depth, nodes=params.nodes, infinite=True)

    if params.movetime is not None:
        return TimeBudget(
            seconds=max(MINIMUM_BUDGET, params.movetime - overhead),
            depth=params.depth,
            nodes=params.nodes,
        )

    if params.depth is not None or params.nodes is not None:
        if not params.has_clock:
            # An explicit depth or node limit with no clock is a fixed search.
            return TimeBudget(depth=params.depth, nodes=params.nodes)

    if not params.has_clock:
        return TimeBudget(seconds=default_seconds, depth=params.depth, nodes=params.nodes)

    remaining = (params.wtime if turn == chess.WHITE else params.btime) or 0.0
    increment = params.winc if turn == chess.WHITE else params.binc
    usable = max(0.0, remaining - overhead)

    moves_left = (
        params.movestogo if params.movestogo and params.movestogo > 0 else ASSUMED_MOVES_REMAINING
    )
    budget = usable / moves_left + increment * INCREMENT_SHARE

    # However the arithmetic came out, one move never gets most of the clock.
    budget = min(budget, usable * MAX_CLOCK_SHARE)
    return TimeBudget(
        seconds=max(MINIMUM_BUDGET, budget),
        depth=params.depth,
        nodes=params.nodes,
    )
