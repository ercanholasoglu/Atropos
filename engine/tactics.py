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
    TacticalPosition(
        "mined 1",
        "1Q6/3bpkbr/5p2/7p/p3Pp1P/1PN2P2/P2P1PR1/1R1K1BN1 w - - 0 23",
        ("Bc4+",),
        note="mate in 12, white to move; Stockfish depth 16 prefers it by 8778 centipawns",
    ),
    TacticalPosition(
        "mined 2",
        "5r2/4p1k1/4b3/4Pp1p/PQ3p1P/P1N2P2/3P1P2/1R1K1BN1 w - - 2 28",
        ("Qxe7+",),
        note="mate in 8, white to move; Stockfish depth 16 prefers it by 8820 centipawns",
    ),
    TacticalPosition(
        "mined 3",
        "rnb2bn1/3pk1Pr/pp1p3p/6NQ/2Pp4/1P6/P4PPP/R1B1KB1R w KQ - 2 16",
        ("Qf7+",),
        note="mate in 3, white to move; Stockfish depth 16 prefers it by 8938 centipawns",
    ),
    TacticalPosition(
        "mined 4",
        "rnbk1bn1/3p2Pr/pp1p3p/6N1/2Pp4/1P6/P3QPPP/R1B1KB1R w KQ - 4 17",
        ("gxf8=Q+",),
        note="mate in 8, white to move; Stockfish depth 16 prefers it by 8989 centipawns",
    ),
    TacticalPosition(
        "mined 5",
        "rn1qkb1r/p5np/b1pP1ppQ/8/8/4P3/PPPP2PP/RNB1K1NR b KQkq - 0 11",
        ("Nh5",),
        note="wins material (+5.6), black to move; Stockfish depth 16 prefers it by 266 centipawns",
    ),
    TacticalPosition(
        "mined 6",
        "2Q3nr/p1p5/1p1kP3/5p1p/6pq/P2P4/PBP2PPP/1R1K1BNR w - - 5 14",
        ("Qd7+",),
        note="mate in 2, white to move; Stockfish depth 16 prefers it by 8919 centipawns",
    ),
    TacticalPosition(
        "mined 7",
        "rn2kbnr/pb1pp2p/1pp2p2/q7/2P3P1/1Q1P1N1P/PP1BPP2/RN2KB1R w KQkq - 1 11",
        ("Bxa5",),
        note="wins material (+7.6), white to move; Stockfish depth 16 prefers it by 316 centipawns",
    ),
    TacticalPosition(
        "mined 8",
        "r7/7N/b2B2kp/Rppn4/6PP/1PP2P2/3PP1B1/1NQ1K2R w K - 1 28",
        ("Qc2+",),
        note="mate in 9, white to move; Stockfish depth 16 prefers it by 8718 centipawns",
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


# Positions this engine does **not** currently solve, kept rather than
# discarded. They were mined and verified the same way, and each is a tactic
# Stockfish sees decisively at depth 16 that a depth-4 search here misses.
#
# They are not assertions. A suite that demanded these pass would be red
# forever and would stop being read. They are checked and *reported*: if a
# change makes one start solving, that is a real improvement and the test says
# so instead of letting it pass unnoticed.
KNOWN_MISSES: tuple[TacticalPosition, ...] = (
    TacticalPosition(
        "known miss 1",
        "rnb2kB1/pp1p4/2N2p2/2P3p1/7p/2N1P3/PPPQ1PPP/R3K2R w KQ - 0 19",
        ("Qd5",),
        note="mate in 3, white to move; Stockfish depth 16 prefers it by 8824 centipawns",
    ),
    TacticalPosition(
        "known miss 2",
        "rnb2Qn1/2kp3N/pp1p3p/8/2P5/1P1p4/P3QPPP/R1B1KB1R w KQ - 0 19",
        ("Qxd6+",),
        note="mate in 8, white to move; Stockfish depth 16 prefers it by 8681 centipawns",
    ),
    TacticalPosition(
        "known miss 3",
        "4kb1R/8/2p2p2/N1Nbp3/1P1P2P1/2P1B3/5K2/2R2Q2 w - - 0 35",
        ("Ke2",),
        note="mate in 9, white to move; Stockfish depth 16 prefers it by 8663 centipawns",
    ),
    TacticalPosition(
        "known miss 4",
        "r5nN/1Q6/n4p2/p1k1p3/2p4P/P4P2/P2PP3/R1B1KB1R w KQ - 1 22",
        ("Rb1",),
        note="mate in 8, white to move; Stockfish depth 16 prefers it by 8685 centipawns",
    ),
    TacticalPosition(
        "known miss 5",
        "1r3r2/ppQ4p/2p1pkpP/P2p4/2P5/7N/P4P1P/R3KB1R w KQ - 11 26",
        ("Qg7+",),
        note="mate in 6, white to move; Stockfish depth 16 prefers it by 8894 centipawns",
    ),
    TacticalPosition(
        "known miss 6",
        "1Q6/p4r1p/1pp1pkpP/P2p4/2P5/3B3N/P4P1P/R3K2R w KQ - 0 28",
        ("Qd8+",),
        note="wins material (+15.7), white to move; Stockfish depth 16 prefers it by 250 centipawns",
    ),
)


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
