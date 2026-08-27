# Phase 16 expected behavior

Phase 16 adds the first external gauntlet scaffold for calibrated strength
measurement.

## Implemented

- `scripts/run_gauntlet.sh` runs Atropos against a configured UCI opponent
  through `cutechess-cli`.
- Gauntlet output is written under `games/` as PGN and log files.
- `strength::summarize_match_score` converts win/loss/draw counts to score rate
  and approximate Elo difference.
- `strength::parse_cutechess_score_line` parses common cutechess score summary
  lines such as `Score of Atropos vs Baseline: 10 - 5 - 5`.

## Usage

```sh
OPPONENT_CMD=stockfish OPPONENT_NAME=StockfishSkill1 GAMES=100 TC=10+0.1 \
  ./scripts/run_gauntlet.sh
```

Optional environment variables:

- `ATROPOS_BIN`: defaults to `./build/atropos`
- `OPPONENT_CMD`: required opponent UCI command
- `OPPONENT_NAME`: defaults to `Opponent`
- `GAMES`: defaults to `100`
- `TC`: defaults to `10+0.1`
- `CONCURRENCY`: defaults to `1`
- `OUT_DIR`: defaults to `games`

## Elo Interpretation

The score-derived Elo difference is meaningful only relative to the selected
opponent, time control and opening/position policy. A stable public estimate
still requires many games, opponent calibration and confidence intervals.

## Coverage

The regression suite covers match-score summary math and cutechess score-line
parsing. The external script is intentionally not run by default because it
depends on locally installed engines and `cutechess-cli`.
