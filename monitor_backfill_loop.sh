#!/bin/bash
LOG_FILE=$(ls -t backfill_final_*.log 2>/dev/null | head -1)
while true; do
  COMPLETED=$(grep "backfill completed" "$LOG_FILE" 2>/dev/null | cut -d= -f2 | cut -d' ' -f1 | sort -u | wc -l)
  TOTAL_INSERTED=$(grep "backfill completed" "$LOG_FILE" 2>/dev/null | grep "inserted=" | sed 's/.*inserted=//' | awk '{sum+=$1} END {print sum}')
  COMPLETED_MSG=$(grep "BACKFILL_COMPLETED" "$LOG_FILE" 2>/dev/null || echo "")
  
  if [ -n "$COMPLETED_MSG" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ BACKFILL_COMPLETED | 幣種: $COMPLETED | 總行數: $TOTAL_INSERTED"
    break
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 進行中 | 幣種: $COMPLETED / 528 | 總行數: $TOTAL_INSERTED"
    sleep 30
  fi
done
