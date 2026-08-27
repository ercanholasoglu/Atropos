#!/usr/bin/env sh
set -eu

GAMES="${GAMES:-100}"
TC="${TC:-10+0.1}"
CONCURRENCY="${CONCURRENCY:-1}"
ATROPOS_BIN="${ATROPOS_BIN:-./build/atropos}"
OPPONENT_NAME="${OPPONENT_NAME:-Opponent}"
OPPONENT_CMD="${OPPONENT_CMD:-}"
OUT_DIR="${OUT_DIR:-games}"

if ! command -v cutechess-cli >/dev/null 2>&1; then
  echo "cutechess-cli not found. Install cutechess-cli before running an external gauntlet." >&2
  exit 1
fi

if [ ! -x "$ATROPOS_BIN" ]; then
  echo "Atropos binary is not executable: $ATROPOS_BIN" >&2
  exit 1
fi

if [ -z "$OPPONENT_CMD" ]; then
  echo "Set OPPONENT_CMD to the opponent UCI engine command." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
PGN="$OUT_DIR/atropos_vs_${OPPONENT_NAME}_${STAMP}.pgn"
LOG="$OUT_DIR/atropos_vs_${OPPONENT_NAME}_${STAMP}.log"

cutechess-cli \
  -engine "cmd=$ATROPOS_BIN" "name=Atropos" \
  -engine "cmd=$OPPONENT_CMD" "name=$OPPONENT_NAME" \
  -each "tc=$TC" proto=uci \
  -games "$GAMES" \
  -repeat \
  -concurrency "$CONCURRENCY" \
  -pgnout "$PGN" \
  2>&1 | tee "$LOG"

echo "pgn $PGN"
echo "log $LOG"
