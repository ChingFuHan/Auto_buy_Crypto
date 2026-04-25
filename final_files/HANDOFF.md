## HANDOFF - BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM

更新時間：2026-04-25 07:00 +08:00

### 一句話現況
- 核心架構已完成，原生止損已從舊的 `/fapi/v1/order` 修正為 `/fapi/v1/algoOrder`，主流程可跑。
- 2026-04-23 已完成真實 BTCUSDT function test，確認 `MARKET BUY -> STOP_MARKET algo order` 可成立，Telegram 已收到 `STOP_ORDER_SUCCESS` 與 `STOP_ORDER_POSITION_CLOSED`。
- 2026-04-25 重新核對後，單元測試為 `11 passed`，Binance 帳戶目前唯讀查詢為 `0` 非零持倉 / `0` 一般 open orders / `0` algo orders。
- 下一位 agent 不需要再追原生止損根因；請直接接著做「`STOP_ORDER_TRIGGERED` 實測」與「PostgreSQL 端到端驗證」。

### 本輪已重新確認的事實
- `pump_system/` 主程式沒有新的未提交程式碼 diff；目前 git dirty 主要集中在 `final_files/` 匯出物與筆記檔。
- `manual-test-entry` 常駐程序仍存在，檢查時命令列為：
  - `"C:\Users\User\Documents\Auto_buy_Crypto\.venv\Scripts\python.exe" main.py manual-test-entry`
- `logs/app.log` 顯示 2026-04-25 06:58:19 仍有 `positions=1 open_order_symbols=1`，到 06:58:49 已變為 `positions=0 open_order_symbols=0`。
- 我用唯讀 Binance 查詢再次確認後，當下帳戶狀態確實是：
  - `nonzero_positions=0`
  - `open_orders=0`
  - `open_algo_orders=0`
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
- 已補齊回歸測試：
  - native stop 走 algo endpoint
  - native stop trigger 通知
  - algo order 計入 position state
  - fallback stale state 清理

### 目前真正還沒完成的事
- [TODO] 尚未在最新通知版本上實際收到一次 `STOP_ORDER_TRIGGERED` Telegram。
- [TODO] 尚未做 PostgreSQL 端到端整合驗證。
- [TODO] 2026-04-25 06:58 這次 `1/1 -> 0/0` 狀態變化，`app.log` 沒看到新的 `STOP_ORDER_*` 記錄；需確認是人工外部收斂、交易所側事件缺失，還是本地通知監控仍有缺口。

### 下一位 agent 應先做什麼
1. 先確認舊的 `manual-test-entry` 常駐程序要不要保留。
2. 若要重跑功能測試，先做唯讀狀態檢查，確認帳戶仍然是 `0` 持倉 / `0` 一般單 / `0` algo 單。
3. 若要重新驗證 `STOP_ORDER_TRIGGERED`，建議先停止舊程序，再重跑 `manual-test-entry` 做一次可控 stop 觸發測試。
4. 接著做 PostgreSQL 端到端驗證，確認：
   - finalized 1m/3m 真的寫進既有表
   - in-progress bar 仍只留在本地 CSV
   - websocket / catch-up / flush loop 不會把未收盤 bar 寫進 DB
5. 驗證完成後同步更新 `HANDOFF.md`、`HANDOFF_NATIVE_STOP.md`、必要時更新 `README.md`。

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
- [RISK] 目前帳戶檢查雖然是乾淨的，但舊 `manual-test-entry` 程序仍在執行；若直接再開一個新程序，可能增加排查噪音。
- [RISK] Binance 把條件單與一般 open orders 分開查；若後續還有其他觀測模組只查 `/fapi/v1/openOrders`，仍會漏看 native stop。
- [RISK] 2026-04-25 這次持倉從 `1/1` 變成 `0/0` 沒伴隨新的 `STOP_ORDER_*` log，這一點還不能視為通知鏈路已完全驗證。
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
- 2026-04-23：真實 BTCUSDT 測試 `MARKET BUY` -> `POST /fapi/v1/algoOrder` 成功，`algoStatus=NEW`
- 2026-04-23：Telegram 已收到 `STOP_ORDER_SUCCESS`
- 2026-04-23：75 秒內未觸發 stop；人工平倉收斂後，Telegram 收到 `STOP_ORDER_POSITION_CLOSED`
- 2026-04-25：唯讀 Binance 查詢確認 `0` 非零持倉 / `0` 一般 open orders / `0` algo orders

### 目前工作樹狀態
- `git status` 當下 dirty 項目如下：
  - `M final_files/MANIFEST.txt`
  - `D final_files/env_example.env`
  - `M final_files/main.py`
  - `D solve_99/README.md`
  - `?? .claude/`
  - `?? Fix Leverage Bracket Error.txt`
  - `?? final_files/HANDOFF_NATIVE_STOP.md`
  - `?? final_files/solve_99_README.md`
- 我檢查時 `pump_system/` 主程式本體沒有未提交 diff。

### 可直接轉貼給下個 agent 的話
「請先讀 `HANDOFF.md` 和 `HANDOFF_NATIVE_STOP.md`。原生止損根因已查完並修成 `/fapi/v1/algoOrder`，不用重查舊 bug。先確認是否仍有舊的 `main.py manual-test-entry` 常駐程序，再用唯讀查詢確認 Binance 帳戶是不是 `0` 持倉 / `0` 一般單 / `0` algo 單。接著直接做兩件事：1. 補一次能真正收到 `STOP_ORDER_TRIGGERED` Telegram 的 controlled test；2. 做 PostgreSQL 端到端驗證，確認 finalized / in-progress 分流沒有破。另請查清楚 2026-04-25 06:58 那次 `1/1 -> 0/0` 為什麼沒有新的 `STOP_ORDER_*` log。」 

### 資源回報
- ⏱️ 任務耗時：本輪 handoff 核對與文件更新約 40 分鐘
- Tokens (估算)：IN 20k / OUT 8k
- 狀態：可交接，待下一位 agent 直接接續驗證
