# 原生止損單 (Native Stop Loss) 交接文件

## 當前狀態

### 已確認
1. Binance USD-M Futures 的原生條件單目前要走 `POST /fapi/v1/algoOrder`
2. `algoType=CONDITIONAL` + `type=STOP_MARKET` 可以成功建立 BTCUSDT 原生止損
3. Hedge Mode 下，平多倉可用：
   - `side=SELL`
   - `positionSide=LONG`
   - `closePosition=true`
4. `triggerPrice` 才是 algo order 的觸發價欄位，不是 `/fapi/v1/order` 那套 `stopPrice`

### 已實測成功的參數組合

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
| `pump_system/execution/order_service.py` | `_place_exchange_stop()` 改走 algo order |
| `pump_system/state/position_state.py` | 補查 `openAlgoOrders` |
| `pump_system/fallback_stop/manager.py` | Hedge Mode fallback close 不再送 `reduceOnly` |

## 測試命令

```powershell
# 查目前 BTCUSDT 倉位與 algo order
.\.venv\Scripts\python -c "import asyncio; from config import load_settings; from pump_system.exchange.binance_client import BinanceClient; async def main(): client=BinanceClient(load_settings()); print(await client.get_position_risk('BTCUSDT')); print(await client.get_open_algo_orders(symbol='BTCUSDT', algo_type='CONDITIONAL')); await client.close(); asyncio.run(main())"

# 清倉並取消舊 algo order 後，再重跑完整流程
.\.venv\Scripts\python main.py manual-test-entry
```

## 下一位接手先做什麼

先把舊 BTCUSDT 測試倉位清乾淨，再用 `manual-test-entry` 驗證「market entry -> algo STOP_MARKET」整條程式路徑是否成功。
