# Phase 15 expected behavior

Phase 15 adds the first reproducible strength-tracking harness.

## Implemented

- `strength::run_self_play` plays deterministic internal games from the fixed
  benchmark starting-position suite.
- Each game searches with the configured depth and stops on checkmate,
  stalemate, threefold repetition, fifty-move rule or max-ply limit.
- The result reports games, depth, max plies, white wins, black wins, draws,
  total plies, total nodes, white score rate and score-derived Elo difference.
- UCI command: `selfplay [games] [depth] [maxplies]`.

## Elo Interpretation

The reported Elo is not an absolute engine rating. It is calculated from the
white score rate with the standard logistic Elo transform and is best read as a
side/result bias for this deterministic internal suite.

Absolute Elo requires an external opponent pool, fixed time controls, many more
games and statistical gating. That belongs in the next strength-tracking phase.

## Coverage

The regression suite covers Elo conversion, short deterministic self-play, and
the UCI `selfplay` output contract.
