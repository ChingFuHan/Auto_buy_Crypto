#!/bin/bash
set -e
PROJECT_DIR="/media/sf_agent_sanbox_vm/Auto_buy_Crypto"
cd "$PROJECT_DIR"

# Ensure conservative concurrency (do not overwrite existing setting)
if ! grep -q '^BACKFILL_CONCURRENCY=' .env; then
  echo 'BACKFILL_CONCURRENCY=4' >> .env
fi

BACKOFF=5
MAX_BACKOFF=300
RUN_COUNT=0

while true; do
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  LOG_FILE="backfill_supervisor_${TIMESTAMP}.log"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting backfill (run #$((RUN_COUNT+1))) -> $LOG_FILE"
  # start backfill and capture exit code
  python3 main.py backfill > "$LOG_FILE" 2>&1
  EXIT_CODE=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] backfill exited with code $EXIT_CODE"

  # if completion marker present in the log, finish
  if grep -q "BACKFILL_COMPLETED" "$LOG_FILE" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] BACKFILL_COMPLETED detected in $LOG_FILE. Exiting supervisor."
    break
  fi

  # increment run count and backoff
  RUN_COUNT=$((RUN_COUNT+1))
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] No completion detected. Sleeping ${BACKOFF}s before restart..."
  sleep $BACKOFF
  BACKOFF=$((BACKOFF*2))
  if [ $BACKOFF -gt $MAX_BACKOFF ]; then BACKOFF=$MAX_BACKOFF; fi

  # continue loop (will restart backfill)
done

echo "Supervisor finished."
