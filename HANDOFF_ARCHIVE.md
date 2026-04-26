# HANDOFF_ARCHIVE

## Archive snapshot — 2026-04-26 05:00 +08:00
- Source: `HANDOFF.md`
- Reason: hot handoff exceeded recommended size; full prior content archived before rebuilding the hot zone.
- Pre-archive snapshot: `/home/xiaohan/.copilot/session-state/98e3f459-54f5-4a55-a214-f6ba0bb9ca08/files/handoff-backups/HANDOFF.pre-archive.20260426-0500.md`

---

## HANDOFF - BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM

更新時間：2026-04-25 13:36 +08:00

### 一句話現況
- 核心架構已完成，原生止損已從舊的 `/fapi/v1/order` 修正為 `/fapi/v1/algoOrder`，主流程可跑。
- 2026-04-25 已完成真實 BNBUSDT controlled stop test，確認 `MARKET BUY -> STOP_MARKET algo order -> native stop fill`，Telegram 已收到 `STOP_ORDER_TRIGGERED`。
- 2026-04-25 已完成 PostgreSQL 端到端分流驗證，確認 in-progress 只進本地 CSV，finalized 1m/3m 進既有 DB 表。
- 2026-04-25（本輪）新增 `tests/test_algo_fill_regression.py`，覆蓋 algo order fill detection 欄位回歸保護，全套測試 `18 passed, 1 xfailed`。

### 本輪 (2026-04-25 10:54~11:00) 執行摘要
- 新增 `tests/test_algo_fill_regression.py`（8 個 tests：7 passed + 1 xfail）
- 驗證 Binance 帳戶：0 持倉 / 0 open orders / 0 algo orders ✅
- 驗證 DB + Telegram：正常 ✅
- 模擬模式測試：rate limit 正常觸發與重試，system 行為符合預期 ✅
- 當前配置已準備好實盤功能測試（`.env` ENABLE_LIVE_TRADING=true）
- 完整執行清單已文件化在「BTCUSDT 實盤功能測試指引」

### 已完成事項
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

### 本輪 (2026-04-25 10:xx) 新增
- 新增 `tests/test_algo_fill_regression.py`（8 個 tests：7 passed + 1 xfail）：
  - `test_restore_watchlist_extracts_all_algo_response_fields`：覆蓋 `clientAlgoId / algoId / orderType / positionSide / triggerPrice / workingType` 全部欄位名稱
  - `test_restore_watchlist_skips_orders_with_wrong_type_side_or_prefix`：驗證 filter 邏輯（distractor orders）
  - `test_reconcile_fill_extracts_order_id_executedqty_avgprice`：覆蓋 `clientOrderId / orderId / executedQty / avgPrice` 欄位，含 distractor 對比
  - `test_reconcile_fill_falls_back_to_tracker_qty_when_executedqty_absent`：executedQty 缺席時 fallback 到 tracker.quantity
  - `test_reconcile_continues_when_position_open_and_algo_present`：race condition guard
  - `test_reconcile_stop_missing_emits_error_and_deduplicates`：missing_reported dedupe
  - `test_reconcile_position_closed_when_clientorderid_mismatch__known_gap`：characterisation test，記錄現有降級行為
  - `test_reconcile_triggered_via_algo_history_fallback`：**[xfail]** 文件化 algo history fallback 的目標行為（實作後移除 xfail）
- 全套測試驗證：`18 passed, 1 xfailed`

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
- 暫無本輪 blocker。
- **algo history fallback（xfail 已標記）**：`tests/test_algo_fill_regression.py::test_reconcile_triggered_via_algo_history_fallback` 標為 `xfail`，記錄當 Binance child order clientOrderId 不等於 clientAlgoId 時，應使用 `GET /fapi/v1/algoOrders` 的 `actualOrderId / actualQty / actualPrice` 進行 fallback 判斷。實作時移除 `xfail` 即可。

### 本輪 (2026-04-25 11:00) 新增
- 新增 3 個獨立執行腳本（Linux bash），已驗證語法與帳戶狀態：
  1. **`test_btcusdt_entry.sh`** — 前置檢查 → 下單 + 自動掛止損 → 驗證持倉與止損單（完整自動化流程）
  2. **`check_btcusdt_status.sh`** — 查詢當前 BTCUSDT 持倉 / open orders / algo orders 狀態（隨時查詢）
  3. **`close_btcusdt_position.sh`** — 市價平倉（用於清理或快速結束測試）
- 驗證帳戶狀態：0 持倉 / 0 open orders / 0 algo orders ✅
- 所有腳本已設置可執行權限，可直接運行

