## HANDOFF - BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM

更新時間：2026-04-26 05:08 +08:00

## 本輪補充 (2026-04-26 交接 commit)

### 本輪確認
- 使用者已確認「近120資料已補齊」。
- 當前共識下一步：先維持基線驗證，再進入 P1 `algo history fallback` 實作。

### 下一步執行順序（鎖定）
1. 跑 `tests/test_algo_fill_regression.py` 確認基線。
2. 實作 `BinanceClient.get_historical_algo_orders()`。
3. 在 `order_service` native stop reconcile 接入 history fallback。
4. 將 `test_reconcile_triggered_via_algo_history_fallback` 從 `xfail` 推進為 pass。

### 範圍約束
- 本 commit 僅交接紀錄，不修改交易邏輯、`.env`、Binance 帳戶/API、DB 歷史資料表。

### 一句話現況
- 原生止損正式路徑已改為 `/fapi/v1/algoOrder`，2026-04-25 BNBUSDT controlled stop test 已確認 `STOP_ORDER_TRIGGERED`。
- PostgreSQL finalized / in-progress 分流已完成驗證；目前最主要未完項是 algo history fallback。
- 2026-04-26 已完成 `HANDOFF.md` 熱區整理，完整舊內容已搬到 `HANDOFF_ARCHIVE.md`。

### 本次完成事項
- 建立 `HANDOFF_ARCHIVE.md`，完整保存整理前的 `HANDOFF.md` 全文。
- 將 `HANDOFF.md` 重寫為熱區摘要，移除重複段落與過期 metadata。
- 建立整理前快照：`/home/xiaohan/.copilot/session-state/98e3f459-54f5-4a55-a214-f6ba0bb9ca08/files/handoff-backups/HANDOFF.pre-archive.20260426-0500.md`

### 進行中 / 尚未完成
- [TODO] `tests/test_algo_fill_regression.py::test_reconcile_triggered_via_algo_history_fallback` 仍為 `xfail`。
- [TODO] 若實作 P1，需在 `pump_system/exchange/binance_client.py` 新增 `get_historical_algo_orders()`，並在 `pump_system/execution/order_service.py` 的 native stop reconcile 補上 algo history fallback。
- [SKIP] P2 open orders 統一接口屬未來防禦；目前 `PositionState.refresh()` 已正確同時查一般 open orders 與 algo open orders，不是當前 bug。

### 關鍵檔案清單
| 檔案路徑 | 用途說明 |
|---|---|
| `HANDOFF_ARCHIVE.md` | 2026-04-26 前完整交接歷史；整理前全文已封存 |
| `tests/test_algo_fill_regression.py` | algo fill fallback 的 xfail 測試與目標行為 |
| `pump_system/exchange/binance_client.py` | algo order 相關 API wrapper；P1 需補 historical algo query |
| `pump_system/execution/order_service.py` | native stop reconcile 與 `STOP_ORDER_TRIGGERED` 判定 |
| `pump_system/state/position_state.py` | 目前已正確同時查一般 open orders + algo open orders |
| `README.md` | 專案規格與 stop / data flow / Telegram / runbook 說明 |

### 注意事項 / 已知風險
- [RISK] 若 Binance child order 的 `clientOrderId` 不再對齊原始 `clientAlgoId`，目前流程會降級成 `STOP_ORDER_POSITION_CLOSED`；P1 即是針對此情境補強。
- [RISK] `BinanceClient.get_open_orders()` 目前不支援 `symbol` 參數；若之後做 P2，不可直接照舊 handoff 範例貼上。
- [SKIP] 本輪只整理文件與交接，未碰交易邏輯、`.env`、Binance/API、DB。

### 最近已確認基線
- 2026-04-25：`python -m pytest -q` -> `18 passed, 1 xfailed`
- 2026-04-25：BNBUSDT controlled stop test 成功，`MARKET BUY -> /fapi/v1/algoOrder STOP_MARKET -> native stop filled`
- 2026-04-25：PostgreSQL E2E 確認 in-progress 只留 CSV、finalized 1m/3m 才進 DB
- 2026-04-26：靜態核對確認 `PositionState.refresh()` 已同時查一般單與 algo 單，P2 不是當前 bug

### 下一步建議
1. 優先實作 P1 algo history fallback，移除 `xfail`，讓 stop fill 在 child order `clientOrderId` 改變時仍可準確確認。
2. 若要做 P2，先修正 `get_open_orders(symbol=...)` 設計，再補 README 的 unified open-orders 指引。
3. 繼續保留 `/fapi/v1/algoOrder` 與既有 `STOP_ORDER_TRIGGERED` Telegram 行為，不要回退舊路徑。

### 關鍵決策紀錄
- 原生 stop 的正式實作固定走 Binance `/fapi/v1/algoOrder`，不再回退 `/fapi/v1/order`。
- DB 僅保存 finalized bars；in-progress bars 固定留在 `data/inprogress_1m.csv` / `data/inprogress_3m.csv`。
- function test mode 仍只允許 `FUNCTION_TEST_SYMBOL` 真實下單，其餘 symbol 只做評估與通知。
- `HANDOFF_ARCHIVE.md` 現在是完整歷史冷區；`HANDOFF.md` 僅保留最新熱區摘要。

### 資源回報
- ⏱️ 任務耗時：估算 20 分鐘（文件整理 / 歸檔 / 熱區重寫）
- 🪙 Tokens (估算)：平台未提供
- 💰 狀態：成功

---

## 本輪 (2026-04-26) - Handoff 歸檔嚴格確認

### 確認結論
- 已靜態核對 `HANDOFF.md` / `HANDOFF_ARCHIVE.md` / pre-archive 快照 / P1 相關程式與測試；未跑 pytest、未連 Binance、未查 DB、未改交易邏輯與 `.env`。
- `HANDOFF.md` 追加本段前 55 行，追加後仍低於 100 行，符合熱區摘要用途；`HANDOFF_ARCHIVE.md` 目前 495 行，已建立且包含舊 handoff 主要內容。
- [RISK] `HANDOFF_ARCHIVE.md` 並非整理前快照的 byte-for-byte 原文附加：與 pre-archive 快照相比，多了幾個 Markdown code fence / whitespace 格式調整，舊內容語意大致保留，但嚴格來說不應描述為「完全原樣封存」。
- P1 狀態仍正確：`get_historical_algo_orders()` 尚未在 `BinanceClient` 實作，`test_reconcile_triggered_via_algo_history_fallback` 仍為 strict xfail。
- P2 判斷仍正確：目前 `PositionState.refresh()` 已同時查一般 open orders 與 algo open orders；`BinanceClient.get_open_orders()` 仍不支援 `symbol` 參數。
