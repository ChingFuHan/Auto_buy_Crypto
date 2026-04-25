## HANDOFF - BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM

更新時間：2026-04-25 07:54 +08:00

### 一句話現況
- 核心架構已完成，原生止損已從舊的 `/fapi/v1/order` 修正為 `/fapi/v1/algoOrder`，主流程可跑。
- 2026-04-25 已完成真實 BNBUSDT controlled stop test，確認 `MARKET BUY -> STOP_MARKET algo order -> native stop fill`，Telegram 已收到 `STOP_ORDER_TRIGGERED`。
- 2026-04-25 已完成 PostgreSQL 端到端分流驗證，確認 in-progress 只進本地 CSV，finalized 1m/3m 進既有 DB 表。
- 2026-04-25 重新核對後，單元測試為 `11 passed`，Binance 帳戶目前唯讀查詢為 `0` 非零持倉 / `0` 一般 open orders / `0` algo orders。

### 本輪已重新確認的事實
- `pump_system/` 主程式沒有新的未提交程式碼 diff；目前 git dirty 主要集中在既有 handoff / `final_files/` 匯出物與筆記檔。
- 精準程序查詢確認目前沒有 Python `main.py manual-test-entry` 常駐程序。
- 我用唯讀 Binance 查詢再次確認後，當下帳戶狀態確實是：
  - `nonzero_positions=0`
  - `open_orders=0`
  - `open_algo_orders=0`
- 2026-04-25 07:52 BNBUSDT controlled stop test：
  - entry order `89314554687`，`BUY LONG 0.01 BNBUSDT`，avgPrice `636.50000`
  - stop algo `algoId=4000001164771108`，`clientAlgoId=stop_bnbusdt_1777074774`，triggerPrice `636.490`
  - native stop fill child order `89314555215`
  - `logs/app.log` 顯示 `telegram sent event_type=STOP_ORDER_TRIGGERED`
- PostgreSQL E2E 使用測試 symbol `E2ETSTUSDT`：
  - in-progress 1m/3m 經 periodic flush 後只出現在 `data/inprogress_1m.csv` / `data/inprogress_3m.csv`，DB 仍為 0 筆
  - finalized 1m/3m 經 `_flush_finalized_batches()` 後分別寫入 `public.semi_auto_price_future_1m` / `public.semi_auto_price_future_3m` 各 1 筆
  - finalized 後 CSV 測試 rows 被移除，DB 測試 rows 已清理回 0 筆
- 2026-04-25 06:58 的 `1/1 -> 0/0` 已查明：
  - 實際 symbol 是 `BSBUSDT`
  - 2026-04-24 16:45:32 有外部 `aos_usdt_...` client order 建立 `BUY LONG 349 BSBUSDT`
  - 2026-04-24 16:45:53 有外部 Android `STOP_MARKET` closePosition stop，client id `android_K3gRFBMtyAZXJUjC7iOM`
  - 2026-04-25 06:58:21 Android 市價減倉單 `orderId=420103041` / `clientOrderId=android_rgm3BnB7hAiK4vmNozmp` 成交，原 Android stop 同時被取消
  - 因為這組倉位與 stop 不是本 bot 建立的 `entry_*` / `stop_*` tracker，bot 只有 position sync 看到 `1/1 -> 0/0`，不會產生新的 `STOP_ORDER_*` log
- `data/fallback_stop_state.csv` 目前只留下歷史紀錄，最新狀態是 `POSITION_ALREADY_CLOSED`，不是 active fallback。

### 已完成事項
- 已確認 Binance USD-M Futures 目前官方原生條件單入口是 `POST /fapi/v1/algoOrder`，不是原本失敗的 `/fapi/v1/order`。
- 已新增 `BinanceClient.create_algo_order()` / `get_open_algo_orders()`，native stop 改走 `algoType=CONDITIONAL` + `type=STOP_MARKET`。
- 已用真實 BTCUSDT 倉位實測成功掛上原生 stop algo order。
- 已完成至少一次真實 BTCUSDT function test：`MARKET BUY` 後自動建立 `STOP_MARKET` algo order。
- `PositionState` 現在會把 algo open orders 一起納入觀測，避免原生止損已存在卻顯示 `open_order_symbols=0`。
- fallback market close 已移除 `reduceOnly`，避免 Hedge Mode 被 Binance 拒單。
- manual function test 的 stop low 已對齊專案規格，改回使用當下 in-progress `1m` low。
- 已關閉 `httpx` / `httpcore` INFO request log，避免 Telegram token 再次出現在 console / `app.log`。
- 已新增 native stop Telegram 事件：
  - `STOP_ORDER_SUCCESS`
  - `STOP_ORDER_TRIGGERED`
  - `STOP_ORDER_POSITION_CLOSED`