### 下一位 agent 應先做什麼
1. **BTCUSDT 實盤功能測試執行清單已準備** — 見下方 `BTCUSDT 實盤功能測試指引` 及獨立執行腳本
2. 用戶可直接執行 `bash test_btcusdt_entry.sh` 開始測試
3. 若要長時間跑主程式，先確認使用者是否允許 live production mode 繼續交易。
4. 若要改 native stop monitor，保留目前已實測成功的 `/fapi/v1/algoOrder` 路徑與 `STOP_ORDER_TRIGGERED` Telegram 行為。

### BTCUSDT 實盤功能測試指引

**前置條件**（已驗證 ✅）：
- 帳戶狀態：0 非零持倉 / 0 open orders / 0 algo orders
- DB 連線：OK（validate 已完成）
- 時間同步：OK（offset_ms=33）
- Telegram：OK（通知已收到）
- 當前配置：`TESTNET=false`, `ENABLE_LIVE_TRADING=true`, `FUNCTION_TEST_MODE=true`, `FUNCTION_TEST_SYMBOL=BTCUSDT`

**執行選項**：

#### 選項 A — 完整自動化測試（推薦 ✨）
```bash
cd /media/sf_agent_sanbox_vm/Auto_buy_Crypto
bash test_btcusdt_entry.sh
```
流程：
1. 前置檢查帳戶清潔
2. 執行市價買入 + 自動掛止損
3. 驗證持倉 + 止損單
4. 提示後續操作選項

#### 選項 B — 分步執行
```bash
# Step 1: 查詢帳戶狀態
bash check_btcusdt_status.sh

# Step 2: 手動觸發下單 + 掛止損
cd /media/sf_agent_sanbox_vm/Auto_buy_Crypto && python3 main.py manual-test-entry

# Step 3: 驗證結果
bash check_btcusdt_status.sh
```

#### 選項 C — 模擬模式測試（無真實下單）
```bash
cd /media/sf_agent_sanbox_vm/Auto_buy_Crypto
sed -i 's/ENABLE_LIVE_TRADING=true/ENABLE_LIVE_TRADING=false/' .env
python3 main.py manual-test-entry
sed -i 's/ENABLE_LIVE_TRADING=false/ENABLE_LIVE_TRADING=true/' .env
```

#### 選項 D — 等待止損自動觸發（帶監控）
```bash
cd /media/sf_agent_sanbox_vm/Auto_buy_Crypto
python3 main.py run
# Ctrl+C 停止監控
```

#### 選項 E — 平倉/清理
```bash
cd /media/sf_agent_sanbox_vm/Auto_buy_Crypto
bash close_btcusdt_position.sh
```

**預期 Telegram 通知**：
| 階段 | 通知類型 |
|---|---|
| 下單 | `ENTRY_ORDER_SUCCESS` - BUY LONG 0.003 BTCUSDT |
| 掛止損 | `STOP_ORDER_SUCCESS` - 原生 algo order 已建立 |
| 止損觸發 | `STOP_ORDER_TRIGGERED` - 止損單已成交 |
| 平倉（如適用） | `STOP_ORDER_POSITION_CLOSED` - 持倉已關閉 |

**異常處理**：
| 情況 | 對應操作 |
|---|---|
| `ENTRY_ORDER_FAILED` | 檢查帳戶保證金 / 槓桿 / 手續費 |
| `STOP_ORDER_MISSING` | 原生 algo 建立失敗，fallback CSV 已激活 |
| `[BLOCKED] native stop missing` | 手動介入，查詢 logs/app.log |
| `BINANCE_API_RETRY / 429` | 暫時等待，會自動重試（rate limit） |

**快速查詢命令**：
```bash
# 監控日誌（實時）
tail -f /media/sf_agent_sanbox_vm/Auto_buy_Crypto/logs/app.log | grep -E 'STOP|TRIGGER|ENTRY|BTCUSDT'

# 檢查當前單狀態
bash /media/sf_agent_sanbox_vm/Auto_buy_Crypto/check_btcusdt_status.sh
```

### 建議的第一批命令
```python
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
```

```powershell
# 4. 若決定重跑功能測試
.\.venv\Scripts\python main.py manual-test-entry

# 5. 若要做 DB / wiring 驗證
.\.venv\Scripts\python main.py validate
.\.venv\Scripts\python main.py backfill
```

### 關鍵檔案清單
| 檔案路徑 | 用途說明 |
|---|---|
| `tests/test_algo_fill_regression.py` | algo fill detection regression tests（8 個，含 xfail algo history fallback）|
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

**當前 PositionState 已正確處理，以下風險為「未來防禦」考量**

