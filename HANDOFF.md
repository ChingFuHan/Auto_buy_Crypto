## HANDOFF - BINANCE_SMALLCAP_FIRST_PUMP_ENTRY_STOP_SYSTEM

更新時間：2026-04-28

## 接手必讀 / Active Watch Items

- 2026-04-28 11:31 +08:00：新增 **Always-Sync 持續時間同步服務**（`pump_system/sync/time_sync_manager.py`）。`main.py run` 執行期間無需停止，TimeSyncManager 會每 60 秒自動檢查並同步時間。三層監控：HEALTHY (≤3s 靜默) / WARNING (3-8s 每 5 次通知) / CRITICAL (>8s 立即通知)。詳見 `ALWAYS_SYNC_TIME.md`。整合測試通過（36 passed 1 xfailed）。
- 2026-04-28 11:27 +08:00：新增時間同步診斷工具 `time_sync_diagnostic.py`。之前使用者回報 `SERVER_TIME_OFFSET_BLOCKED (offset_ms: 101933)`，經診斷現已恢復正常（offset: +23 ms）。詳見 `TIME_SYNC_TROUBLESHOOT.md`；若再次發生類似問題，執行 `python3 time_sync_diagnostic.py --repeat 3` 快速診斷。
- `DAMUSDT` near-miss 案例已確認不是候選池漏單，也不是交易所規格問題；2026-04-27 log 有 74 筆 `signal check symbol=DAMUSDT`，`triggered=True` 為 0。
- 它沒進場的原因是主策略偏抓「第一段爆發」：`vol_ratio_3m`、`ret_3m_pct`、`range_3m_pct` 未同時達標；雖有 7 次 `breakout_3m=True`，但仍被成交量、推動幅度與壓縮條件擋下。
- 後續不要直接放寬正式盤主策略門檻。若使用者要改善這類「後面續漲但沒有第一段爆發特徵」的走勢，優先做 `near-miss` 記錄/回測，再評估是否新增第二套小倉位趨勢延續策略。
- 若 `HANDOFF.md` 未來要瘦身，這段必須保留在熱區；完整細節見本檔尾端 `DAMUSDT 未進場原因調查`。
- 2026-04-28 04:19-04:40 +08:00：已用既有 `BinanceClient + SymbolRegistry + BackfillService + KlineRepository` 做一次性 `15m` 回補，寫入 `public.semi_auto_price_future_15m`，固定近 120 天、只寫 finalized bar、`ON CONFLICT (code, da) DO NOTHING`；結果為 `535` 個 USDT perpetual symbol、`6,003,323` 筆、全數最新 `max_da=2026-04-27 20:00:00`，最早全域 `min_da=2025-12-28 20:30:00`，較少筆數的 symbol 為近期新上市合約（例如 `OPGUSDT` 僅 `499` 筆，起始於 `2026-04-22 15:30:00`），屬正常。執行 log：`logs/backfill_15m_20260428_041948.log`。
- 2026-04-28 04:51 +08:00：已完成正式主線週期可配置化，新增 `.env` 字串 `STRATEGY_INTERVAL=3m|15m`；切到 `15m` 時 REST backfill、WebSocket、DB seed、in-progress CSV、SignalEngine、OrderService manual/evaluation、DB finalized flush、fallback contract trigger 都會使用 `15m`。未修改實際 `.env`。
- 2026-04-28 04:59 +08:00：依使用者要求新增並改寫 `.env_template`，作為可自行複製修改的非機密中文詳細模板；預設安全模式 `TESTNET=true`、`ENABLE_LIVE_TRADING=false`、`FUNCTION_TEST_MODE=true`，並包含 `STRATEGY_INTERVAL=3m` / 可改 `15m`、小額固定名目與止損模式範例。未修改實際 `.env`。
- 2026-04-28 05:11 +08:00：已修正訊號門檻命名避免誤解。現在 `STRATEGY_INTERVAL=3m` 只讀 `SIGNAL_3M_*`，`STRATEGY_INTERVAL=15m` 只讀 `SIGNAL_15M_*`；兩組門檻彼此獨立，不再讓 15m 套用 3m 名稱。未修改實際 `.env`。
- 2026-04-28：已依使用者要求同步實際 `.env` 的訊號門檻區塊為 3m / 15m 獨立格式，並保留既有敏感與實盤設定；交接不記錄 `.env` 詳細值。
- 2026-04-28 05:19 +08:00：已依使用者要求將主策略預設週期調整為 15m；僅記錄方向，不記錄 `.env` 其他詳細值。
- 2026-04-28 05:21 +08:00：使用者準備在 Windows 執行 `main.py validate` 後接 `main.py run`；下一位 Agent 接手時先看使用者貼出的 validate/run 輸出，不要假設已成功啟動。
- 2026-04-28：新增 Telegram heartbeat 背景任務。`HEARTBEAT_ENABLED`（預設 `true`）、`HEARTBEAT_INTERVAL_SECONDS`（預設 `900`，最小 `60`）由 `.env` 控制；`pump_system/app.py:_heartbeat_loop` 在 `_start_background_tasks` 啟動後每隔 interval 送一次 INFO 等級 `HEARTBEAT`，帶 uptime / active_positions / strategy_interval / live_trading / testnet / data_symbols。INFO 等級走 `disable_notification=true`，手機通常靜音抵達；若 heartbeat 突然停止抵達，代表程式可能已崩潰。未修改實際 `.env`，defaults 即可工作。
- 2026-04-28 07:50 +08:00：驗證 15m run 無 `staging updated` / `finalized bar buffered` / `inprogress_15m.csv` 的原因；舊 URL `wss://fstream.binance.com/stream?streams=btcusdt@kline_15m` 連得上但 10 秒無資料，官方 routed endpoint `wss://fstream.binance.com/market/stream?streams=btcusdt@kline_15m` 可立即收到 kline。結論：優先修正/覆寫 USDⓈ-M Futures WebSocket base 為 `wss://fstream.binance.com/market`，不是先改 REST polling、換 VPS 或 VPN/proxy。未修改 `.env`、未啟動交易程式、未下單、未查/寫 DB。
- 2026-04-28 08:26 +08:00：已修正 `config.py` `ws_base_url` property：live 環境由 `wss://fstream.binance.com` → `wss://fstream.binance.com/market`；已清除 websocket_manager.py 的臨時 debug log；`compileall` + `pytest -q` 36 passed 1 xfailed 通過；VM 端實測確認新 URL 立即收到 kline 資料。
- 2026-04-28 07:56-07:59 +08:00：使用者依建議以 `BINANCE_WS_BASE_URL=wss://fstream.binance.com/market python3 main.py run` 啟動後，log 已確認 4 筆 `market entry success`，分別為 `C98USDT`、`WOOUSDT`、`BREVUSDT`、`ALCHUSDT`；每筆後面皆有 `native stop algo order placed` 與 `STOP_ORDER_SUCCESS`，代表程式目前仍會自動掛 native stop，不是只做紀錄。若要改成「只記錄、由使用者手動決定新止損點」，仍需另行調整交易邏輯。
- 2026-04-28 08:0x +08:00：再次確認 fallback stop 行為：原生 stop 失敗時，`FallbackStopRecord` 會保存原 stop_price / quantity / working_type / entry_price，之後由 `FallbackStopManager` 以固定 poll 週期觀測價格；若 `MARK_PRICE` 就查 mark price，否則用 staging 的 in-progress 價格；當 `current_price <= stop_price` 才會嘗試 `MARKET SELL`，不是把 stop 單重新掛回交易所。若倉位已被人手動平掉，會先辨識 `POSITION_ALREADY_CLOSED` 再移除，不會硬平。
- [RISK] `SIGNAL_15M_*` 已獨立，但目前預設值先與 3m 相同，尚未以 15m 回測/實盤觀察重新校準。正式盤切 15m 前至少跑 `main.py validate`，並用小額觀察。

