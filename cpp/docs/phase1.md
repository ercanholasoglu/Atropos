# Phase 1 expected behavior

Phase 1 implements a simple mailbox board representation and legal move
generation for standard chess only.

## Implemented

- FEN parsing and serialization
- Side to move, castling rights, en passant square, halfmove clock and fullmove
  number
- Legal move generation by pseudo-legal generation followed by make/check
  filtering
- Check and double-check evasion through legal filtering
- Castling with occupied-square and attacked-transit validation
- En passant, including discovered-check rejection
- Quiet and capture promotions to queen, rook, bishop and knight
- Make/unmake state restoration
- Deterministic Zobrist hash recomputation
- Repetition-key tracking for repeated positions
- UCI `position ... moves ...` state updates
- UCI `go` deterministic legal fallback move

## Assumptions

- Correctness is prioritized over speed. The implementation uses a mailbox board
  and recomputes hashes instead of maintaining incremental bitboards.
- `go` does not search. It returns the first legal move generated from board
  order, or `bestmove 0000` if no legal move exists.
- Movegen allocates vectors. Allocation-light hot paths will be addressed after
  perft correctness and search requirements are in place.

## Regression measurement

The Phase 1 regression suite includes deterministic unit tests for FEN
roundtrip, state counters, castling rights, legal move counts, castling transit
attack rejection, en passant discovered check rejection, all promotion choices,
Zobrist hash consistency, repetition tracking, UCI bestmove legality and a
fixed-seed random legal make/unmake invariant test.