- [RISK] Binance 把條件單 (`/fapi/v1/openAlgoOrders`) 與一般 open orders (`/fapi/v1/openOrders`) 分開查詢。當前 `PositionState.refresh()` 已同時查詢兩者 (L43-54)。若**未來新增模組繞過 PositionState、直接呼叫 `exchange_client.get_open_orders()`**，會漏看 native stop。防禦措施見下方「改進計畫」[P2]。

- [RISK] 若 Binance 未來改變 algo trigger 後 child order 的 `clientOrderId` 對應方式（當前 Binance 有時生成系統 `clientOrderId` ≠ 原始 `clientAlgoId`），目前 `_find_order_by_client_id()` 會返回 None，降級到 `STOP_ORDER_POSITION_CLOSED` 警告。應實作 `GET /fapi/v1/algoOrders` 的 `actualOrderId` / `actualQty` / `actualPrice` 欄位進行 fallback 判斷。防禦措施見下方「改進計畫」[P1]。

- [ASSUMPTION] 2026-04-23 官方文件定義的 `New Algo Order` 即為 task.md 所說的 `STOP_MARKET` 當前等價實作。

### 關鍵決策紀錄
- 3m 正式資料來源維持 Binance 原生 3m，不改成本地聚合。
- DB 僅存 finalized bars；in-progress bars 固定留在 `data/inprogress_1m.csv` / `data/inprogress_3m.csv`。
- `db_util.py` 仍直接重用 pool / env naming / fetch helpers；bulk insert 仍由 repository adapter 補齊。
- function test mode 不依賴 `SYMBOL_WHITELIST`，而是由 `SymbolRegistry.should_evaluate()` 額外納入 `FUNCTION_TEST_SYMBOL`。
- Telegram 採 queue worker，避免通知失敗拖垮交易主流程。
- Binance 原生 stop 的正式實作改採 `/fapi/v1/algoOrder`，不再嘗試 `STOP_LOSS_LIMIT`。
- [EXCEPTION] 依使用者要求採一次性交付完整專案，未走分階段 MVP；其餘 `god_rule.md` 規則維持遵守。預計恢復時間：下一輪功能擴充時回到迭代式交付。

---

## 本輪 (2026-04-26 04:38) - 改進計畫確認

### 核心改進計畫（按優先級排序）

#### [P1] Algo History Fallback — 最高優先級 ⚡
**目的**: 當 Binance child order `clientOrderId` ≠ 原始 `clientAlgoId` 時，能準確 confirm fill

**當前狀態**:
- `test_reconcile_triggered_via_algo_history_fallback` 已 xfail (tests/test_algo_fill_regression.py L415-466)
- `_FakeExchange.get_historical_algo_orders()` 已有測試佔位 (L62-69)
- `BinanceClient` 缺少 `get_historical_algo_orders()` 實作

**實作步驟**:
1. 在 `pump_system/exchange/binance_client.py` 新增:
   ```python
   async def get_historical_algo_orders(
       self, symbol: str | None = None, algo_type: str | None = None, limit: int = 50
   ) -> list[dict]:
       """Query /fapi/v1/algoOrders to retrieve past algo orders for fallback reconciliation."""
   ```
2. 修改 `pump_system/execution/order_service.py::reconcile_native_stops()`:
   - 當 `_find_order_by_client_id()` 返回 None 時
   - 查詢 `get_historical_algo_orders(symbol, "CONDITIONAL", limit=50)`
   - 按 `clientAlgoId` 匹配並提取 `actualOrderId / actualQty / actualPrice`
   - 驗證 qty 與 tracker.quantity 相符，發送 `STOP_ORDER_TRIGGERED` (confirmed)
3. 移除 xfail 標籤，驗證: `18 passed, 0 xfailed`

**代碼位置**: `pump_system/exchange/binance_client.py` + `pump_system/execution/order_service.py`
**估計工作量**: 1-2 小時
**依賴**: 無 (完全新增)
**風險**: 低（已有測試樁，邏輯独立）

---

#### [P2] Open Orders 統一接口 — 中等優先級 🛡️
**目的**: 防止未來新模組繞過 PositionState、直接調 `get_open_orders()` 而漏看 algo orders

**當前狀態**:
- `PositionState.refresh()` 已正確同時查詢 open orders + algo orders (position_state.py L43-54)
- 未來新模組若直接調 `BinanceClient.get_open_orders()` 會漏看 native stop

