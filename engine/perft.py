"""Perft: counting leaf nodes, and why an engine needs it before anything else.

Perft walks the move tree to a fixed depth and counts the leaves. The counts
for standard positions are published to the node, so a mismatch is a proof of
a bug in move generation — not a hint, a proof. Everything above it (search,
evaluation, ratings) is built on the assumption that the legal moves are the
legal moves, and perft is the only thing that checks it.

This engine generates moves through python-chess, which is well tested, so
perft here is verifying the *wiring* rather than the generator: the board
wrapper, make/unmake, and the special cases — castling rights, en passant,
promotion — that every homegrown board gets wrong at least once.

It doubles as the standard throughput benchmark. Nodes per second here is the
cleanest speed number an engine has, because no evaluation or search
heuristic is involved.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import chess


@dataclass(frozen=True)
class PerftPosition:
    """A position with published node counts, one per depth."""

    name: str
    fen: str
    counts: tuple[int, ...]  # index 0 is depth 1

    @property
    def max_depth(self) -> int:
        return len(self.counts)


# The standard set. Positions 2-6 are the ones that catch the bugs position 1
# never will: castling through check, en passant pins, promotion in check.
PERFT_POSITIONS: tuple[PerftPosition, ...] = (
    PerftPosition(
        "startpos",
        chess.STARTING_FEN,
        (20, 400, 8_902, 197_281, 4_865_609),
    ),
    PerftPosition(
        "kiwipete",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        (48, 2_039, 97_862, 4_085_603),
    ),
    PerftPosition(
        "endgame",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
        (14, 191, 2_812, 43_238, 674_624),
    ),
    PerftPosition(
        "promotion",
        "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
        (6, 264, 9_467, 422_333),
    ),
    PerftPosition(
        "position-5",
        "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
        (44, 1_486, 62_379, 2_103_487),
    ),
    PerftPosition(
        "position-6",
        "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10",
        (46, 2_079, 89_890, 3_894_594),
    ),
)


def perft(board: chess.Board, depth: int) -> int:
    """Leaf nodes at ``depth``.

    The depth-1 shortcut matters: counting the moves is the answer, and
    pushing each one only to pop it immediately would double the work at the
    widest level of the tree.
    """
    if depth <= 0:
        return 1
    if depth == 1:
        return board.legal_moves.count()

    nodes = 0
    for move in board.legal_moves:
        board.push(move)
        nodes += perft(board, depth - 1)
        board.pop()
    return nodes


def perft_divide(board: chess.Board, depth: int) -> dict[str, int]:
    """Nodes per root move — how a perft mismatch is actually tracked down.

    A wrong total says something is broken; a divide says *which move* leads
    to the broken subtree, and repeating it descends straight to the bug.
    """
    if depth <= 0:
        return {}
    divided: dict[str, int] = {}
    for move in board.legal_moves:
        board.push(move)
        divided[move.uci()] = perft(board, depth - 1)
        board.pop()
    return divided


@dataclass
class PerftResult:
    name: str
    depth: int
    nodes: int
    expected: int | None
    seconds: float

    @property
    def matches(self) -> bool:
        return self.expected is None or self.nodes == self.expected

    @property
    def nps(self) -> float:
        return self.nodes / self.seconds if self.seconds > 0 else 0.0


def run_perft(position: PerftPosition, depth: int) -> PerftResult:
    board = chess.Board(position.fen)
    expected = position.counts[depth - 1] if depth <= position.max_depth else None
    started = time.perf_counter()
    nodes = perft(board, depth)
    return PerftResult(
        name=position.name,
        depth=depth,
        nodes=nodes,
        expected=expected,
        seconds=time.perf_counter() - started,
    )


@dataclass
class PerftSuite:
    results: list[PerftResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(result.matches for result in self.results)

    @property
    def nodes(self) -> int:
        return sum(result.nodes for result in self.results)

    @property
    def seconds(self) -> float:
        return sum(result.seconds for result in self.results)

    @property
    def nps(self) -> float:
        return self.nodes / self.seconds if self.seconds > 0 else 0.0

    def table(self) -> str:
        header = f"{'position':<14} {'depth':>6} {'nodes':>12} {'expected':>12} {'nps':>10}  ok"
        lines = [header, "-" * len(header)]
        for result in self.results:
            expected = f"{result.expected:,}" if result.expected is not None else "-"
            mark = "yes" if result.matches else "NO"
            lines.append(
                f"{result.name:<14} {result.depth:>6} {result.nodes:>12,} "
                f"{expected:>12} {result.nps:>10,.0f}  {mark}"
            )
        lines.append("-" * len(header))
        lines.append(f"{self.nodes:,} nodes in {self.seconds:.2f}s — {self.nps:,.0f} nps")
        return "\n".join(lines)


def run_suite(
    depth: int = 3,
    positions: tuple[PerftPosition, ...] = PERFT_POSITIONS,
    on_result=None,
) -> PerftSuite:
    """Run every position to ``depth``, clamped to what each one publishes."""
    suite = PerftSuite()
    for position in positions:
        result = run_perft(position, min(depth, position.max_depth))
        suite.results.append(result)
        if on_result is not None:
            on_result(result)
    return suite
