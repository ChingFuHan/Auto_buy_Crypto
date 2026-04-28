# Quick Start: Backfill with Rate Limit Handling

## One-Line Commands

### Linux/WSL (from shared folder or VM)
```bash
cd /media/sf_agent_sanbox_vm/Auto_buy_Crypto && source .venv/bin/activate && python3 main.py backfill
```

### Windows (PowerShell)
```powershell
cd C:\Users\User\Documents\agent_sanbox_vm\Auto_buy_Crypto
.\.venv\Scripts\python.exe main.py backfill
```

## What It Does

✅ Downloads 120 days of kline data (1m and 3m intervals)  
✅ ~528 symbols × 2 intervals = ~1,056 requests total  
✅ **Automatically waits when hitting rate limit (429)**  
✅ Resumes after ~60 seconds  
✅ Continues until all data is complete  

## Expected Output

```
[2026-04-25 14:00:00] [INFO] [market_data.backfill] backfill completed symbol=BTCUSDT interval=1m inserted=12999
[2026-04-25 14:00:01] [INFO] [market_data.backfill] backfill completed symbol=BTCUSDT interval=3m inserted=4399
...

# When rate limit hits (after ~30-40 requests):
[2026-04-25 14:05:44] [WARNING] [exchange.binance] rate limit 429 detected, waiting 59.5 sec until next minute
[2026-04-25 14:05:44] [INFO] [notify.telegram] telegram sent event_type=BINANCE_API_RATE_LIMIT_WAIT

# Automatically resumes:
[2026-04-25 14:06:45] [INFO] [market_data.backfill] backfill completed symbol=ALLOUSDT interval=1m inserted=6806
...
```

## How Long Does It Take?

- **Without rate limits**: 5-10 minutes
- **With rate limit wait**: 30-45 minutes (typical)
- **Total time**: Depends on number of rate limit hits (usually 1-3)

## Monitor Progress

```bash
# Real-time log streaming (show only backfill-related lines)
tail -f /media/sf_agent_sanbox_vm/Auto_buy_Crypto/logs/app.log | grep -E "backfill|rate limit|inserted"
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Still getting 429 errors?** | Edit `.env`, set `BACKFILL_CONCURRENCY=3` (was 5) |
| **Program exits on error?** | Make sure you have the latest code (backfill rate limit fix applied) |
| **"symbol registry not loaded"?** | Check that `.env` config is valid, try `python3 main.py validate` |
| **Slow progress?** | Normal - rate limits cause waits. Check logs to see if 429 is being hit |

## Verify Backfill Completed

After backfill finishes:

```bash
# Check how many symbols have 1m data
sqlite3 data/daily.db "SELECT COUNT(DISTINCT symbol) FROM public.semi_auto_price_future_1m;"

# Expected: ~500-528 symbols
```

## Configuration (if needed)

Edit `.env` to adjust:

```env
# How many days to backfill
BACKFILL_DAYS=120

# Max parallel requests (lower = slower but fewer rate limits)
BACKFILL_CONCURRENCY=5

# Klines per request (1000 is max, don't change)
BACKFILL_LIMIT=1000
```

## That's It!

The backfill will now:
- ✅ Download all klines automatically
- ✅ Handle rate limits gracefully
- ✅ Wait ~60 seconds when needed
- ✅ Resume and continue automatically
- ✅ Complete without manual intervention

**Just run the command and let it finish!**

For more details, see: `BACKFILL_RATE_LIMIT_GUIDE.md`