**實作步驟**:
1. 在 `pump_system/state/position_state.py` 新增:
   ```python
   async def get_all_open_orders_for_symbol(self, symbol: str) -> list[dict]:
       """Unified getter: returns BOTH regular + algo conditional orders for a symbol."""
       regular = await self.exchange_client.get_open_orders(symbol=symbol)
       algo = await self.exchange_client.get_open_algo_orders(symbol=symbol, algo_type="CONDITIONAL")
       return regular + algo
   ```
2. 在 README.md 新增「Open Orders Query 最佳實踐」章節，強制所有代碼使用此接口
3. 執行 `grep -r "get_open_orders" pump_system/` 確保沒有直接呼叫（除了 PositionState 內部）

**代碼位置**: `pump_system/state/position_state.py` + README.md
**估計工作量**: 45 分鐘
**依賴**: 無
**風險**: 低（純防禦性、不改邏輯）

---

#### [P3] 3m 聚合配置化 — 低優先級（可選）⏸️
**目的**: 未來可切換 3m 資料來源（當前固定 Binance 原生 3m）

**當前狀態**: 固定使用 Binance 原生 3m，無配置

**建議**: **暫不實作** (無明確需求，符合 `god_rule.md` MVP First)

若將來要改，方向如下:
1. 新增 `config.KLINE_AGGREGATION_MODE = "NATIVE"` (可改為 "AGGREGATE_1M")
2. 在 `pump_system/market_data/kline_source.py` 抽象層隔離選擇邏輯
3. 補完 1m 聚合 3m 的測試與性能驗證

**代碼位置**: config.py + pump_system/market_data/
**估計工作量**: 2-3 小時
**依賴**: 無
**優先級調整**: 暫不做

---

### 行動方案

| 優先級 | 項目 | 狀態 | 預計耗時 |
|---|---|---|---|
| **[P1]** | Algo history fallback | Ready to implement | 1-2h |
| **[P2]** | Open orders 統一接口 | Ready to implement | 45min |
| **[P3]** | 3m 聚合配置化 | Hold (no requirement) | 2-3h |

---

### [METADATA] 文件健康檢查

- ⚠️ **HANDOFF.md 超長**: 當前 ~370 行（建議 100 行內）
  - 需將舊版歷史段落搬遷至 `HANDOFF_ARCHIVE.md`
  - 優先級: P2 (非阻塞，可下輪處理)

### 驗證紀錄
- 2026-04-25（本輪）：`python -m pytest -q` -> `18 passed, 1 xfailed`
- 2026-04-25（本輪）：`python -m pytest -q` -> `18 passed, 1 xfailed` ✅
- 2026-04-25（本輪）：帳戶唯讀查詢 -> `0 持倉 / 0 open orders / 0 algo orders` ✅
- 2026-04-25（本輪）：模擬模式啟動測試 -> rate limit 正常，system 穩定 ✅
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

---

## 本輪 (2026-04-25 14:xx) - 修復 Backfill Rate Limit 處理

### 問題
- 用戶在 Windows 上執行 `python3 main.py backfill` 遇到 Binance API rate limit (429)
- 程序會在達到速率限制後退出失敗，無法自動恢復並繼續抓取 120 天完整數據

### 根因
- `BinanceClient._request()` 中的 `rate_limit_wait_until` 是**局部變數**
- 每次 request 呼叫後該變數消失，無法跨請求持久化
- 當 backfill 發送多個並行請求時，第一個請求觸發 429，但第二個請求不知道要等待，仍直接發送

### 解決方案
1. **新增實例變數**: `self.rate_limit_wait_until_ms = 0.0` 在 `BinanceClient.__init__()` ← 持久化狀態
2. **修改 `_request()` 邏輯**:
   - 請求前檢查全局速率限制窗口
   - 若在等待窗口內，先睡眠等待
   - 若觸發 429，設置 `self.rate_limit_wait_until_ms = now_ms + 60_000`
   - 所有後續請求都會檢查並尊重這個全局窗口

### 改動檔案
- `pump_system/exchange/binance_client.py` ✅
  - `__init__()`: 新增 `self.rate_limit_wait_until_ms = 0.0`
  - `_request()`: 重新實現速率限制檢查邏輯，改用實例變數而非局部變數

### 新增檔案
- `BACKFILL_RATE_LIMIT_GUIDE.md` ✅ - 詳細使用指引

### 驗證
- 全部測試通過: `18 passed, 1 xfailed` ✅
- 速率限制持久化測試: ✅
  - 驗證 `rate_limit_wait_until_ms` 初始化為 0
  - 驗證設置後能跨請求保存
  - 驗證等待窗口過期後自動釋放

