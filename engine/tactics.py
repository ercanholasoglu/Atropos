"""A tactical suite: positions with one right answer.

Matches measure strength the way it is finally judged, and they are expensive
and noisy — hundreds of games to see a difference worth fifty Elo. A tactical
suite measures something narrower for almost nothing: given a position with a
forced win in it, does the search find the move?

That makes it the right regression guard. A change to move ordering or pruning
that quietly stops finding a tactic shows up here in seconds, long before a
gauntlet would notice it, and unlike a match a failure points at a position
that can be looked at.

Every entry is checked rather than trusted: a test asserts that a deep search
agrees with the recorded answer, so a mistyped FEN or a wrong solution fails
loudly instead of quietly making the suite easier.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import chess


@dataclass(frozen=True)
class TacticalPosition:
    """A position and its answer, stated whichever way round is honest.

    Some puzzles have one winning move. Others have one *losing* move and a
    dozen adequate replies — enumerating the dozen would be a long list that
    is easy to get wrong, so those are recorded as what to avoid instead.
    """

    name: str
    fen: str
    best_moves: tuple[str, ...] = ()  # SAN; several when several moves win
    avoid_moves: tuple[str, ...] = ()  # SAN; the trap
    note: str = ""

    def board(self) -> chess.Board:
        return chess.Board(self.fen)

    def solved_by(self, board: chess.Board, move: chess.Move | None) -> bool:
        if move is None:
            return False
        san = board.san(move)
        if self.avoid_moves:
            return san not in self.avoid_moves
        return san in self.best_moves


# Deliberately small and mostly forcing. A suite of quiet positional puzzles
# would measure taste; these have a proof at the end of them.
TACTICAL_SUITE: tuple[TacticalPosition, ...] = (
    TacticalPosition(
        "back-rank mate",
        "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1",
        ("Ra8#",),
        note="the king has no luft",
    ),
    TacticalPosition(
        "queen mate in one",
        "6k1/5ppp/8/8/8/8/5PPP/4Q1K1 w - - 0 1",
        ("Qe8#",),
    ),
    TacticalPosition(
        "corner mate",
        "7k/8/6K1/8/8/8/8/1Q6 w - - 0 1",
        ("Qb8#",),
        note="the king takes every flight square; the queen only has to check",
    ),
    TacticalPosition(
        "queen sacrifice, mate in two",
        "r1b2k1r/ppp1bppp/8/1B1Q4/5q2/2P5/PPP2PPP/R3R1K1 w - - 1 0",
        ("Qd8+",),
        note="1. Qd8+ Bxd8 2. Re8#",
    ),
    TacticalPosition(
        "take the free queen",
        "4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1",
        ("exd5",),
        note="the pawn is the cheapest attacker",
    ),
    TacticalPosition(
        "win the rook, not the pawn",
        "4k3/3p1r2/8/4N3/8/8/8/4K3 w - - 0 1",
        ("Nxf7",),
        note="a bigger victim is worth more than a nearer one",
    ),
    TacticalPosition(
        "decline the poisoned pawn",
        "4k3/8/2p5/3p4/8/8/Q7/4K3 w - - 0 1",
        avoid_moves=("Qxd5",),
        note="the pawn is free for one move; cxd5 collects the queen",
    ),
    TacticalPosition(
        "promote and mate",
        "5k2/7P/5K2/8/8/8/8/8 w - - 0 1",
        ("h8=Q#", "h8=R#"),
        note="a rook mates too — the extra squares a queen covers are already covered",
    ),
)


@dataclass
class TacticalResult:
    position: TacticalPosition
    played: str
    solved: bool
    depth: int
    nodes: int
    seconds: float


@dataclass
class TacticalReport:
    results: list[TacticalResult] = field(default_factory=list)

    @property
    def solved(self) -> int:
        return sum(1 for result in self.results if result.solved)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def rate(self) -> float:
        return self.solved / self.total if self.total else 0.0

    @property
    def seconds(self) -> float:
        return sum(result.seconds for result in self.results)

    def table(self) -> str:
        header = f"{'position':<28} {'played':>10} {'depth':>6} {'nodes':>9}  ok"
        lines = [header, "-" * len(header)]
        for result in self.results:
            lines.append(
                f"{result.position.name:<28} {result.played:>10} {result.depth:>6} "
                f"{result.nodes:>9,}  {'yes' if result.solved else 'NO'}"
            )
        lines.append("-" * len(header))
        lines.append(f"{self.solved}/{self.total} solved in {self.seconds:.1f}s")
        return "\n".join(lines)


def run_suite(engine, positions=TACTICAL_SUITE, on_result=None) -> TacticalReport:
    """Give each position to the engine and record what it played."""
    report = TacticalReport()
    for position in positions:
        board = position.board()
        engine.new_game()
        started = time.perf_counter()
        result = engine.analyse(board)
        played = board.san(result.move) if result.move else "-"
        outcome = TacticalResult(
            position=position,
            played=played,
            solved=position.solved_by(board, result.move),
            depth=result.depth,
            nodes=result.nodes,
            seconds=time.perf_counter() - started,
        )
        report.results.append(outcome)
        if on_result is not None:
            on_result(outcome)
    return report