## 本輪 (2026-04-27) - 進度查詢與 3m-only 改造

- 2026-04-27 03:06 +08:00：依使用者要求查看最新進度；僅讀取 `god_rule.md`、`HANDOFF.md`、`README.md`，未跑測試、未連 Binance、未查 DB、未修改交易邏輯或 `.env`。
- 2026-04-27 本輪補充：使用者貼上另一個 review session 的 A/B/D 選項並要求解釋；本輪讀取 `god_rule.md`、`README.md`、`HANDOFF.md`，並因 B 涉及 `final_files` 補讀 `final_file.md`；僅說明含義與風險，不修改交易邏輯、不跑測試、不連 Binance、不查 DB、不改 `.env`。
- 2026-04-27 本輪策略討論：[TENTATIVE] 使用者表示下一階段先改用 `3m` WebSocket 監控全 USDT 合約以降低複雜度、先求功能上線；本輪僅討論疑慮與策略使用方式，未修改交易程式、未跑測試、未連 Binance、未查 DB、不改 `.env`。
- 2026-04-27 本輪明確決策：使用者要求強制改為 `3m-only`；止損 low 來源同步改為當前 in-progress `3m` low；REST 429 retry 問題先不動、實盤觀察；接受 3m 追高較慢但較穩。
- 2026-04-27 本輪完成：已將正式主線改為 `3m-only`，包含 WebSocket 訂閱、backfill/catch-up、rolling staging、SignalEngine、OrderService manual/evaluation、fallback contract trigger、README 與 `tests/test_signal_engine.py`；未修改 `.env`、未連 Binance、未查/寫 DB、未動 REST 429 retry。
- 驗證：`python3 -m pytest -q` -> `18 passed, 1 xfailed`；`python3 -m compileall config.py main.py pump_system tests` -> pass。Linux 下 `.venv/Scripts/python.exe` 是 Windows PE，無法執行，故用系統 `python3` 做本地驗證。
- 2026-04-27 使用者要求提供 Windows 驗證指令與實盤親自驗證操作手冊；Agent 僅提供指令，不執行、不修改 `.env`、不連 Binance、不查/寫 DB。
- 2026-04-27 使用者回報 Windows PowerShell 驗證：`.venv\Scripts\python.exe --version` -> Python 3.11.9；`compileall` pass；`pytest -q` -> `18 passed, 1 xfailed`；`kline_1m` / `current_1m|finalized_1m|1m_` / `get_klines(symbol, "1m"` 搜尋皆無輸出，`kline_3m` 有輸出，確認 3m-only 主線已落地。
- 2026-04-27 使用者回報正式盤 dry-run：`.env` 為 `TESTNET=false`、`ENABLE_LIVE_TRADING=false`、`FUNCTION_TEST_MODE=true`、`FUNCTION_TEST_SYMBOL=BTCUSDT`；`main.py validate` 成功，載入 `data_symbols=535`、`candidate_symbols=528`、seeded rolling history `3m=47610`。`main.py backfill` 開始寫入 3m 增量，多數 symbol inserted=49；途中遇 Binance `/fapi/v1/klines` 429，既有邏輯進入 60 秒等待，尚未判定為失敗。
- 2026-04-27 使用者詢問 `STOP_WORKING_TYPE`、`TARGET_NOTIONAL_USDT`、`MAX_CONCURRENT_POSITIONS`、`STARTUP_BACKFILL_ENABLED` 建議值；Agent 僅提供建議，不修改 `.env`、不執行實盤、不連 Binance。
- [RISK] `god_rule.md` 要求任務完成時更新 `HANDOFF.md`；本專案「查詢進度」段落要求不要修改檔案。此處依上位規則做最小追加，僅保存查詢紀錄。
- 2026-04-27 03:06 +08:00 後續解釋 P1 步驟時，最小範圍讀取 `tests/test_algo_fill_regression.py`、`pump_system/exchange/binance_client.py`、`pump_system/execution/order_service.py`。
- [RISK] `tests/test_algo_fill_regression.py` 的 xfail reason 寫 `GET /fapi/v1/algoOrders`，但 Binance 官方 USDⓈ-M Futures 文件目前列的是 `GET /fapi/v1/algoOrder`（單筆）與 `GET /fapi/v1/allAlgoOrders`（全部）；另有 Algo Trading 產品文件的 `GET /sapi/v1/algo/futures/historicalOrders`，屬不同文件線。P1 實作前必須釐清正式 endpoint 與 response 欄位，不可盲貼測試註解。

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

