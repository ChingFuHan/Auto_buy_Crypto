# 原生止損單 (Native Stop Loss) 交接文件

更新時間：2026-04-25 07:00 +08:00

## 目前結論

### 已確認
1. Binance USD-M Futures 的原生條件單目前要走 `POST /fapi/v1/algoOrder`。
2. `algoType=CONDITIONAL` + `type=STOP_MARKET` 可以成功建立 BTCUSDT 原生止損。
3. Hedge Mode 下，平多倉可用參數組合為：
   - `side=SELL`
   - `positionSide=LONG`
   - `closePosition=true`
4. `triggerPrice` 才是 algo order 的觸發價欄位，不是 `/fapi/v1/order` 那套 `stopPrice`。
5. `PositionState` 已補查 `openAlgoOrders`，不會再漏算原生止損。

### 截至 2026-04-25 目前實況
- 2026-04-23 已真實驗證成功收到：
  - `ENTRY_ORDER_SUCCESS`
  - `STOP_ORDER_SUCCESS`
  - `STOP_ORDER_POSITION_CLOSED`
- 2026-04-25 唯讀 Binance 查詢結果為：
  - `nonzero_positions=0`
  - `open_orders=0`
  - `open_algo_orders=0`
- 仍有一個持續運行中的 `main.py manual-test-entry` 程序存在；若要重跑測試，建議先確認是否需要關閉。
- `logs/app.log` 在 2026-04-25 06:58:19 還顯示 `positions=1 open_order_symbols=1`，06:58:49 已變成 `positions=0 open_order_symbols=0`；但同段沒有新的 `STOP_ORDER_*` 記錄，這是下一位 agent 要釐清的點。

## 已實測成功的參數組合

```python
{
    "algoType": "CONDITIONAL",
    "symbol": "BTCUSDT",
    "side": "SELL",
    "positionSide": "LONG",
    "type": "STOP_MARKET",
    "triggerPrice": "<low price>",
    "workingType": "CONTRACT_PRICE",
    "closePosition": "true",
}
```

## 根因

之前一直失敗，不是因為 `STOP_MARKET` 類型不存在，而是因為 Binance 現在把 USD-M Futures 的條件單拆到 algo order API：

- 錯的路徑：`POST /fapi/v1/order`
- 對的路徑：`POST /fapi/v1/algoOrder`

## 關鍵文件位置

| 文件 | 說明 |
|------|------|
| `pump_system/exchange/binance_client.py` | algo order API wrapper |
| `pump_system/execution/order_service.py` | `_place_exchange_stop()`、native stop monitor、manual test |
| `pump_system/state/position_state.py` | 補查 `openAlgoOrders` |
| `pump_system/fallback_stop/manager.py` | Hedge Mode fallback close 不再送 `reduceOnly` |
| `tests/test_order_service_stop.py` | native stop regression tests |
| `tests/test_position_state.py` | algo open orders count regression test |

## 下一位接手建議順序

1. 先確認舊的 `manual-test-entry` 程序是否還在跑。
2. 先做唯讀 Binance 查詢，確認帳戶仍然是 `0` 持倉 / `0` 一般單 / `0` algo 單。
3. 若要重跑 native stop 測試，建議先關閉舊程序，再跑一次新的 `manual-test-entry`。
4. 目標不是再證明「能掛單」，而是補到一次真正的 `STOP_ORDER_TRIGGERED` Telegram。
5. 若再次出現 `1/1 -> 0/0` 但沒有 `STOP_ORDER_*` 記錄，優先查 monitor / reconcile 邏輯，不要先懷疑 endpoint。

## 測試命令

```powershell
# 查是否有舊的 manual-test-entry 程序
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py manual-test-entry*' } | Select-Object ProcessId, CommandLine

# 查目前 Binance 帳戶狀態
@'
import asyncio
from config import load_settings
from pump_system.exchange.binance_client import BinanceClient

async def main():
    client = BinanceClient(load_settings())
    try:
        positions = await client.get_position_risk()
        open_orders = await client.get_open_orders()
        open_algo = await client.get_open_algo_orders(algo_type='CONDITIONAL')
        nonzero = [p for p in positions if abs(float(p.get('positionAmt', '0') or 0)) > 0]
        print({'nonzero_positions': len(nonzero), 'open_orders': len(open_orders), 'open_algo_orders': len(open_algo)})
        print(nonzero[:5])
        print(open_orders[:5])
        print(open_algo[:5])
    finally:
        await client.close()

asyncio.run(main())
'@ | .\.venv\Scripts\python -

# 重跑完整流程
.\.venv\Scripts\python main.py manual-test-entry
```

## 下一位接手先做什麼

先不要再追 `/fapi/v1/order` 舊問題。先確認帳戶與程序狀態，再直接補 `STOP_ORDER_TRIGGERED` 實測與 2026-04-25 06:58 那次無通知狀態轉移的原因。