### 預期行為 (Backfill 執行流程)
```text
python3 main.py backfill
  ↓
開始抓取 ~528 個 symbol × 2 intervals (1m, 3m)
  ↓
可能在某次請求觸發 429 rate limit
  ↓
自動設置 60 秒等待窗口
  ↓
所有並行請求在等待窗口內暫停
  ↓
60+ 秒後自動恢復繼續抓取
  ↓
重複直到 120 天完整數據抓完
  ↓
完成
```

### 配置說明
- `BACKFILL_CONCURRENCY=5` (預設) - 若速率限制頻繁可改小
- `BACKFILL_DAYS=120` - 保持不變（約 4 個月數據）
- `BACKFILL_LIMIT=1000` - Binance API 最大值，勿改

### 使用指令

**Linux (VM 中)**:
```bash
cd /media/sf_agent_sanbox_vm/Auto_buy_Crypto
source .venv/bin/activate
python3 main.py backfill
```

**Windows (Host, 共用資料夾)**:
```powershell
.\.venv\Scripts\python.exe main.py backfill
```

程序會自動：
- 檢測 rate limit
- 等待 ~60 秒至下一分鐘
- 繼續抓取
- 直到全部 120 天數據完成

### 監控
```bash
tail -f logs/app.log | grep -E "backfill|rate limit|429"
```

### 下次 Agent 要點
- 若需修改 backfill 邏輯，保持 `rate_limit_wait_until_ms` 實例變數不變
- 若速率限制仍頻繁，改低 `BACKFILL_CONCURRENCY`
- 詳見 `BACKFILL_RATE_LIMIT_GUIDE.md` 完整指引

---

## 本輪 (2026-04-26) - 前 Agent 匯報嚴格確認

### 確認結論
- 已讀 `god_rule.md` / `AGENTS.md` / `README.md` / `HANDOFF.md`，並以最小範圍核對 `position_state.py` / `binance_client.py` / `order_service.py` / `tests/test_algo_fill_regression.py`。
- 前 agent 關於核心事實大致正確：`/fapi/v1/algoOrder` 已存在、`rate_limit_wait_until_ms` 已是 `BinanceClient` 實例變數、`PositionState.refresh()` 已同時查一般 open orders 與 algo open orders、algo history fallback 測試目前仍為 xfail。
- [RISK] `HANDOFF.md` 現為 460+ 行，且根目錄目前沒有 `HANDOFF_ARCHIVE.md`；前 agent 只標記超長，尚未完成 RULE 01 要求的熱區轉冷區雙檔整理。
- [RISK] P2 改進計畫中的範例 `self.exchange_client.get_open_orders(symbol=symbol)` 與當前 `BinanceClient.get_open_orders()` 簽名不相容；若實作 P2，需先調整 client 方法支援 symbol 參數，或由統一接口自行過濾全部 open orders。
- [SKIP] 本次沒有跑 pytest、沒有連 Binance、沒有查 DB、沒有修改交易邏輯與 `.env`；僅做文件與程式靜態核對。

### 補充驗證 (2026-04-26 後續) — Opus 4.7 二次審查
- ✅ 確認 Codex 的所有靜態核對結論為真：核對檔案 `binance_client.py:46,139,176,191` / `position_state.py:43-54` / `tests/test_algo_fill_regression.py:415-466` 全部對應。
- ✅ 確認 `get_open_orders()` 目前僅由 `position_state.py:44` 呼叫；專案內無其他模組繞過 PositionState。P2 屬「未來防禦」，與當前實作沒有 bug。
- ✅ 確認 xfail 測試使用 `strict=True`：實作 P1 後必須移除 `@pytest.mark.xfail` 裝飾器，不可僅靠測試 pass（strict 模式下會報 XPASS = failed）。
- [RISK] HANDOFF.md L329 內部 metadata 仍寫 `當前 ~370 行`，與實際 470 行不一致；前次審查未同步刷新此值。
- [RISK] 文件結構問題前次審查未標記：`### 已完成事項` 重複出現於 L19 與 L55；`## 本輪 2026-04-26 04:38` (L238) 與 `## 本輪 2026-04-25 14:xx` (L373) 順序顛倒；本段 `## 本輪 (2026-04-26)` (L463) 與 L238 同日卻分立兩段。整體建議於下次「歷史搬遷」一併處理。
- [TODO] Codex 上輪 HANDOFF 段落缺 RULE 02 資源回報；本次補上於下方。
- [SKIP] 同前次：未跑 pytest、未連 Binance、未碰 DB、未改交易邏輯與 `.env`。

### 資源回報 (Opus 4.7 二次審查)
- ⏱️ 任務耗時：約 8 分鐘（純靜態審查）
- 🪙 Tokens (估算)：IN ~25k / OUT ~3k
- 💰 狀態：成功，無越界執行
