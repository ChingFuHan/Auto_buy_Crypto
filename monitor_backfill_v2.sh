#!/bin/bash
LOG_FILE=$(ls -t backfill_retry_*.log 2>/dev/null | head -1)
echo "════════════════════════════════════════════════════════════════"
echo "Backfill 進度 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════════"
COMPLETED=$(grep "backfill completed" "$LOG_FILE" 2>/dev/null | cut -d= -f2 | cut -d' ' -f1 | sort -u | wc -l)
TOTAL_INSERTED=$(grep "backfill completed" "$LOG_FILE" 2>/dev/null | grep "inserted=" | sed 's/.*inserted=//' | awk '{sum+=$1} END {print sum}')
RATE_LIMITS=$(grep -c "429\|RATE_LIMIT" "$LOG_FILE" 2>/dev/null || echo 0)
echo "✅ 幣種已完成: $COMPLETED / 528"
echo "📊 總插入行數: $TOTAL_INSERTED"
echo "⚠️  Rate limit: $RATE_LIMITS 次"
echo "🔄 最新符號:"
tail -5 "$LOG_FILE" 2>/dev/null | grep "backfill completed" | head -3 | sed 's/.*symbol=/  /' | sed 's/ interval.*//'
echo "════════════════════════════════════════════════════════════════"
