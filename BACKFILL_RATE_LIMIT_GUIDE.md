# Backfill Rate Limit Handling Guide

## Overview

The backfill system now includes **persistent rate limit handling** that automatically waits when hitting Binance API rate limits (HTTP 429 errors). The system will:

1. **Detect rate limit** (429 error)
2. **Wait until the next minute** (~60 seconds)
3. **Resume backfilling** automatically
4. **Continue until all 120 days of data is complete**

## What Changed

### Before
- Rate limit detection existed but waited only within a single `_request()` call
- Once the retry attempts exhausted in a request, the program exited with error
- Multiple requests during backfill would each trigger separate rate limits and fail

### After
- `rate_limit_wait_until_ms` is now **an instance variable** in `BinanceClient`
- It persists across ALL requests from the entire backfill operation
- When hit, it waits until the next minute window, then **automatically continues**
- All requests honor the global rate limit window

## How It Works

### In the Code

```python
class BinanceClient:
    def __init__(self, ...):
        # ... existing code ...
        self.rate_limit_wait_until_ms = 0.0  # ← NEW: Persistent rate limit tracker
```

### When Rate Limit Hits

1. **Detection**: API returns 429 status
2. **Action**: Set `self.rate_limit_wait_until_ms = now_ms + 60_000`
3. **Wait**: All subsequent requests check this window and wait if needed
4. **Resume**: After 60+ seconds, requests proceed normally

### Example Flow

```
Time: 13:34:44 - Symbol 1 backfill request
Time: 13:34:44 - Binance returns 429 (rate limit)
Time: 13:34:44 - Set wait window until 13:35:44
Time: 13:34:44 - Wait 60 seconds + 0.5s buffer
Time: 13:35:45 - Symbol 1 request retries (succeeds)
Time: 13:35:46 - Symbol 2 request (checks wait window, already expired, proceeds)
Time: 13:35:47 - Symbol 3 request (proceeds normally)
... backfill continues across all symbols until 120 days complete
```

## Running Backfill

### On Linux (VM)

```bash
cd /media/sf_agent_sanbox_vm/Auto_buy_Crypto

# Activate virtual environment
source .venv/bin/activate

# Run backfill
python3 main.py backfill

# The program will now:
# - Download 1m and 3m klines for ~120 days
# - Automatically wait when hitting rate limits
# - Continue until all symbols have their full data history
```

### On Windows (Host, using .venv)

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Run backfill
python main.py backfill

# Or using python.exe directly
.\.venv\Scripts\python.exe main.py backfill
```

## Monitoring Backfill Progress

### Real-time Logs

```bash
# Watch backfill progress
tail -f /media/sf_agent_sanbox_vm/Auto_buy_Crypto/logs/app.log | grep -E "backfill|rate limit|429"
```

### Log Messages You'll See

**Normal backfill** (every symbol completed):
```
[INFO] [market_data.backfill] backfill completed symbol=BTCUSDT interval=1m inserted=12999
[INFO] [market_data.backfill] backfill completed symbol=BTCUSDT interval=3m inserted=4399
```

**When hitting rate limit**:
```
[WARNING] [exchange.binance] rate limit 429 detected, waiting 59.5 sec until next minute method=GET path=/fapi/v1/klines
[INFO] [notify.telegram] telegram sent event_type=BINANCE_API_RATE_LIMIT_WAIT
```

**After rate limit window expires**:
```
[INFO] [market_data.backfill] backfill completed symbol=ALLOUSDT interval=1m inserted=6806
[INFO] [market_data.backfill] backfill completed symbol=ALLOUSDT interval=3m inserted=4399
```

## Configuration

### Backfill Settings in `.env`

```env
# Number of days to backfill (120 days = ~4 months)
# Don't change this unless you want less historical data
BACKFILL_DAYS=120

# Number of klines per API request (1000 is max)
BACKFILL_LIMIT=1000

