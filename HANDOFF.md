## HANDOFF - BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM

### 本次完成事項
- 已確認 Binance USD-M Futures 目前官方原生條件單入口是 `POST /fapi/v1/algoOrder`，不是原本失敗的 `/fapi/v1/order`
- 新增 `BinanceClient.create_algo_order()` / `get_open_algo_orders()`，native stop 改走 `algoType=CONDITIONAL` + `type=STOP_MARKET`
- 已用真實 BTCUSDT 倉位實測成功掛上原生 stop algo order
- 已完成一次真實 BTCUSDT function test：`MARKET BUY` 後自動建立 `STOP_MARKET` algo order
- `PositionState` 現在會把 algo open orders 一起納入觀測，避免原生止損已存在卻顯示 `open_order_symbols=0`
- fallback market close 移除 `reduceOnly`，避免 Hedge Mode 被 Binance 拒單
- manual function test 的 stop low 已對齊專案規格，改回使用當下 in-progress `1m` low
- 關閉 `httpx` / `httpcore` INFO request log，避免 Telegram token 再次出現在 console / app.log
- 新增 native stop Telegram 事件：`STOP_ORDER_SUCCESS` / `STOP_ORDER_TRIGGERED` / `STOP_ORDER_POSITION_CLOSED`

### 進行中 / 尚未完成
- [TODO] 尚未在最新通知版本上實際收到一次 `STOP_ORDER_TRIGGERED` Telegram；本輪 live test 75 秒內未觸發 stop，最後人工收斂倉位，因此收到的是 `STOP_ORDER_POSITION_CLOSED`
- [TODO] 尚未做 PostgreSQL 端到端整合驗證

### 關鍵檔案清單
| 檔案路徑 | 用途說明 |
|---|---|
| `pump_system/exchange/binance_client.py` | 新增 algo order API wrapper |
| `pump_system/execution/order_service.py` | native stop 改走 `STOP_MARKET` algo order，manual test low 對齊 in-progress `1m` |
| `pump_system/state/position_state.py` | 同步一般 open orders + algo open orders |
| `pump_system/fallback_stop/manager.py` | Hedge Mode fallback close 改成不送 `reduceOnly` |
| `pump_system/utils/logging_utils.py` | 關閉 `httpx` request log，避免 token 洩漏 |
| `README.md` | 記錄 Binance 官方當前等價 stop 實作 |

### 注意事項 / 已知風險
- [RISK] 目前帳戶上已有新的 BTCUSDT 測試倉位與對應 algo stop；若要重跑，先處理掉現有倉位與 stop
- [RISK] Binance 現在把條件單與一般 open orders 分開查；若後續還有其他觀測模組只查 `/fapi/v1/openOrders`，會漏看 native stop
- [ASSUMPTION] 2026-04-23 官方文件定義的 `New Algo Order` 即為 task.md 所說的 `STOP_MARKET` 當前等價實作

### 下一步建議
- 先決定要不要直接做 stop 觸發測試
- 若要重跑 entry test，先取消現有 algo stop 並平掉 BTCUSDT 測試倉位
- 用 `openAlgoOrders` 或交易所 UI 核對目前 `STOP_MARKET` algo order 狀態

### 關鍵決策紀錄
- 3m 正式資料來源維持 Binance 原生 3m，不改成本地聚合
- DB 僅存 finalized bars；in-progress bars 固定留在 `data/inprogress_1m.csv` / `data/inprogress_3m.csv`
- `db_util.py` 仍直接重用 pool / env naming / fetch helpers；bulk insert 仍由 repository adapter 補齊
- function test mode 不依賴 `SYMBOL_WHITELIST`，而是由 `SymbolRegistry.should_evaluate()` 額外納入 `FUNCTION_TEST_SYMBOL`
- Telegram 採 queue worker，避免通知失敗拖垮交易主流程
- Binance 原生 stop 的當前正式實作改採 `/fapi/v1/algoOrder`，不再嘗試 `STOP_LOSS_LIMIT`
- [EXCEPTION] 依使用者要求採一次性交付完整專案，未走分階段 MVP；其餘 `god_rule.md` 規則維持遵守。預計恢復時間：下一輪功能擴充時回到迭代式交付

### 驗證紀錄
- `./.venv/Scripts/python -m pytest -q`
- 真實 BTCUSDT 測試：`MARKET BUY` -> `POST /fapi/v1/algoOrder` 成功，`algoStatus=NEW`
- 真實 BTCUSDT 測試：Telegram 已收到 `STOP_ORDER_SUCCESS`
- 真實 BTCUSDT 測試：75 秒內未觸發 stop；人工平倉收斂後，Telegram 收到 `STOP_ORDER_POSITION_CLOSED`

### 資源回報
- ⏱️ 任務耗時：本輪持續中 | Tokens (估算): IN 18k / OUT 9k | 狀態: 進行中