## 本輪 (2026-04-27) - Handoff 遇到爆 context
 [2026-04-27 04:37:57,282] [INFO] [execution.order] signal check symbol=THETAUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.001728839211999714523754587942', 'range_3m_pct': '0.008442776735459662288930581614', 'vol_ratio_3m': '0.4344012084232175088401994986', 'ret_3m_pct': '-0.0004655493482309124767225325885',
  'prior_runup_3m_pct': '0.003266448903406439570695286981', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,318] [INFO] [app] staging updated symbol=SOONUSDT interval=3m
  [2026-04-27 04:37:57,319] [INFO] [execution.order] signal check symbol=SOONUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.0052504219845369976174380235', 'range_3m_pct': '0.03345925526173772261198057205', 'vol_ratio_3m': '0.3205692224015407523650727132', 'ret_3m_pct': '-0.003727369542066027689030883919',
  'prior_runup_3m_pct': '0.01173333333333333333333333333', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,339] [INFO] [app] staging updated symbol=SPKUSDT interval=3m
  [2026-04-27 04:37:57,339] [INFO] [execution.order] signal check symbol=SPKUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.003124468830951487391091801051', 'range_3m_pct': '0.01352785145888594164456233422', 'vol_ratio_3m': '0.2985705522553241923420039816', 'ret_3m_pct': '-0.0007936507936507936507936507937',
  'prior_runup_3m_pct': '0.008474576271186440677966101695', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,352] [INFO] [app] staging updated symbol=SLPUSDT interval=3m
  [2026-04-27 04:37:57,352] [INFO] [execution.order] signal check symbol=SLPUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002937875020769375763324694189', 'range_3m_pct': '0.01937282229965156794425087108', 'vol_ratio_3m': '0.1207931955828651561712371627', 'ret_3m_pct': '-0.0006912760956726116410894511268',
  'prior_runup_3m_pct': '0.005281445448227936066712995136', 'recent_green_3m_bars': '2', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,352] [INFO] [app] staging updated symbol=ZBTUSDT interval=3m
  [2026-04-27 04:37:57,352] [INFO] [execution.order] signal check symbol=ZBTUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout,already_extended metrics={'mode':
  '3m_only', 'atr_3m_pct': '0.02062504237742849518531904769', 'range_3m_pct': '0.09532312925170068027210884354', 'vol_ratio_3m': '0.8003460257139032474727799845', 'ret_3m_pct':
  '0.004159387738124948007653273438', 'prior_runup_3m_pct': '0.04842687074829931972789115646', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,481] [INFO] [app] staging updated symbol=USUSDT interval=3m
  [2026-04-27 04:37:57,482] [INFO] [execution.order] signal check symbol=USUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002466212044035474542269447318', 'range_3m_pct': '0.01371774006045105789351313648', 'vol_ratio_3m': '0.3495803888069167249100463358', 'ret_3m_pct': '-0.001613646841862609497464269249',
  'prior_runup_3m_pct': '0.004847645429362880886426592798', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,538] [INFO] [app] staging updated symbol=SKYAIUSDT interval=3m
  [2026-04-27 04:37:57,539] [INFO] [execution.order] signal check symbol=SKYAIUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002666407490457371617132293542', 'range_3m_pct': '0.01310630069291507761723156255', 'vol_ratio_3m': '0.7897034469931703386891501055', 'ret_3m_pct': '-0.002129925452609158679446219382',
  'prior_runup_3m_pct': '0.004110174015159602861108145618', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,577] [INFO] [app] staging updated symbol=USDCUSDT interval=3m
  [2026-04-27 04:37:57,578] [INFO] [execution.order] signal check symbol=USDCUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.000001000820021885159478750268951', 'range_3m_pct': '0.000001000820672951820492804099361', 'vol_ratio_3m': '0.2788183666916408005993792144', 'ret_3m_pct': '0', 'prior_runup_3m_pct':
  '0.000001000820672951820492804099361', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,608] [INFO] [app] staging updated symbol=SOLUSDT interval=3m
  [2026-04-27 04:37:57,609] [INFO] [app] staging updated symbol=ZBTUSDT interval=3m
  [2026-04-27 04:37:57,609] [INFO] [execution.order] signal check symbol=ZBTUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout,already_extended metrics={'mode':
  '3m_only', 'atr_3m_pct': '0.02062504237742849518531904769', 'range_3m_pct': '0.09532312925170068027210884354', 'vol_ratio_3m': '0.8013171717540709228071278740', 'ret_3m_pct':
  '0.004492138757174943848265535313', 'prior_runup_3m_pct': '0.04842687074829931972789115646', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,641] [INFO] [app] staging updated symbol=ZILUSDT interval=3m
  [2026-04-27 04:37:57,641] [INFO] [execution.order] signal check symbol=ZILUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002878282578206849316277563154', 'range_3m_pct': '0.007211538461538461538461538462', 'vol_ratio_3m': '0.1662373846383533140563870289', 'ret_3m_pct': '0', 'prior_runup_3m_pct':
  '0.004807692307692307692307692308', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,648] [INFO] [app] staging updated symbol=TAOUSDT interval=3m
  [2026-04-27 04:37:57,650] [INFO] [execution.order] signal check symbol=TAOUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002114259907946179934065428200', 'range_3m_pct': '0.009314039015030380556443875919', 'vol_ratio_3m': '1.825194860171422692669115891', 'ret_3m_pct': '-0.002030335602531947927863370357',
  'prior_runup_3m_pct': '0.004196139551612516484833952763', 'recent_green_3m_bars': '3', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,656] [INFO] [app] staging updated symbol=ZECUSDT interval=3m
  [2026-04-27 04:37:57,656] [INFO] [execution.order] signal check symbol=ZECUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002710257699817798386467790478', 'range_3m_pct': '0.01534232743387653212913359325', 'vol_ratio_3m': '1.228931732431396931458051368', 'ret_3m_pct': '0.001167152980408503543142976240',
  'prior_runup_3m_pct': '0.01018557276405748569833961211', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,671] [INFO] [app] staging updated symbol=STOUSDT interval=3m
  [2026-04-27 04:37:57,672] [INFO] [execution.order] signal check symbol=STOUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only',
  'atr_3m_pct': '0.004743916714474239252096605917', 'range_3m_pct': '0.03988637708604568587998579714', 'vol_ratio_3m': '0.2118834030701181329449743307', 'ret_3m_pct': '-0.0003437213565536205316223648029',
  'prior_runup_3m_pct': '0.005288572085536905035640377098', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,807] [INFO] [app] staging updated symbol=STABLEUSDT interval=3m
  [2026-04-27 04:37:57,807] [INFO] [execution.order] signal check symbol=STABLEUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.00524704576725226848430468031', 'range_3m_pct': '0.02424600827912477823772915435', 'vol_ratio_3m': '0.6786451621630939045214354819', 'ret_3m_pct': '-0.002660360626662725391664203370',
  'prior_runup_3m_pct': '0.02424600827912477823772915435', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,820] [INFO] [app] staging updated symbol=XPLUSDT interval=3m
  [2026-04-27 04:37:57,820] [INFO] [execution.order] signal check symbol=XPLUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002734692014594367200524026220', 'range_3m_pct': '0.008991008991008991008991008991', 'vol_ratio_3m': '0.2099808215288020147245548971', 'ret_3m_pct': '-0.0009930486593843098311817279047',
  'prior_runup_3m_pct': '0.005976095617529880478087649402', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,859] [INFO] [app] staging updated symbol=ZBTUSDT interval=3m
  [2026-04-27 04:37:57,859] [INFO] [execution.order] signal check symbol=ZBTUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout,already_extended metrics={'mode':
  '3m_only', 'atr_3m_pct': '0.02062504237742849518531904769', 'range_3m_pct': '0.09532312925170068027210884354', 'vol_ratio_3m': '0.8026375523069801611935843233', 'ret_3m_pct':
  '0.004616920389318692288495133516', 'prior_runup_3m_pct': '0.04842687074829931972789115646', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,910] [INFO] [app] staging updated symbol=SPACEUSDT interval=3m
  [2026-04-27 04:37:57,910] [INFO] [execution.order] signal check symbol=SPACEUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only',
  'atr_3m_pct': '0.01035332471533064435826892542', 'range_3m_pct': '0.05794701986754966887417218543', 'vol_ratio_3m': '0.6248071000955163427583458635', 'ret_3m_pct': '-0.002908514013749338974087784241',
  'prior_runup_3m_pct': '0.01900332225913621262458471761', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:57,931] [INFO] [app] staging updated symbol=UBUSDT interval=3m
  [2026-04-27 04:37:57,931] [INFO] [execution.order] signal check symbol=UBUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only',
  'atr_3m_pct': '0.01532133149738378514049966226', 'range_3m_pct': '0.06798640271945610877824435113', 'vol_ratio_3m': '0.3865746778493327994259270825', 'ret_3m_pct': '0.001548586914440572977158343012',
  'prior_runup_3m_pct': '0.02049664958612534489554592038', 'recent_green_3m_bars': '2', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,059] [INFO] [app] staging updated symbol=SOLUSDT interval=3m
  [2026-04-27 04:37:58,110] [INFO] [app] staging updated symbol=VINEUSDT interval=3m
  [2026-04-27 04:37:58,110] [INFO] [execution.order] signal check symbol=VINEUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002075871269922844374300496144', 'range_3m_pct': '0.01282051282051282051282051282', 'vol_ratio_3m': '0.03860052562417871222076215506', 'ret_3m_pct': '-0.0006393861892583120204603580563',
  'prior_runup_3m_pct': '0.001920614596670934699103713188', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,122] [INFO] [app] staging updated symbol=TRADOORUSDT interval=3m
  [2026-04-27 04:37:58,123] [INFO] [execution.order] signal check symbol=TRADOORUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only',
  'atr_3m_pct': '0.007410226759688400672730985625', 'range_3m_pct': '0.05793450881612090680100755668', 'vol_ratio_3m': '0.6211209222586745713706107833', 'ret_3m_pct': '0.002389486260454002389486260454',
  'prior_runup_3m_pct': '0.02815177478580171358629130967', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,134] [INFO] [app] staging updated symbol=WLDUSDT interval=3m
  [2026-04-27 04:37:58,134] [INFO] [execution.order] signal check symbol=WLDUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.001543844045053831632272931047', 'range_3m_pct': '0.005415860735009671179883945841', 'vol_ratio_3m': '0.7664793309289844344144706461', 'ret_3m_pct': '-0.0007707129094412331406551059730',
  'prior_runup_3m_pct': '0.003862495171881035148706064117', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,160] [INFO] [cache.staging] staging csv flushed interval=3m rows=135
  [2026-04-27 04:37:58,171] [INFO] [app] staging updated symbol=ZBTUSDT interval=3m
  [2026-04-27 04:37:58,171] [INFO] [execution.order] signal check symbol=ZBTUSDT triggered=False reason=3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout,already_extended metrics={'mode':
  '3m_only', 'atr_3m_pct': '0.02062504237742849518531904769', 'range_3m_pct': '0.09532312925170068027210884354', 'vol_ratio_3m': '0.8038419151699326286337719615', 'ret_3m_pct':
  '0.004741702021462440728724731719', 'prior_runup_3m_pct': '0.04842687074829931972789115646', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,173] [INFO] [app] staging updated symbol=VVVUSDT interval=3m
  [2026-04-27 04:37:58,173] [INFO] [execution.order] signal check symbol=VVVUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002961579161924753220039140484', 'range_3m_pct': '0.008361558001693480101608806097', 'vol_ratio_3m': '0.5575503317012074576841742091', 'ret_3m_pct': '-0.0005275374551593163114581135261',
  'prior_runup_3m_pct': '0.008361558001693480101608806097', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,209] [INFO] [app] staging updated symbol=SUIUSDT interval=3m
  [2026-04-27 04:37:58,210] [INFO] [execution.order] signal check symbol=SUIUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.00105704604515521910516568182', 'range_3m_pct': '0.004765434713544424441385153023', 'vol_ratio_3m': '0.6601917347439124114721395681', 'ret_3m_pct': '-0.001266490765171503957783641161',
  'prior_runup_3m_pct': '0.003490216816499206768905341089', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,223] [INFO] [app] staging updated symbol=币安人生USDT interval=3m
  [2026-04-27 04:37:58,223] [INFO] [execution.order] signal check symbol=币安人生USDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.00521444544583858555905680873', 'range_3m_pct': '0.02671972711768050028425241615', 'vol_ratio_3m': '0.3416706492450048299354313895', 'ret_3m_pct': '-0.0009895951142275503279800950011',
  'prior_runup_3m_pct': '0.008953951108584422967595224559', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,231] [INFO] [app] staging updated symbol=TONUSDT interval=3m
  [2026-04-27 04:37:58,231] [INFO] [execution.order] signal check symbol=TONUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout,recent_green_stretch metrics={'mode': '3m_only',
  'atr_3m_pct': '0.001216616159334315490796683317', 'range_3m_pct': '0.01145801291910181482620732082', 'vol_ratio_3m': '1.673287709061275598913102514', 'ret_3m_pct': '0.0002283278788340056320876779055',
  'prior_runup_3m_pct': '0.005657924917807171802125544766', 'recent_green_3m_bars': '6', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,241] [INFO] [app] staging updated symbol=XANUSDT interval=3m
  [2026-04-27 04:37:58,241] [INFO] [execution.order] signal check symbol=XANUSDT triggered=False reason=3m_push_too_small metrics={'mode': '3m_only', 'atr_3m_pct': '0.002667729936844493425787988938',
  'range_3m_pct': '0.01197604790419161676646706587', 'vol_ratio_3m': '7.936979216006834399128228371', 'ret_3m_pct': '-0.005562130177514792899408284024', 'prior_runup_3m_pct':
  '0.01064465972969740461667264681', 'recent_green_3m_bars': '1', 'breakout_3m': 'True', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,282] [INFO] [app] staging updated symbol=XMRUSDT interval=3m
  [2026-04-27 04:37:58,282] [INFO] [execution.order] signal check symbol=XMRUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.001797374204459753042141610908', 'range_3m_pct': '0.006891622849558425647046811986', 'vol_ratio_3m': '0.3820215804506505871152015233', 'ret_3m_pct': '-0.0007617886798202178715624285823',
  'prior_runup_3m_pct': '0.004916571137434721691504266972', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,334] [INFO] [app] staging updated symbol=龙虾USDT interval=3m
  [2026-04-27 04:37:58,335] [INFO] [execution.order] signal check symbol=龙虾USDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002130853453094351513836082421', 'range_3m_pct': '0.004452054794520547945205479452', 'vol_ratio_3m': '1.300809747705777299704098212', 'ret_3m_pct': '-0.003412581048799908997838698669',
  'prior_runup_3m_pct': '0.003306727480045610034207525656', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,343] [INFO] [app] staging updated symbol=SOONUSDT interval=3m
  [2026-04-27 04:37:58,343] [INFO] [execution.order] signal check symbol=SOONUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.0052504219845369976174380235', 'range_3m_pct': '0.03345925526173772261198057205', 'vol_ratio_3m': '0.3215868798278542110628635287', 'ret_3m_pct': '-0.003194888178913738019169329073',
  'prior_runup_3m_pct': '0.01173333333333333333333333333', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,474] [INFO] [app] staging updated symbol=ZECUSDT interval=3m
  [2026-04-27 04:37:58,475] [INFO] [execution.order] signal check symbol=ZECUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002710257699817798386467790478', 'range_3m_pct': '0.01534232743387653212913359325', 'vol_ratio_3m': '1.232335100094479362429928295', 'ret_3m_pct': '0.001167152980408503543142976240',
  'prior_runup_3m_pct': '0.01018557276405748569833961211', 'recent_green_3m_bars': '0', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,490] [INFO] [app] staging updated symbol=VVVUSDT interval=3m
  [2026-04-27 04:37:58,491] [INFO] [execution.order] signal check symbol=VVVUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  '0.002961579161924753220039140484', 'range_3m_pct': '0.008361558001693480101608806097', 'vol_ratio_3m': '0.5577090619074758632751911576', 'ret_3m_pct': '-0.0004220299641274530491664908208',
  'prior_runup_3m_pct': '0.008361558001693480101608806097', 'recent_green_3m_bars': '1', 'breakout_3m': 'False', 'stop_source': 'in_progress_3m_low'}
  [2026-04-27 04:37:58,491] [INFO] [app] staging updated symbol=VIRTUALUSDT interval=3m
  [2026-04-27 04:37:58,492] [INFO] [execution.order] signal check symbol=VIRTUALUSDT triggered=False reason=3m_volume_too_low,3m_push_too_small,3m_not_breakout metrics={'mode': '3m_only', 'atr_3m_pct':
  [2026-04-27 04:37:58,550] [INFO] [app] staging updated symbol=SOLUSDT interval=3m
  Traceback (most recent call last):
    File "C:\Users\User\Documents\agent_sanbox_vm\Auto_buy_Crypto\main.py", line 40, in <module>
      main()
    File "C:\Users\User\Documents\agent_sanbox_vm\Auto_buy_Crypto\main.py", line 36, in main
      asyncio.run(app.run())
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\runners.py", line 190, in run
      return runner.run(main)
             ^^^^^^^^^^^^^^^^
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\runners.py", line 118, in run
      return self._loop.run_until_complete(task)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\base_events.py", line 641, in run_until_complete
      self.run_forever()
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\windows_events.py", line 321, in run_forever
      super().run_forever()
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\base_events.py", line 608, in run_forever
      self._run_once()
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\base_events.py", line 1898, in _run_once
      event_list = self._selector.select(timeout)
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\windows_events.py", line 444, in select
      self._poll(timeout)
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\windows_events.py", line 825, in _poll
      status = _overlapped.GetQueuedCompletionStatus(self._iocp, ms)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\asyncio\runners.py", line 157, in _on_sigint
      raise KeyboardInterrupt()
  KeyboardInterrupt
  PS C:\Users\User\Documents\agent_sanbox_vm\Auto_buy_Crypto>


■ Error running remote compact task: {
  "error": {
    "message": "Your input exceeds the context window of this model. Please adjust your input and try again.",
    "type": "invalid_request_error",
    "param": "input",
    "code": "context_length_exceeded"
  }
}


› commit


■ Error running remote compact task: {
  "error": {
    "message": "Your input exceeds the context window of this model. Please adjust your input and try again.",
    "type": "invalid_request_error",
    "param": "input",
    "code": "context_length_exceeded"
  }
}


› Find and fix a bug in @filename

  gpt-5.5 xhigh · /media/sf_agent_sanbox_vm/Auto_buy_Crypto

## 本輪 (2026-04-27) - commit 前整理

- 2026-04-27 04:50 +08:00：依使用者要求讀取 `AGENTS.md`、`god_rule.md`、`README.md`、`HANDOFF.md` 後進行 commit。
- 快照：commit 前 `HEAD=eebc4ccabe62676d8d3a7c8f91ee0ebe0bd93fda`。
- 本輪不修改交易邏輯、不修改 `.env`、不連 Binance、不查/寫 DB。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`python3 -m pytest -q` -> `18 passed, 1 xfailed`。
- [SKIP] 未納入 runtime 產物與高風險檔：`*.log`、`*.pid`、`*.out`、`backfill_pid.txt`、`backfill_completion_monitor.sh`（含硬寫 DB password）、會直接操作帳戶/修改 `.env` 的臨時 shell script。
- [RISK] `HANDOFF.md` 目前已超過熱區建議長度，且含上一輪 context 爆量紀錄；本輪為避免擴張 commit 任務，僅補最小交接紀錄，後續應另開任務將完整內容先附加到 `HANDOFF_ARCHIVE.md` 再整理熱區。

## 本輪 (2026-04-27) - 正式小額實盤啟動

- 使用者明確要求跳過 BTC dry-run，直接進正式小額實盤。
- 已確認 `.env` 非機密開關：`TESTNET=false`、`STOP_WORKING_TYPE=CONTRACT_PRICE`、`TARGET_NOTIONAL_USDT=50`、`MAX_CONCURRENT_POSITIONS=1`、`STARTUP_BACKFILL_ENABLED=false`、`ENABLE_LIVE_TRADING=true`、`FUNCTION_TEST_MODE=false`。
- 已確認 API / DB / Telegram 必要值存在但未輸出內容；未發現既有 `main.py run` 程序。
- [RISK] 這是正式盤真實下單模式，可能產生真實虧損；BTCUSDT 依預設 `EXCLUDED_BIG_CAPS` 排除，且 function test mode 關閉後不會被特別加入測試池。
- 啟動結果：第一次背景啟動 PID `11578` 未常駐；改用 `setsid nohup python3 main.py run` 後成功常駐，PID `11674`，stdout log：`logs/live_run_20260427_050208.log`。
- 2026-04-27 05:02 +08:00：正式實盤已觸發 `SFPUSDT` 真實進場，`MARKET BUY` 成交 `139 SFPUSDT`，成交均價 `0.3597`，名目 `49.9983 USDT`；已掛原生 `STOP_MARKET` algo stop，`triggerPrice=0.3571`，`workingType=CONTRACT_PRICE`，`algoId=4000001175410215`。
- 驗證：查詢 Binance position/open algo orders 顯示 `SFPUSDT` LONG 倉位仍存在，open algo stop 狀態 `NEW`，一般 open orders=0；程序 PID `11674` 仍在執行。
- 2026-04-27 05:04 +08:00：`SFPUSDT` 原生止損已觸發，log 顯示 `native stop filled` 與 Telegram `STOP_ORDER_TRIGGERED`；再次查詢 Binance 後 `SFPUSDT positionAmt=0`、open algo count=0。PID `11674` 仍在執行，會依 `MAX_CONCURRENT_POSITIONS=1` 繼續等待下一個符合條件的訊號。
- 2026-04-27 05:06 +08:00：使用者要求停止程式；已對 PID `11674` 發送 SIGTERM，確認 `python3 main.py run` 已停止，且未發現其他同類程序。未修改 `.env`、未刪除 log/pid 檔。
- 2026-04-27 後續需求：[TODO] 使用者表示後續只需要把止損來源改成可人工切換：`in-progress low` 或「名目持倉金額的 50% 風險距離」兩種選擇，方便日後隨時人工調整；本輪僅記錄需求，尚未修改交易邏輯。

## 本輪 (2026-04-27 05:18 +08:00) - 止損模式改為 .env 可調

- 完成：新增 `.env` 可調止損價模式，預設維持既有 `IN_PROGRESS_3M_LOW`；可切到 `NOTIONAL_RISK_PCT`，並用 `STOP_NOTIONAL_RISK_PCT=0.50` 表示做多止損價約為成交均價的 50%；若 Binance 市價單回傳 `avgPrice=0`，會退回訊號當下價格估算止損與通知 entry price。
- 修改檔案：`config.py`、`pump_system/execution/order_service.py`、`tests/test_order_service_stop.py`、`.env.example`、`README.md`、`HANDOFF.md`。
- [SKIP] 未修改實際 `.env`，未啟動程式，未連 Binance，未查/寫 DB。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`git diff --check -- .env.example README.md config.py pump_system/execution/order_service.py tests/test_order_service_stop.py` -> pass；`python3 -m pytest -q` -> `21 passed, 1 xfailed`。
- 注意：修改 `.env` 後必須重啟 `main.py run`，新止損模式才會生效。

## 本輪 (2026-04-27 05:34 +08:00) - 多幣資金分配模式

- 完成：新增 `POSITION_SIZING_MODE`，預設 `FIXED_NOTIONAL` 維持既有 `TARGET_NOTIONAL_USDT` 固定名目；新增 `BALANCE_SPLIT` 會用 `availableBalance * max_leverage / remaining_position_slots` 計算本次目標名目，適合 `MAX_CONCURRENT_POSITIONS=5` 時把可用保證金分配到最多 5 個幣。
- 修改檔案：`config.py`、`pump_system/execution/order_service.py`、`pump_system/app.py`、`tests/test_order_service_stop.py`、`.env.example`、`README.md`、`HANDOFF.md`。
- [SKIP] 未修改實際 `.env`，未啟動實盤程式，未連 Binance，未查/寫 DB；`main.py validate` 會 bootstrap 外部服務，本輪未執行。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`git diff --check -- .env.example README.md config.py pump_system/app.py pump_system/execution/order_service.py tests/test_order_service_stop.py` -> pass；`python3 -m pytest -q` -> `23 passed, 1 xfailed`；另用本地 `python3 -c` 驗證 `POSITION_SIZING_MODE=BALANCE_SPLIT MAX_CONCURRENT_POSITIONS=5` 與 `FIXED_NOTIONAL TARGET_NOTIONAL_USDT=50` 都能正確載入。
- 建議設定：若要最多 5 幣並盡量分配可用保證金，用 `POSITION_SIZING_MODE=BALANCE_SPLIT` + `MAX_CONCURRENT_POSITIONS=5`；此模式下 `TARGET_NOTIONAL_USDT` 不再決定每筆目標名目。

## 本輪 (2026-04-27 05:43 +08:00) - 使用者實盤 .env 設定確認

- 使用者回報 `.env` 已改為正式盤真下單：`TESTNET=false`、`ENABLE_LIVE_TRADING=true`、`FUNCTION_TEST_MODE=false`、`POSITION_SIZING_MODE=FIXED_NOTIONAL`、`TARGET_NOTIONAL_USDT=50`、`MAX_CONCURRENT_POSITIONS=5`。
- 使用者目前止損模式為 `STOP_PRICE_MODE=NOTIONAL_RISK_PCT`、`STOP_NOTIONAL_RISK_PCT=0.15`，代表做多止損價約為成交均價的 85%。
- [RISK] 使用者貼出的說明文字 `要切換時改成：` 若直接存在 `.env`，應加 `#` 註解，避免 dotenv 解析不一致。

## 本輪 (2026-04-27 05:50 +08:00) - 帳戶持倉唯讀觀察

- 使用者表示程式已開始執行，要求僅觀察帳戶持倉是否屬實。
- 完成：透過 Binance futures read-only 查詢確認正式盤目前有 5 個 LONG 持倉；`LIGHTUSDT`、`OPENUSDT`、`PIPPINUSDT`、`PROMUSDT` 有 open algo STOP_MARKET；`SFPUSDT` 有一般 open order STOP_MARKET，非 algo stop。
- 2026-04-27 05:51 +08:00：使用者確認 `SFPUSDT` stop 為人工設置，後續可忽略其 stop 來源差異；但若 `SFPUSDT` 仍有持倉，仍計入 `MAX_CONCURRENT_POSITIONS`。
- [SKIP] 未下單、未取消單、未改 `.env`、未停止程式、未查/寫 DB。

## 本輪 (2026-04-27 05:52 +08:00) - .env 最大持倉數確認

- 使用者要求直接讀取 `.env`，確認已改為最多 10 種幣。
- 完成：僅讀取非機密交易開關，確認 `.env` 目前為 `MAX_CONCURRENT_POSITIONS=10`、`POSITION_SIZING_MODE=FIXED_NOTIONAL`、`TARGET_NOTIONAL_USDT=50`、`STOP_PRICE_MODE=NOTIONAL_RISK_PCT`、`STOP_NOTIONAL_RISK_PCT=0.20`。
- 注意：若 `main.py run` 是修改 `.env` 前已啟動，需重啟後 `MAX_CONCURRENT_POSITIONS=10` 才會生效。

## 本輪 (2026-04-28 02:25 +08:00) - 10 倉設定與未增倉觀察

- 使用者表示已重新執行新 `.env`，但昨天至今看似只剩一開始的 3 種幣，詢問是否有問題。
- 完成：唯讀檢查 `.env`、log 與 Binance futures 持倉；確認 `MAX_CONCURRENT_POSITIONS=10` 已在 log 生效，且 `2026-04-27 06:09` 後有新進場 `USELESSUSDT`、`SNXUSDT`、`ZKCUSDT`。
- 目前交易所實際 open positions=3：`USELESSUSDT`、`SNXUSDT`、`ZKCUSDT`，三者皆有 algo STOP_MARKET；多數後續 signal check 為 `triggered=False`，常見原因為 `3m_volume_too_low`、`3m_push_too_small`、`3m_not_breakout`。
- 結論：不是 10 倉上限未生效；目前只剩 3 倉主要是策略條件未再觸發新單，且早先 `PIPPINUSDT`、`PROMUSDT`、`LIGHTUSDT`、`OPENUSDT` 已於 `2026-04-27 06:07` 左右平倉/止損。
- 2026-04-28 02:28 +08:00 補充：使用者確認 `2026-04-27 06:07` 左右那批歸零是為了重試而手動把倉位變 0，後續不可誤判為策略止損績效。
- [RISK] log 曾出現 Windows shared-folder staging CSV replace 權限錯誤 `[WinError 5]`，websocket 已自動 reconnect 並 catch-up；若頻繁出現可另行處理檔案鎖問題。

## 本輪 (2026-04-28 02:37 +08:00) - 使用者再次人工全平重啟

- 使用者表示會再次手動全部平倉，再重新啟動腳本。
- 注意：此輪人工全平應視為重試/重置操作，不可納入策略自然止損或績效判讀。

## 本輪 (2026-04-28 02:49 +08:00) - 全平後重啟觀察確認

- 使用者貼出 `2026-04-28 02:37` validate 成功與 `02:37:56` run 啟動紀錄，隨後用 Ctrl+C 停止。
- 完成：唯讀查詢 Binance futures，確認目前 `open_positions=0`、`open_regular_orders=0`，帳戶未實現損益為 0；本機也未發現仍在執行的 `python main.py run` 程序。
- log 顯示本次 run 期間 position sync 持續為 `positions=0 open_order_symbols=0`，未看到 `market entry success`、`target notional resolved` 或 `triggered=True`。
- 注意：本次 run 期間 log 也未看到平常大量的 `staging updated` / `signal check`，因此只能確認「沒有進場/沒有持倉」，不能嚴格證明所有幣都有逐一被評估後不符合；若要確認即時掃描，需重新啟動並觀察是否恢復 `staging updated` / `signal check`。

## 本輪 (2026-04-27 06:01 +08:00) - 帳戶持倉與 Windows run log 對照

- 使用者明確允許唯讀查詢幣安帳戶目前持倉，並提供 Windows `main.py validate` / `main.py run` 啟動日誌要求核對。
- 完成：read-only 查詢確認目前正式盤為 4 個 LONG 持倉：`LIGHTUSDT`、`OPENUSDT`、`PIPPINUSDT`、`PROMUSDT`；目前一般 open order 為 0，open algo orders 為 4，與 Windows log 的 `position sync complete positions=4 open_order_symbols=4` 一致。
- 完成：Windows log 內 `websocket connect symbols=200/200/135` 與 `symbol registry loaded data_symbols=535 candidate_symbols=528` 相互吻合，代表 535 個資料 symbol 已分 3 條 WS shard 啟動。
- [RISK] `validate` 與 `run` 都出現 `telegram send exception event_type=SERVER_TIME_SYNC_OK`，但後續 `APP_STARTUP_SUCCESS`、`MODE_SUMMARY`、`LIVE_PRODUCTION_MODE` 仍成功送出；目前判斷為單一 Telegram 通知事件異常，非主交易流程啟動失敗。
- [SKIP] 本輪未下單、未取消單、未改 `.env`、未停止 Windows 上正在跑的程式、未查/寫 DB。

## 本輪 (2026-04-27 06:02 +08:00) - DB 停止更新疑問判讀

- 使用者詢問「DB 目前停止更新是否代表 websocket 沒正常」；本輪僅做靜態程式流程與既有 log 判讀，未連 Windows 機器、未查/寫 DB、未停止程式。
- 結論：目前不能直接把「DB 暫時沒新增 row」等同於「websocket 壞掉」。正式主線設計是 `x=false` 的 in-progress `3m` 只留 staging/CSV，`x=true` 的 finalized `3m` 才會進 DB，因此 DB 天生只會在 `3m` 收盤點附近新增資料。
- 結論：從使用者貼的啟動 log 看，`websocket connect symbols=200/200/135` 正常，且沒有 `websocket reconnect` / `WEBSOCKET_RECONNECT_BLOCKED` / `db flush failed` 類錯誤；僅靠該片段不足以判定 WS 異常。
- [RISK] 使用者貼的 console 片段未包含 `staging updated`、`finalized bar buffered`、`db flush complete` 三類關鍵訊息，因此目前只能下「暫無異常證據、但尚未直接證明 DB 正在持續寫入」的結論。

## 本輪 (2026-04-27 06:07 +08:00) - 使用者手動清倉後重啟

- 使用者表示將先手動把幣安倉位全部關閉，再依序於 Windows 執行 `main.py validate` 與 `main.py run`。
- 這次重啟後，若帳戶與掛單都已清空，正常觀察值應接近 `position sync complete positions=0 open_order_symbols=0`；之後只要 websocket 正常收到新資料，仍會持續出現 `staging updated ... interval=3m`，到收盤點才會有 `finalized bar buffered` / `db flush complete`。
- [SKIP] 本輪僅記錄使用者操作計畫，未遠端控制 Windows、未下單、未取消單、未改 `.env`、未查/寫 DB。

## 本輪 (2026-04-27 06:18 +08:00) - 觀察前 commit

- 使用者要求先將目前狀態 commit，後續以既有正式盤流程繼續觀察。
- 快照：commit 前 `HEAD=2b3b2d72d4e4f2dc137e88dc38d4fe98903c497f`。
- 納入 commit 的檔案範圍：`.env.example`、`README.md`、`config.py`、`pump_system/app.py`、`pump_system/execution/order_service.py`、`tests/test_order_service_stop.py`、`HANDOFF.md`。
- 排除：`Auto_buy_Crypto.txt`、`Fix Leverage Bracket Error.txt`、`task.md`、`final_files/*`、backfill/log/pid/shell script 等 transcript、輸出物與 runtime 產物。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`python3 -m pytest -q` -> `23 passed, 1 xfailed`。

## 本輪 (2026-04-28 04:16 +08:00) - DAMUSDT 未進場原因調查

- 使用者回報 2026-04-27 在 Binance app 看到 `DAMUSDT` 似乎符合標準，但程式未選到，要求檢查。
- 完成：僅讀取 `god_rule.md`、`README.md`、`HANDOFF.md`、`config.py`、`pump_system/strategy/signal_engine.py`、`logs/app.log*` 與 Binance public exchangeInfo；未下單、未取消單、未改 `.env`、未查/寫 DB。
- 結論：`DAMUSDT` 有進入候選與訊號評估，不是候選池漏掉；2026-04-27 log 內共有 74 筆 `signal check symbol=DAMUSDT`，`triggered=True` 為 0。
- 主要擋下原因：63 筆為 `3m_not_compressed,3m_volume_too_low,3m_push_too_small,3m_not_breakout`，7 筆為 `3m_not_compressed,3m_volume_too_low,3m_push_too_small`，4 筆為 `missing_in_progress_3m`。
- 關鍵數值：策略要求 `vol_ratio_3m >= 2.0`，DAMUSDT 最高約 `0.7849`；策略要求 `ret_3m_pct >= 0.015`，DAMUSDT 最高約 `0.002215`；策略要求 `range_3m_pct <= 0.035`，DAMUSDT 當時約 `0.08325`。
- 補充：DAMUSDT 有 7 次 `breakout_3m=True`，但同時仍不符合壓縮、成交量與推動幅度，所以不會進場；`missing_in_progress_3m` 出現在 3m bar 收盤切換瞬間，屬資料狀態，不是交易所規格問題。
- Binance public exchangeInfo 顯示 `DAMUSDT` 為 `TRADING`、`PERPETUAL`、`quoteAsset=USDT`，支援 `MARKET` 與 `STOP_MARKET`，`MIN_NOTIONAL=5`，交易所規格本身不是阻擋原因。
- 2026-04-28 04:20 +08:00 補充說明：`vol_ratio_3m` 是當前未收 3m K 成交量除以最近 20 根已收 3m K 平均量；`ret_3m_pct` 是當前未收 3m K close 相對上一根已收 3m close 的漲幅；`range_3m_pct` 是最近 20 根已收 3m K 的最高價到最低價區間除以最低價，用來判斷是否壓縮。
- 策略解讀：目前條件偏「第一段啟動」而非「後段追趨勢」。若幣種後續慢慢持續上漲，`range_3m_pct` 會因前 20 根區間放大而更難通過，`vol_ratio_3m` 也會因近 20 根平均量墊高而更難達到 2 倍，`ret_3m_pct` 則要求單根 3m 仍要推升 1.5%；因此 DAMUSDT 這類「後面有漲但前面不夠像瞬間爆發」的走勢，確實可能被策略刻意漏掉。
- 2026-04-28 04:21 +08:00 取捨建議：先不要直接放寬實盤三個核心門檻，因為會同時增加追高與假突破；較穩妥路線是先新增/觀察「near-miss」或離線回測 DAMUSDT 類型，再決定是否建立第二套較小倉位的趨勢延續策略。
- 2026-04-28 04:22 +08:00 給下一位 Agent：接手時請先讀本段。不要把 DAMUSDT 判定為候選池漏單或交易所規格錯誤；目前已確認它是策略刻意未進場。若使用者要求改善，優先方案是新增 near-miss 記錄/回測，而不是直接放寬正式盤主策略門檻。
- 2026-04-28 04:23 +08:00 文件取捨：目前不建議另開一般性觀察文件，先留在 `HANDOFF.md` 即可；若使用者明確要開始長期統計 near-miss，才建立正式結構化觀察資料（建議 CSV/DB 或明確命名的 watchlist），避免多一份手寫文件變成第二個交接源。

## 本輪 (2026-04-28 04:51 +08:00) - 主策略週期可切 3m / 15m

- 使用者確認 `public.semi_auto_price_future_15m` 近 120 天資料已由另一視窗補齊，要求正式盤可用、只改字串即可自行切換 `3m` / `15m`。
- 快照：修改前 `HEAD=d867a1e07b141805b1d7aaf9269b48ec986099cf`。
- 完成：新增 `STRATEGY_INTERVAL=3m|15m`，預設維持 `3m`；切 `15m` 時會使用 `public.semi_auto_price_future_15m`、`data/inprogress_15m.csv`、Binance `kline_15m`、15m seed/backfill/catch-up/signal/fallback trigger。
- 修改檔案：`config.py`、`pump_system/app.py`、`pump_system/cache/staging_store.py`、`pump_system/db/repository.py`、`pump_system/execution/order_service.py`、`pump_system/market_data/backfill.py`、`pump_system/market_data/websocket_manager.py`、`pump_system/strategy/signal_engine.py`、`tests/test_signal_engine.py`、`.env.example`、`README.md`、`HANDOFF.md`。
- [SKIP] 未修改實際 `.env`、未啟動實盤、未下單、未取消單、未查/寫帳戶；僅做本地程式與文件修改。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`python3 -m pytest -q` -> `26 passed, 1 xfailed`；`STRATEGY_INTERVAL=15m python3 - <<...load_settings...>>` 確認 table=`public.semi_auto_price_future_15m`、CSV=`data/inprogress_15m.csv`、interval_ms=`900000`；`git diff --check -- config.py pump_system tests .env.example README.md` -> pass。
- [SUPERSEDED 2026-04-28 05:11] 本段原先記錄 15m 暫時沿用 `SIGNAL_3M_*` 名稱；後續已改為 `SIGNAL_15M_*` 獨立門檻，詳見下方「拆分 3m / 15m 訊號門檻」。

## 本輪 (2026-04-28 04:59 +08:00) - 新增中文 .env_template

- 使用者要求提供 `.env` 模板，命名為 `.env_template`，方便自行複製修改。
- 完成：新增並改寫 `.env_template`，所有註解改為中文且補充詳細用途、可填值與風險；不含任何真實 API / Telegram / DB secret；預設安全模式 `TESTNET=true`、`ENABLE_LIVE_TRADING=false`、`FUNCTION_TEST_MODE=true`，並保留正式盤切換註解。
- 模板包含：`STRATEGY_INTERVAL=3m`（可改 `15m`）、`POSITION_SIZING_MODE=FIXED_NOTIONAL`、`TARGET_NOTIONAL_USDT=50`、`MAX_CONCURRENT_POSITIONS=10`、`STOP_PRICE_MODE=IN_PROGRESS_INTERVAL_LOW` 與 `NOTIONAL_RISK_PCT` 範例。
- [SKIP] 未修改實際 `.env`、未啟動程式、未連 Binance、未查/寫 DB。
- 驗證：`git diff --check -- .env_template HANDOFF.md` -> pass；`python-dotenv dotenv_values('.env_template')` 可解析 61 個 key；檢查 `.env_template` secret 欄位皆為空，且無非註解的無效設定行。

## 本輪 (2026-04-28 05:11 +08:00) - 拆分 3m / 15m 訊號門檻

- 使用者指出 `.env_template` 的訊號門檻只有 `1m` / `3m`，在已支援 `STRATEGY_INTERVAL=15m` 後容易誤解，要求改成不會誤解的方式。
- 完成：`StrategyConfig` 改為 resolved 主週期門檻欄位；`STRATEGY_INTERVAL=3m` 讀 `SIGNAL_3M_*`，`STRATEGY_INTERVAL=15m` 讀 `SIGNAL_15M_*`，不互相 fallback。
- 完成：移除模板中的舊 `SIGNAL_1M_*`；`.env.example` 與 `.env_template` 都新增完整 `SIGNAL_15M_*`，README 改寫為 3m / 15m 對應門檻。
- 修改檔案：`config.py`、`pump_system/strategy/signal_engine.py`、`pump_system/execution/order_service.py`、`tests/test_signal_engine.py`、`.env.example`、`.env_template`、`README.md`、`HANDOFF.md`。
- [SKIP] 未修改實際 `.env`、未啟動程式、未連 Binance、未下單、未查/寫 DB。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`python3 -m pytest -q` -> `28 passed, 1 xfailed`；環境變數測試確認 `15m` 只讀 `SIGNAL_15M_*`、`3m` 只讀 `SIGNAL_3M_*`；`python-dotenv` 可解析 `.env_template` / `.env.example` 各 62 個 key，且 `SIGNAL_1M_*` 已不在模板內；`git diff --check -- config.py pump_system tests .env.example .env_template README.md HANDOFF.md` -> pass。

## 本輪 (2026-04-28) - 同步實際 .env 門檻格式

- 使用者要求直接更新實際 `.env`，但不要覆蓋既有詳細資料，也不要在交接記錄 `.env` 詳細值。
- 完成：僅同步 `.env` 的訊號門檻區塊為 3m / 15m 獨立格式，保留既有敏感值與其他實盤設定；`.env_template` 已維持同格式。
- [SKIP] 未記錄 `.env` 具體值，未啟動程式，未連 Binance，未下單，未查/寫 DB。
- 驗證：`.env` / `.env_template` 均可由 `python-dotenv` 解析，兩者都沒有 `SIGNAL_1M_*`，且皆包含 `SIGNAL_3M_*` 與 `SIGNAL_15M_*`；`load_settings()` 成功。

## 本輪 (2026-04-28 05:19 +08:00) - 主策略預設週期改為 15m

- 使用者要求預設使用 15m。
- 完成：同步實際 `.env`、`.env_template`、`.env.example` 與程式 fallback default；若未設定 `STRATEGY_INTERVAL`，程式也會使用 15m。
- [SKIP] 未記錄 `.env` 其他詳細值，未啟動程式，未連 Binance，未下單，未查/寫 DB。
- 驗證：`python3 -m compileall config.py main.py pump_system tests` -> pass；`python3 -m pytest -q` -> `29 passed, 1 xfailed`；確認 `.env` / `.env_template` / `.env.example` 的主週期一致，且 unset `STRATEGY_INTERVAL` 時 `load_settings()` 預設為 15m；`git diff --check -- config.py tests/test_signal_engine.py .env_template .env.example README.md HANDOFF.md` -> pass。

## 本輪 (2026-04-28 05:21 +08:00) - Windows 執行交接

- 使用者詢問是否可直接在 Windows 執行：`cd C:\Users\User\Documents\agent_sanbox_vm\Auto_buy_Crypto`、`.\.venv\Scripts\python.exe main.py validate`、`.\.venv\Scripts\python.exe main.py run`。
- 回答方向：可以，先跑 validate；只有 validate 成功結束後再跑 run。`run` 會依實際 `.env` 的 live/testnet 開關執行，若正式盤真單開關為啟用狀態，會產生真實交易。
- 給下一位 Agent：接手時請要求使用者貼 validate/run 最新輸出，先判讀 `APP_STARTUP_SUCCESS`、`MODE_SUMMARY`、`LIVE_PRODUCTION_MODE`、`websocket connect`、`position sync complete`、`signal check`、`db flush complete` 等關鍵 log；不要重複啟動第二個 run。
- [SKIP] 本輪未啟動程式、未連 Binance、未下單、未查/寫 DB；不記錄 `.env` 詳細值或密鑰。

## 本輪 (2026-04-28 05:51 +08:00) - 純理解專案脈絡

- 使用者要求先純讀理解專案，不執行交易、不修改策略。
- 已讀：`god_rule.md`、`README.md`、`HANDOFF.md`、使用者貼上的前次對話紀錄、`main.py`、`config.py`、`pump_system/app.py`、`pump_system/strategy/signal_engine.py`、`pump_system/execution/order_service.py`、`pump_system/notify/telegram_notifier.py`。
- 確認主線脈絡：這是 Binance USDT 永續小幣「第一段爆發」自動做多 + 原生 stop + fallback stop 系統；CLI 入口為 `main.py`，組裝核心在 `TradingApplication`。
- 確認目前正式主線：`STRATEGY_INTERVAL` 現在支援 `3m` / `15m`，且程式 fallback default 已改為 `15m`；對應 DB 表、WebSocket、backfill、staging CSV、訊號判斷與 stop trigger 都跟主週期一起切換。
- 確認目前熱區風險：`SIGNAL_15M_*` 雖已獨立，但數值仍先沿用 3m 同級預設，尚未完成 15m 專屬校準；另外 P1 `algo history fallback` 仍未實作，`tests/test_algo_fill_regression.py` 仍保留 1 個 xfail。
- [SKIP] 本輪未跑測試、未啟動程式、未連 Binance、未查/寫 DB、未改 `.env`、未改交易邏輯；僅補交接紀錄。

- 2026-04-28 10:43-10:51 +08:00：完成 DB 時區遷移 UTC+0 → UTC+8（commit `6cbfc04`）。三張 semi_auto_price_future_*m 表全部 da +8h；`Kline.db_timestamp` 改為轉成 UTC+8 naive 存入 DB；`repository.py` 讀取時將 da 視為 UTC+8 aware；`backfill.py` 時間比較邏輯同步調整。已停程式→DB migration→程式改動→測試 36 passed。現在 DB 觀看時間都是 UTC+8 對齊，無需心算時差。

