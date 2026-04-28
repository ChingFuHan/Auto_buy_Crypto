#!/bin/bash
# 完成偵測監控腳本 - 每 15 分鐘採樣，完成後建立 marker 並更新 HANDOFF.md
PROJECT_DIR="/media/sf_agent_sanbox_vm/Auto_buy_Crypto"
cd "$PROJECT_DIR" || exit 1

MARKER_FILE="backfill_DONE.marker"
LOG_FILE="backfill_completion_monitor.log"
TOTAL_SYMBOLS=528
CHECK_INTERVAL=900  # 15 minutes

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

get_db_counts() {
  if command -v psql >/dev/null 2>&1; then
    D1M=$(PGPASSWORD=123456 psql -h 192.168.0.72 -U postgres -d daily -t \
      -c "SELECT COUNT(DISTINCT code) FROM public.semi_auto_price_future_1m;" 2>/dev/null | tr -d ' \n' || echo "0")
    D3M=$(PGPASSWORD=123456 psql -h 192.168.0.72 -U postgres -d daily -t \
      -c "SELECT COUNT(DISTINCT code) FROM public.semi_auto_price_future_3m;" 2>/dev/null | tr -d ' \n' || echo "0")
    R1M=$(PGPASSWORD=123456 psql -h 192.168.0.72 -U postgres -d daily -t \
      -c "SELECT COUNT(*) FROM public.semi_auto_price_future_1m;" 2>/dev/null | tr -d ' \n' || echo "0")
    R3M=$(PGPASSWORD=123456 psql -h 192.168.0.72 -U postgres -d daily -t \
      -c "SELECT COUNT(*) FROM public.semi_auto_price_future_3m;" 2>/dev/null | tr -d ' \n' || echo "0")
    echo "DB_D1M=$D1M DB_D3M=$D3M DB_R1M=$R1M DB_R3M=$R3M"
  else
    echo "DB_D1M=? DB_D3M=? DB_R1M=? DB_R3M=?"
  fi
}

count_rate_limits() {
  grep -h -c "429\|RATE_LIMIT\|rate limit" backfill_supervisor_*.log 2>/dev/null | awk '{s+=$1} END{print s+0}'
}

check_completion() {
  local D1M="$1"
  # Check for BACKFILL_COMPLETED in logs
  if grep -rq "BACKFILL_COMPLETED" backfill_supervisor_*.log 2>/dev/null; then
    echo "DONE_LOG"
    return 0
  fi
  # Check if DB symbols >= 528
  if [[ "$D1M" =~ ^[0-9]+$ ]] && [ "$D1M" -ge "$TOTAL_SYMBOLS" ]; then
    echo "DONE_DB"
    return 0
  fi
  echo "RUNNING"
  return 1
}

log "Completion monitor started (PID=$$, check every ${CHECK_INTERVAL}s, target $TOTAL_SYMBOLS symbols)"

while true; do
  NOW=$(date --iso-8601=seconds)
  SUPPID=$(cat backfill_supervisor.pid 2>/dev/null || echo "")
  SUPPID_RUNNING="no"
  if [[ "$SUPPID" =~ ^[0-9]+$ ]] && ps -p "$SUPPID" > /dev/null 2>&1; then
    SUPPID_RUNNING="yes"
  fi

  COUNTS=$(get_db_counts)
  D1M=$(echo "$COUNTS" | grep -o 'DB_D1M=[0-9?]*' | cut -d= -f2 || echo "0")
  D3M=$(echo "$COUNTS" | grep -o 'DB_D3M=[0-9?]*' | cut -d= -f2 || echo "0")
  R1M=$(echo "$COUNTS" | grep -o 'DB_R1M=[0-9?]*' | cut -d= -f2 || echo "0")
  R3M=$(echo "$COUNTS" | grep -o 'DB_R3M=[0-9?]*' | cut -d= -f2 || echo "0")
  RATE_LIMITS=$(count_rate_limits)
  TOTAL_ROWS=$(( R1M + R3M ))

  STATUS=$(check_completion "$D1M")
  log "SNAPSHOT: symbols_1m=$D1M/$TOTAL_SYMBOLS symbols_3m=$D3M rows_1m=$R1M rows_3m=$R3M total_rows=$TOTAL_ROWS rate_limits=$RATE_LIMITS supervisor=$SUPPID_RUNNING status=$STATUS"

  # Restart supervisor if not running and not complete
  if [ "$SUPPID_RUNNING" = "no" ] && [ "$STATUS" = "RUNNING" ]; then
    log "Supervisor not running, restarting..."
    nohup bash backfill_supervisor.sh >> backfill_supervisor.out 2>&1 &
    NEW_PID=$!
    echo $NEW_PID > backfill_supervisor.pid
    log "Supervisor restarted PID=$NEW_PID"
  fi

  # Check if completed
  if [ "$STATUS" = "DONE_LOG" ] || [ "$STATUS" = "DONE_DB" ]; then
    log "=== BACKFILL COMPLETED === $STATUS"
    SNIPPET=$(ls -t backfill_supervisor_*.log 2>/dev/null | head -1 | xargs tail -n 10 2>/dev/null || echo "(no log)")
    SUMMARY="=== Backfill Completed [$NOW] === symbols=$D1M/$TOTAL_SYMBOLS total_rows=$TOTAL_ROWS rate_limit_hits=$RATE_LIMITS status=$STATUS"

    # Write completion marker
    echo "$SUMMARY" > "$MARKER_FILE"
    echo "$SNIPPET" >> "$MARKER_FILE"
    log "Completion marker written: $MARKER_FILE"

    # Append to HANDOFF.md
    {
      echo ""
      echo "---"
      echo "## Backfill Completed [$NOW]"
      echo ""
      echo "- symbols completed (1m): $D1M / $TOTAL_SYMBOLS"
      echo "- symbols completed (3m): $D3M / $TOTAL_SYMBOLS"
      echo "- total rows inserted: $TOTAL_ROWS (1m=$R1M, 3m=$R3M)"
      echo "- rate-limit hits: $RATE_LIMITS"
      echo "- detection method: $STATUS"
      echo ""
      echo "### Log snippet (last 10 lines):"
      echo '```'
      echo "$SNIPPET"
      echo '```'
    } >> HANDOFF.md
    log "HANDOFF.md updated"
    log "Completion monitor exiting"
    break
  fi

  sleep "$CHECK_INTERVAL"
done

log "Monitor done."
