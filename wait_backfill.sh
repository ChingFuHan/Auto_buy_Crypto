#!/bin/bash
LOG_FILE=$(ls -t backfill_final_*.log 2>/dev/null | head -1)
echo "Waiting for backfill to complete..."
echo "Log: $LOG_FILE"
while ! grep -q "BACKFILL_COMPLETED" "$LOG_FILE" 2>/dev/null; do
  sleep 120
  COMPLETED=$(grep "backfill completed" "$LOG_FILE" 2>/dev/null | cut -d= -f2 | cut -d' ' -f1 | sort -u | wc -l)
  TOTAL=$(grep "backfill completed" "$LOG_FILE" 2>/dev/null | grep "inserted=" | sed 's/.*inserted=//' | awk '{sum+=$1} END {print sum}')
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 幣種: $COMPLETED / 528 | 總行數: $TOTAL"
done
echo "✅ BACKFILL COMPLETED"
tail -5 "$LOG_FILE"