- 已用 BNBUSDT controlled test 實際收到 `STOP_ORDER_TRIGGERED` Telegram。
- 已完成 PostgreSQL E2E 分流驗證，並清理測試 rows。
- 已釐清 2026-04-25 06:58 無 `STOP_ORDER_*` 的原因是外部 Android/AOS BSBUSDT 倉位收斂，不是本 bot native stop monitor 漏報。
- 已補齊回歸測試：
  - native stop 走 algo endpoint
  - native stop trigger 通知
  - algo order 計入 position state
  - fallback stale state 清理

### 目前真正還沒完成的事
- 暫無本輪 blocker。下一步若要擴充，建議補一個不打實盤、但覆蓋 algo history 查詢欄位的 integration-style regression test，避免未來 Binance response 變動時漏掉 native stop fill 判斷。

### 下一位 agent 應先做什麼
1. 若要再做實盤測試，仍先查程序與 Binance 帳戶狀態，確認 `0` 持倉 / `0` 一般單 / `0` algo 單。
2. 若要長時間跑主程式，先確認使用者是否允許 live production mode 繼續交易。
3. 若要改 native stop monitor，保留目前已實測成功的 `/fapi/v1/algoOrder` 路徑與 `STOP_ORDER_TRIGGERED` Telegram 行為。

### 建議的第一批命令

```powershell
# 1. 查目前是否還有舊的 manual-test-entry 常駐程序
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*main.py manual-test-entry*' } | Select-Object ProcessId, CommandLine

# 2. 重新跑單元測試
.\.venv\Scripts\python -m pytest -q

# 3. 唯讀查 Binance 帳戶狀態
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
    finally:
        await client.close()

asyncio.run(main())
'@ | .\.venv\Scripts\python -

# 4. 若決定重跑功能測試
.\.venv\Scripts\python main.py manual-test-entry

# 5. 若要做 DB / wiring 驗證
.\.venv\Scripts\python main.py validate
.\.venv\Scripts\python main.py backfill
```

### 關鍵檔案清單
| 檔案路徑 | 用途說明 |
|---|---|
| `pump_system/exchange/binance_client.py` | algo order API wrapper，包含 `/fapi/v1/algoOrder` 與 `/fapi/v1/openAlgoOrders` |
| `pump_system/execution/order_service.py` | entry、native stop 掛單、native stop monitor、manual function test |
| `pump_system/state/position_state.py` | 同步一般 open orders + algo open orders |
| `pump_system/fallback_stop/manager.py` | fallback stop CSV 狀態與本地平倉 |
| `pump_system/app.py` | bootstrap、background tasks、DB flush、manual-test-entry 入口 |
| `pump_system/utils/logging_utils.py` | 關閉高風險 HTTP request log |
| `tests/test_order_service_stop.py` | native stop endpoint / trigger regression tests |
| `tests/test_position_state.py` | algo order count regression test |
| `README.md` | 記錄官方當前 stop 等價實作與 workingType 說明 |
| `logs/app.log` | 真實流程與近期狀態變化的第一手證據 |

### 注意事項 / 已知風險
- [RISK] Binance 把條件單與一般 open orders 分開查；若後續還有其他觀測模組只查 `/fapi/v1/openOrders`，仍會漏看 native stop。
- [RISK] 若 Binance 未來改變 algo trigger 後 child order 的 `clientOrderId` 對應方式，目前 `_find_order_by_client_id()` 可能需要改成同時查 `/fapi/v1/algoOrder` 的 `actualOrderId` / `actualQty` / `actualPrice` 欄位。
- [ASSUMPTION] 2026-04-23 官方文件定義的 `New Algo Order` 即為 task.md 所說的 `STOP_MARKET` 當前等價實作。