# Concurrent backfill tasks (how many symbols to fetch simultaneously)
# Lower = slower but less rate limit hits
# Higher = faster but higher chance of rate limit
BACKFILL_CONCURRENCY=5
```

### Retry Settings (already configured, usually don't need to change)

```env
# API retry settings
API_RETRY_MAX_ATTEMPTS=3
API_RETRY_BACKOFF_BASE_SECONDS=1.0
API_RETRY_BACKOFF_MAX_SECONDS=8.0
```

## Expected Duration

For ~528 candidate symbols with 120-day history:

- **Without rate limits**: ~5-10 minutes
- **With rate limit waits**: ~30-45 minutes (1-2 rate limit hits expected)

## Understanding Rate Limits

Binance Futures API has:
- **Limit**: 2400 requests per minute per IP
- **Size**: ~500-700 active symbols × 2 intervals (1m, 3m) = 1000-1400 concurrent requests
- **Solution**: Our backfill concurrency (`BACKFILL_CONCURRENCY=5`) and automatic rate limit handling

## Troubleshooting

### Issue: Program Still Exits with 429 Error

**Check**: Are you using the latest code?
```bash
cd /media/sf_agent_sanbox_vm/Auto_buy_Crypto
git log --oneline -5 | head -1
```

**Solution**: Make sure you have the latest `pump_system/exchange/binance_client.py` with the `rate_limit_wait_until_ms` instance variable.

### Issue: Backfill is Very Slow

**Reason**: Rate limits are being hit frequently
**Solution**: Reduce `BACKFILL_CONCURRENCY` in `.env`
```env
BACKFILL_CONCURRENCY=3  # Was 5, now 3 = fewer parallel requests
```

### Issue: Out of Memory or Database Locks

**Reason**: Too many concurrent requests
**Solution**: 
1. Reduce `BACKFILL_CONCURRENCY`
2. Increase `BACKFILL_LIMIT` (it's already at max 1000)
3. Run backfill during off-peak hours

## Verification

After backfill completes, verify data was inserted:

```python
# Check if backfill data exists
python3 << 'EOF'
import asyncio
from config import load_settings
from pump_system.db.repository import KlineRepository

def main():
    settings = load_settings()
    repo = KlineRepository()
    
    # Check 1m data
    count_1m = repo.fetch_latest_timestamps("public.semi_auto_price_future_1m")
    print(f"Symbols with 1m data: {len(count_1m)}")
    
    # Check 3m data
    count_3m = repo.fetch_latest_timestamps("public.semi_auto_price_future_3m")
    print(f"Symbols with 3m data: {len(count_3m)}")
    
    # Show sample timestamps
    if count_1m:
        sample = list(count_1m.items())[:3]
        for symbol, ts in sample:
            print(f"  {symbol}: {ts}")

main()
EOF
```

## Technical Details

### Rate Limit Window Implementation

The rate limit handling works by:

1. **Checking at request time**: Before making HTTP request, check if `rate_limit_wait_until_ms > now_ms`
2. **Waiting if needed**: If in wait window, sleep until it expires
3. **Updating on 429**: When 429 error occurs, set `rate_limit_wait_until_ms = now_ms + 60_000`
4. **Persistent state**: The `rate_limit_wait_until_ms` persists for the entire `BinanceClient` instance lifetime

### Code Location

File: `pump_system/exchange/binance_client.py`

Changes:
- Added `self.rate_limit_wait_until_ms = 0.0` to `__init__`
- Modified `_request()` method to check/update this window

## Related Files

| File | Purpose |
|------|---------|
| `pump_system/exchange/binance_client.py` | Core rate limit handling (MODIFIED) |
| `pump_system/market_data/backfill.py` | Backfill orchestration |
| `config.py` | Backfill configuration |
| `main.py` | Entry point for `backfill` command |

## Questions or Issues?

If backfill doesn't work as expected:

1. Check logs: `tail -f logs/app.log`
2. Verify API key/secret are valid
3. Ensure you have DB connectivity: `python3 main.py validate`
4. Confirm Binance server time sync: Check logs for `server time synced offset_ms=`