### 關鍵決策紀錄
- 3m 正式資料來源維持 Binance 原生 3m，不改成本地聚合。
- DB 僅存 finalized bars；in-progress bars 固定留在 `data/inprogress_1m.csv` / `data/inprogress_3m.csv`。
- `db_util.py` 仍直接重用 pool / env naming / fetch helpers；bulk insert 仍由 repository adapter 補齊。
- function test mode 不依賴 `SYMBOL_WHITELIST`，而是由 `SymbolRegistry.should_evaluate()` 額外納入 `FUNCTION_TEST_SYMBOL`。
- Telegram 採 queue worker，避免通知失敗拖垮交易主流程。
- Binance 原生 stop 的正式實作改採 `/fapi/v1/algoOrder`，不再嘗試 `STOP_LOSS_LIMIT`。
- [EXCEPTION] 依使用者要求採一次性交付完整專案，未走分階段 MVP；其餘 `god_rule.md` 規則維持遵守。預計恢復時間：下一輪功能擴充時回到迭代式交付。

### 驗證紀錄
- 2026-04-25：`.\.venv\Scripts\python -m pytest -q` -> `11 passed`
- 2026-04-25：精準程序查詢確認沒有 Python `main.py manual-test-entry` 常駐程序
- 2026-04-25：唯讀 Binance 查詢確認 `0` 非零持倉 / `0` 一般 open orders / `0` algo orders
- 2026-04-25：BNBUSDT controlled stop test `BUY LONG 0.01 -> /fapi/v1/algoOrder STOP_MARKET -> native stop filled`，Telegram 收到 `STOP_ORDER_TRIGGERED`
- 2026-04-25：PostgreSQL E2E 使用 `E2ETSTUSDT` 確認 in-progress 只進 CSV、finalized 1m/3m 寫入 DB 後清理回 0 筆
- 2026-04-25：查明 06:58 `1/1 -> 0/0` 是外部 Android/AOS `BSBUSDT` 倉位收斂，不是本 bot stop tracker 漏報
- 2026-04-23：真實 BTCUSDT 測試 `MARKET BUY` -> `POST /fapi/v1/algoOrder` 成功，`algoStatus=NEW`
- 2026-04-23：Telegram 已收到 `STOP_ORDER_SUCCESS`
- 2026-04-23：75 秒內未觸發 stop；人工平倉收斂後，Telegram 收到 `STOP_ORDER_POSITION_CLOSED`

### 目前工作樹狀態
- `git status` 當下 dirty 項目如下：
  - `M HANDOFF.md`
  - `M HANDOFF_NATIVE_STOP.md`
  - `M final_files/HANDOFF.md`
  - `M final_files/MANIFEST.txt`
  - `D final_files/env_example.env`
  - `M final_files/main.py`
  - `D solve_99/README.md`
  - `?? .claude/`
  - `?? Fix Leverage Bracket Error.txt`
  - `?? final_files/HANDOFF_NATIVE_STOP.md`
  - `?? final_files/solve_99_README.md`
- 我檢查時 `pump_system/` 主程式本體沒有未提交 diff；本輪沒有改程式碼。

### 可直接轉貼給下個 agent 的話
「請先讀 `HANDOFF.md` 和 `HANDOFF_NATIVE_STOP.md`。原生止損根因已查完並修成 `/fapi/v1/algoOrder`，且 2026-04-25 BNBUSDT controlled test 已實際收到 `STOP_ORDER_TRIGGERED` Telegram。PostgreSQL E2E 已確認 finalized / in-progress 分流正常。2026-04-25 06:58 的 `1/1 -> 0/0` 是外部 Android/AOS `BSBUSDT` 倉位收斂，不是本 bot `stop_*` tracker 漏報。若要再測實盤，請先確認沒有 `main.py manual-test-entry` 常駐程序，並用唯讀查詢確認 Binance 帳戶仍是 `0` 持倉 / `0` 一般單 / `0` algo 單。」

### 資源回報
- ⏱️ 任務耗時：本輪 controlled stop / PostgreSQL E2E / 06:58 調查與文件更新約 60 分鐘
- Tokens (估算)：IN 35k / OUT 10k
- 狀態：可交接，本輪指定驗證已完成
